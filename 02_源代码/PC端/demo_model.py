# -*- coding: utf-8 -*-
"""用自己训练的模型演示视频检测
用法: python demo_model.py [视频] [起始秒] [结束秒] [模型路径]
按键: Q 退出 | 空格 暂停/继续
"""
import sys

import cv2
from ultralytics import YOLO

DEFAULT_MODEL = r"runs\detect\runs_fall\train_yolo26n\weights\best.pt"

def main():
    video = sys.argv[1] if len(sys.argv) > 1 else "458403333-1-192.mp4"
    t_start = float(sys.argv[2]) if len(sys.argv) > 2 else 0.0
    t_end = float(sys.argv[3]) if len(sys.argv) > 3 else float("inf")
    model_path = sys.argv[4] if len(sys.argv) > 4 else DEFAULT_MODEL

    model = YOLO(model_path)
    cap = cv2.VideoCapture(video)
    if t_start > 0:
        cap.set(cv2.CAP_PROP_POS_MSEC, t_start * 1000)

    win = "My Fall Model (Q quit / Space pause)"
    print(f"播放 {video}  从 {t_start}s 开始, Q 退出")

    paused = False
    while True:
        if not paused:
            ok, frame = cap.read()
            if not ok:
                break
            t = cap.get(cv2.CAP_PROP_POS_MSEC) / 1000
            if t > t_end:
                break
            r = model(frame, conf=0.4, verbose=False)[0]
            frame = r.plot()
            mm, ss = divmod(int(t), 60)
            cv2.putText(frame, f"{mm:02d}:{ss:02d}", (10, 40),
                        cv2.FONT_HERSHEY_SIMPLEX, 1.2, (255, 255, 255), 3)

        cv2.imshow(win, frame)
        key = cv2.waitKey(30) & 0xFF
        if key == ord("q"):
            break
        elif key == ord(" "):
            paused = not paused

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
