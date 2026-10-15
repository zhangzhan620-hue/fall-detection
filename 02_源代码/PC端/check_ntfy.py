# -*- coding: utf-8 -*-
"""检查 ntfy 主题上的消息记录, 验证 PC->云端 链路"""
import json
import urllib.request

url = "https://ntfy.sh/fangshuai-fall-a1b2c3d4e5f6/json?poll=1"
with urllib.request.urlopen(url, timeout=15) as r:
    n = 0
    for line in r:
        d = json.loads(line)
        if d.get("event") == "message":
            n += 1
            print("时间={} 优先级={} 标题={} 附件={} 内容={}".format(
                d.get("time"), d.get("priority"), d.get("title"),
                "有" if d.get("attachment") else "无",
                str(d.get("message", ""))[:30]))
    print(f"共 {n} 条消息在服务器上")
