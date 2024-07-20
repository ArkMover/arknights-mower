from functools import lru_cache
from typing import Union

import cv2
import numpy as np

from arknights_mower import __rootdir__
from arknights_mower.utils import typealias as tp
from arknights_mower.utils.log import logger, save_screenshot
from arknights_mower.utils.path import get_path


def bytes2img(data: bytes, gray: bool = False) -> Union[tp.Image, tp.GrayImage]:
    """bytes -> image"""
    if gray:
        return cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_GRAYSCALE)
    else:
        return cv2.cvtColor(
            cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR),
            cv2.COLOR_BGR2RGB,
        )


def img2bytes(img) -> bytes:
    """bytes -> image"""
    return cv2.imencode(".png", img)[1]


def loadres(res: str, gray: bool = False) -> Union[tp.Image, tp.GrayImage]:
    if res.startswith("@hot"):
        res_name = res.replace("@hot", "@install/tmp/hot_update", 1)
    else:
        res_name = f"{__rootdir__}/resources/{res}"
    if not res.endswith(".jpg"):
        res_name += ".png"
    filename = get_path(res_name, "")
    return loadimg(filename, gray)


@lru_cache(maxsize=128)
def loadimg(filename: str, gray: bool = False) -> Union[tp.Image, tp.GrayImage]:
    """load image from file"""
    logger.debug(filename)
    img_data = np.fromfile(filename, dtype=np.uint8)
    if gray:
        return cv2.imdecode(img_data, cv2.IMREAD_GRAYSCALE)
    else:
        return cv2.cvtColor(cv2.imdecode(img_data, cv2.IMREAD_COLOR), cv2.COLOR_BGR2RGB)


def thres2(img: tp.GrayImage, thresh: int) -> tp.GrayImage:
    """binarization of images"""
    _, ret = cv2.threshold(img, thresh, 255, cv2.THRESH_BINARY)
    return ret


# def thres0(img: tp.Image, thresh: int) -> tp.Image:
#     """ delete pixel, filter: value > thresh """
#     ret = img.copy()
#     if len(ret.shape) == 3:
#         # ret[rgb2gray(img) <= thresh] = 0
#         z0 = ret[:, :, 0]
#         z1 = ret[:, :, 1]
#         z2 = ret[:, :, 2]
#         _ = (z0 <= thresh) | (z1 <= thresh) | (z2 <= thresh)
#         z0[_] = 0
#         z1[_] = 0
#         z2[_] = 0
#     else:
#         ret[ret <= thresh] = 0
#     return ret


# def thres0(img: tp.Image, thresh: int) -> tp.Image:  # not support multichannel image
#     """ delete pixel which > thresh """
#     _, ret = cv2.threshold(img, thresh, 255, cv2.THRESH_TOZERO)
#     return ret


def rgb2gray(img: tp.Image) -> tp.GrayImage:
    """change image from rgb to gray"""
    return cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)


def scope2slice(scope: tp.Scope) -> tp.Slice:
    """((x0, y0), (x1, y1)) -> ((y0, y1), (x0, x1))"""
    if scope is None:
        return slice(None), slice(None)
    return slice(scope[0][1], scope[1][1]), slice(scope[0][0], scope[1][0])


def cropimg(img: tp.Image, scope: tp.Scope) -> tp.Image:
    """crop image"""
    return img[scope2slice(scope)]


def saveimg(img, folder="failure"):
    save_screenshot(
        img2bytes(cv2.cvtColor(img, cv2.COLOR_BGR2RGB)),
        subdir=f"{folder}/{img.shape[0]}x{img.shape[1]}",
    )


def saveimg_depot(img, filename, folder="depot"):
    """filename 传入文件拓展名"""
    save_screenshot(
        img2bytes(cv2.cvtColor(img, cv2.COLOR_BGR2RGB)),
        subdir=f"{folder}/",
        filename=filename,
    )


def cmatch(
    img1: tp.Image, img2: tp.Image, thresh: int = 10, draw: bool = False
) -> tp.Scope | None:
    """比较平均色"""
    h, w, _ = img1.shape
    ca = cv2.mean(img1)[:3]
    cb = cv2.mean(img2)[:3]
    diff = np.array(ca).astype(int) - np.array(cb).astype(int)
    diff = np.max(np.maximum(diff, 0)) - np.min(np.minimum(diff, 0))
    logger.debug(f"{ca=} {cb=} {diff=}")

    if draw:
        board = np.zeros([h + 5, w * 2, 3], dtype=np.uint8)
        board[:h, :w, :] = img1
        board[h:, :w, :] = ca
        board[:h, w:, :] = img2
        board[h:, w:, :] = cb

        from matplotlib import pyplot as plt

        plt.imshow(board)
        plt.show()

    return diff <= thresh
