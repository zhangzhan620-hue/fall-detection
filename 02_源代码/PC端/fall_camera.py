# -*- coding: utf-8 -*-
"""老人防摔智能摄像头 - 最终整合版
功能:
  1. 自训练 YOLO 模型实时检测 fall (持续3秒确认)
  2. 报警: 本地蜂鸣 + 红色警告 + 自动保存现场截图
  3. 手机推送: ntfy.sh 推送文字+截图 (需手机装 ntfy 订阅主题)
  4. 视频监控流: 局域网内手机/浏览器打开 http://电脑IP:8080/video.mjpg 实时看画面
  5. 可选: 4G电话模块 / 阿里云语音电话 (配置了才启用, 未配置自动跳过)
用法:
  FallCamera.exe            摄像头
  FallCamera.exe video.mp4  视频文件
  python fall_camera.py --no-push   关闭推送(测试用)
"""
import os
import sys
import threading
import time

import cv2
from ultralytics import YOLO

try:
    import winsound
except ImportError:
    winsound = None

# 报警模块(缺失也不影响主功能)
try:
    import alert_push
except ImportError:
    alert_push = None
try:
    import video_server
except ImportError:
    video_server = None

ALARM_AFTER = 3.0    # fall 持续多少秒报警
CLEAR_AFTER = 2.0    # fall 消失多少秒解除
SNAPSHOT_DIR = "alerts"  # 报警截图保存目录


def resource_path(rel):
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(sys.argv[0])))
    return os.path.join(base, rel)


def beep():
    if winsound:
        threading.Thread(target=winsound.Beep, args=(1200, 800), daemon=True).start()


def save_snapshot(frame):
    os.makedirs(SNAPSHOT_DIR, exist_ok=True)
    path = os.path.join(SNAPSHOT_DIR, f"fall_{time.strftime('%Y%m%d_%H%M%S')}.jpg")
    cv2.imwrite(path, frame)
    return path


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    no_push = "--no-push" in sys.argv
    source = args[0] if args else 0
    is_file = isinstance(source, str)

    model = YOLO(resource_path("best.pt"))
    fall_cls = [i for i, n in model.names.items() if n == "fall"]
    if not fall_cls:
        print("模型中没有 fall 类别!")
        return
    fall_cls = fall_cls[0]

    cap = cv2.VideoCapture(source)
    if not cap.isOpened():
        print(f"无法打开视频源: {source}")
        return

    # 启动监控视频流(局域网手机可看)
    stream_on = video_server is not None
    if stream_on:
        try:
            video_server.start_video_server(8080)
        except Exception as e:
            print("[监控] 视频流启动失败:", e)
            stream_on = False

    win = "Fall Detection Camera (Q quit)"
    fall_start = None
    last_fall = None
    alarming = False
    t0 = time.time()
    print("智能摄像头运行中... Q 退出")
    if not alert_push or no_push:
        print("[推送] 已关闭")
    else:
        print("[推送] ntfy 手机推送已启用")

    while True:
        ok, frame = cap.read()
        if not ok:
            if is_file:
                break
            continue
        now = cap.get(cv2.CAP_PROP_POS_MSEC) / 1000 if is_file else time.time() - t0

        r = model(frame, conf=0.5, verbose=False)[0]
        frame = r.plot()

        fall_now = any(int(c) == fall_cls for c in r.boxes.cls.tolist()) if r.boxes is not None else False

        if fall_now:
            if fall_start is None:
                fall_start = now
            last_fall = now
            dur = now - fall_start
            cv2.putText(frame, f"fall {dur:.1f}s", (10, 100),
                        cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 165, 255), 2)
            if dur >= ALARM_AFTER and not alarming:
                alarming = True
                mm, ss = divmod(int(now), 60)
                print(f"[{mm:02d}:{ss:02d}] !!! 跌倒报警 !!!")
                beep()
                shot = save_snapshot(frame)
                print(f"[截图] 已保存: {shot}")
                if alert_push and not no_push:
                    alert_push.send_fall_alert(f"现场截图: {shot}", image_path=shot)
        else:
            if last_fall is not None and now - last_fall > CLEAR_AFTER:
                if alarming:
                    print("报警解除: 人已起身或离开")
                fall_start = None
                last_fall = None
                alarming = False

        if alarming:
            cv2.rectangle(frame, (0, 0), (frame.shape[1], 60), (0, 0, 255), -1)
            cv2.putText(frame, "WARNING: FALL DETECTED!", (10, 42),
                        cv2.FONT_HERSHEY_SIMPLEX, 1.2, (255, 255, 255), 3)
            beep()

        # 推流到局域网
        if stream_on:
            video_server.frame_buffer.update(frame)

        cv2.imshow(win, frame)
        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
