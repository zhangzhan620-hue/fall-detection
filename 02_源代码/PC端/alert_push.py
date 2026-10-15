# -*- coding: utf-8 -*-
"""ntfy.sh 手机推送模块（安卓/iOS 通用，支持 4G 外网）
原理: PC 向 ntfy.sh 的一个私密主题发 HTTP 消息, 订阅该主题的手机即刻收到推送
使用: 手机装 ntfy App → 订阅主题 fangshuai-fall-a1b2c3d4e5f6 即可
"""
import json
import threading
import time
import urllib.request

SERVER = "https://ntfy.sh"
TOPIC = "fangshuai-fall-a1b2c3d4e5f6"   # 私密主题名 = 密码, 泄露则换
COOLDOWN = 60.0                          # 推送冷却(秒), 防刷屏

_last_sent = 0.0


def _post(data: bytes, headers: dict):
    req = urllib.request.Request(f"{SERVER}/{TOPIC}", data=data,
                                 headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=15) as r:
        return r.status


def _do_send(detail: str, image_path: str | None):
    text = ("检测到疑似摔倒！\n"
            f"时间: {time.strftime('%H:%M:%S')}\n"
            f"{detail}\n"
            "请立即查看现场情况！")
    attach_url = None
    # 1) 先上传截图(普通优先级, 不会触发App报警), 拿到附件链接
    if image_path:
        with open(image_path, "rb") as f:
            req = urllib.request.Request(f"{SERVER}/{TOPIC}", data=f.read(),
                                         headers={"Filename": "fall.jpg"}, method="PUT")
        with urllib.request.urlopen(req, timeout=15) as r:
            resp = json.loads(r.read().decode("utf-8"))
        attach_url = (resp.get("attachment") or {}).get("url")
    # 2) 文字警报(紧急优先级) + 附件链接, 合并为一条消息
    headers = {"Title": "Fall Alert!", "Priority": "urgent",
               "Tags": "rotating_light,skull"}
    if attach_url:
        headers["Attach"] = attach_url
    _post(("⚠️ " + text).encode("utf-8"), headers)
    print("[推送] 已发送到自研App" + ("（含现场截图）" if attach_url else ""))


def send_fall_alert(detail: str = "", image_path: str | None = None,
                    force: bool = False) -> bool:
    """摔倒确认后调用; 冷却期内自动跳过(force=True 强制发, 用于测试)"""
    global _last_sent
    now = time.time()
    if not force and now - _last_sent < COOLDOWN:
        print(f"[推送] 冷却中跳过（{COOLDOWN - (now - _last_sent):.0f}s 后可再发）")
        return False
    _last_sent = now
    threading.Thread(target=_send_safe, args=(detail, image_path), daemon=True).start()
    return True


def _send_safe(detail, image_path):
    try:
        _do_send(detail, image_path)
    except Exception as e:
        print("[推送] 发送失败:", e)


if __name__ == "__main__":
    # 测试: python alert_push.py
    send_fall_alert("这是一条测试消息——手机能收到就说明链路通了", force=True)
    time.sleep(3)
