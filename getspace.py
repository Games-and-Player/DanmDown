#!/usr/bin/python3

import time

from utils.bilibili_api import BilibiliAPI

if __name__ == '__main__':
    bili = BilibiliAPI()
    bili.login_with_cookie()
    res = bili.get_vids("67390259", "1")

    video_list = []

    for x in res.get("list").get("vlist"):
        x.get("pic")
        video_info = {
            "aid": x.get("pic"),
            "title": x.get("title"),
            "cover": x.get("pic"),
            "desc": x.get("description"),
            "tags": [],
            "cid": None,
            "created_at": time.strftime("%Y-%m-%d %H:%M", time.localtime(x.get("created"))),
            "created_timestamp": x.get("created")
        }
        video_list.append(video_info)
    print(video_list)
