from __future__ import annotations

import gzip
import socket
import time
from typing import Optional

import cv2
import numpy as np

from arknights_mower import __rootdir__
from arknights_mower.utils.image import bytes2img
from arknights_mower.utils.network import is_port_in_use, get_new_port

from .. import config
from ..log import logger, save_screenshot
from .adb_client import ADBClient
from .maatouch import MaaTouch
from .scrcpy import Scrcpy


class Device(object):
    """Android Device"""

    class Control(object):
        """Android Device Control"""

        def __init__(
            self, device: Device, client: ADBClient = None, touch_device: str = None
        ) -> None:
            self.device = device
            self.maatouch = None
            self.scrcpy = None

            if config.ADB_CONTROL_CLIENT == "maatouch":
                self.maatouch = MaaTouch(client)
            else:
                self.scrcpy = Scrcpy(client)

        def tap(self, point: tuple[int, int]) -> None:
            if self.maatouch:
                self.maatouch.tap([point], self.device.display_frames())
            elif self.scrcpy:
                self.scrcpy.tap(point[0], point[1])
            else:
                raise NotImplementedError

        def swipe(
            self, start: tuple[int, int], end: tuple[int, int], duration: int
        ) -> None:
            if self.maatouch:
                self.maatouch.swipe(
                    [start, end], self.device.display_frames(), duration=duration
                )
            elif self.scrcpy:
                self.scrcpy.swipe(start[0], start[1], end[0], end[1], duration / 1000)
            else:
                raise NotImplementedError

        def swipe_ext(
            self, points: list[tuple[int, int]], durations: list[int], up_wait: int
        ) -> None:
            if self.maatouch:
                self.maatouch.swipe(
                    points,
                    self.device.display_frames(),
                    duration=durations,
                    up_wait=up_wait,
                )
            elif self.scrcpy:
                total = len(durations)
                for idx, (S, E, D) in enumerate(
                    zip(points[:-1], points[1:], durations)
                ):
                    self.scrcpy.swipe(
                        S[0],
                        S[1],
                        E[0],
                        E[1],
                        D / 1000,
                        up_wait / 1000 if idx == total - 1 else 0,
                        fall=idx == 0,
                        lift=idx == total - 1,
                    )
            else:
                raise NotImplementedError

    def __init__(
        self, device_id: str = None, connect: str = None, touch_device: str = None
    ) -> None:
        self.device_id = device_id
        self.connect = connect
        self.touch_device = touch_device
        self.client = None
        self.control = None
        self.start()

    def start(self) -> None:
        self.client = ADBClient(self.device_id, self.connect)
        self.control = Device.Control(self, self.client)

    def run(self, cmd: str) -> Optional[bytes]:
        return self.client.run(cmd)

    def launch(self) -> None:
        """launch the application"""
        logger.info("明日方舟，启动！")

        tap = config.TAP_TO_LAUNCH["enable"]
        x = config.TAP_TO_LAUNCH["x"]
        y = config.TAP_TO_LAUNCH["y"]

        if tap:
            self.run(f"input tap {x} {y}")
        else:
            self.run(f"am start -n {config.APPNAME}/{config.APP_ACTIVITY_NAME}")

    def exit(self) -> None:
        """exit the application"""
        logger.info("退出游戏")
        self.run(f"am force-stop {config.APPNAME}")

    def send_keyevent(self, keycode: int) -> None:
        """send a key event"""
        logger.debug(f"keyevent: {keycode}")
        command = f"input keyevent {keycode}"
        self.run(command)

    def send_text(self, text: str) -> None:
        """send a text"""
        logger.debug(f"text: {repr(text)}")
        text = text.replace('"', '\\"')
        command = f'input text "{text}"'
        self.run(command)

    def get_droidcast_classpath(self) -> str | None:
        # TODO: 退出时（并非结束mower线程时）关闭DroidCast进程、取消ADB转发
        try:
            out = self.client.cmd_shell("pm path com.rayworks.droidcast", decode=True)
        except Exception:
            logger.error("无法获取CLASSPATH")
            return None
        prefix = "package:"
        postfix = ".apk"
        beg = out.index(prefix, 0)
        end = out.rfind(postfix)
        class_path = out[beg + len(prefix) : (end + len(postfix))].strip()
        class_path = "CLASSPATH=" + class_path
        logger.info(f"成功获取CLASSPATH：{class_path}")
        return class_path

    def start_droidcast(self) -> bool:
        class_path = self.get_droidcast_classpath()
        if not class_path:
            logger.info("安装DroidCast")
            apk_path = f"{__rootdir__}/vendor/droidcast/DroidCast-debug-1.2.1.apk"
            out = self.client.cmd(["install", apk_path], decode=True)
            if "Success" in out:
                logger.info("DroidCast安装完成，获取CLASSPATH")
            else:
                logger.error(f"DroidCast安装失败：{out}")
                return False
            class_path = self.get_droidcast_classpath()
            if not class_path:
                logger.error(f"无法获取CLASSPATH：{out}")
                return False
        port = config.droidcast["port"]
        if port == 0 or is_port_in_use(port):
            if port != 0:
                self.client.cmd(f"forward --remove tcp:{port}")
            port = get_new_port()
            config.droidcast["port"] = port
            logger.info(f"更新DroidCast端口为{port}")
        else:
            logger.info(f"保持DroidCast端口为{port}")
        self.client.cmd(f"forward tcp:{port} tcp:{port}")
        logger.info("ADB端口转发成功，启动DroidCast")
        process = self.client.process(
            class_path,
            [
                "app_process",
                "/",
                "com.rayworks.droidcast.Main",
                f"--port={port}",
            ],
        )
        config.droidcast["process"] = process
        return True

    def screencap(self, save: bool = False) -> bytes:
        """get a screencap"""
        if config.droidcast["enable"]:
            session = config.droidcast["session"]
            while True:
                try:
                    port = config.droidcast["port"]
                    r = session.get(f"http://127.0.0.1:{port}/screenshot")
                    img = bytes2img(r.content)
                    gray = bytes2img(r.content, True)
                    if config.droidcast["rotate"]:
                        img = cv2.rotate(img, cv2.ROTATE_180)
                        gray = cv2.rotate(gray, cv2.ROTATE_180)
                    break
                except Exception:
                    self.start_droidcast()
                    time.sleep(3)
        else:
            command = "screencap 2>/dev/null | gzip -1"
            data = gzip.decompress(self.run(command))
            array = np.frombuffer(data[-1920 * 1080 * 4 :], np.uint8).reshape(
                1080, 1920, 4
            )
            img = cv2.cvtColor(array, cv2.COLOR_RGBA2RGB)
            gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)

        screencap = cv2.imencode(".png", cv2.cvtColor(img, cv2.COLOR_RGB2BGR))[1]
        if save:
            save_screenshot(screencap)
        return screencap, img, gray

    def current_focus(self) -> str:
        """detect current focus app"""
        command = "dumpsys window | grep mCurrentFocus"
        line = self.run(command).decode("utf8")
        return line.strip()[:-1].split(" ")[-1]

    def display_frames(self) -> tuple[int, int, int]:
        """get display frames if in compatibility mode"""
        if not config.MNT_COMPATIBILITY_MODE:
            return None

        command = "dumpsys window | grep DisplayFrames"
        line = self.run(command).decode("utf8")
        """ eg. DisplayFrames w=1920 h=1080 r=3 """
        res = line.strip().replace("=", " ").split(" ")
        return int(res[2]), int(res[4]), int(res[6])

    def tap(self, point: tuple[int, int]) -> None:
        """tap"""
        logger.debug(f"tap: {point}")
        self.control.tap(point)

    def swipe(
        self, start: tuple[int, int], end: tuple[int, int], duration: int = 100
    ) -> None:
        """swipe"""
        logger.debug(f"swipe: {start} -> {end}, duration={duration}")
        self.control.swipe(start, end, duration)

    def swipe_ext(
        self, points: list[tuple[int, int]], durations: list[int], up_wait: int = 500
    ) -> None:
        """swipe_ext"""
        logger.debug(
            f"swipe_ext: points={points}, durations={durations}, up_wait={up_wait}"
        )
        self.control.swipe_ext(points, durations, up_wait)

    def check_current_focus(self) -> bool:
        """check if the application is in the foreground"""
        if self.current_focus() != f"{config.APPNAME}/{config.APP_ACTIVITY_NAME}":
            self.launch()
            # wait for app to finish launching
            time.sleep(10)
            return True
        return False
