import os
import sys
from datetime import datetime
from importlib import reload
from io import BytesIO
from shutil import rmtree
from time import mktime
from zipfile import ZipFile

import requests
from htmllistparse import fetch_listing

from arknights_mower.utils.image import loadimg
from arknights_mower.utils.log import logger
from arknights_mower.utils.path import get_path

extract_path = get_path("@install/tmp/hot_update")
sign_in = None
navigation = None


def update():
    logger.info("检查热更新资源")
    mirror = "https://mower.zhaozuohong.vip"
    filename = "hot_update.zip"
    cwd, listing = fetch_listing(mirror)
    entry = next(i for i in listing if i.name == filename)
    remote_time = datetime.fromtimestamp(mktime(entry.modified))
    download_update = True
    if extract_path.exists():
        local_time = datetime.fromtimestamp(os.path.getctime(extract_path))
        if local_time > remote_time:
            download_update = False
        else:
            rmtree(extract_path)
    if download_update:
        logger.info("开始下载热更新资源")
        retry_times = 3
        for i in range(retry_times):
            try:
                r = requests.get(f"{mirror}/{filename}")
                ZipFile(BytesIO(r.content)).extractall(extract_path)
                break
            except Exception as e:
                logger.info(f"热更新出错：{e}")
        if i >= retry_times:
            logger.error("热更新失败！")
            return
        logger.info("热更新成功")
    else:
        logger.info("本地资源已是最新")

    global sign_in
    global navigation
    if "sign_in" in sys.modules and "navigation" in sys.modules:
        if download_update:
            loadimg.cache_clear()
            reload(sign_in)
            reload(navigation)
    else:
        if extract_path not in sys.path:
            sys.path.append(str(extract_path))
        import navigation
        import sign_in