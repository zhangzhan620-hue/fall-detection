# -*- coding: utf-8 -*-
"""实时跌倒检测 v3.1
区分"摔倒"和"睡觉/正常躺下":
  1. 追踪同一个人,检测重心是否【突然快速下坠】(快路径,几秒内报警)
  2. 没抓到下坠瞬间也有兜底: 【水平躺地 + 持续不起】(慢路径,10秒报警)
  3. 支持标定【床区域】,躺在床区域里永不报警(解决睡觉误报)
  4. 检测闪烁有2秒宽限,不会因一两帧丢失而清空轨迹
  5. 视频文件使用视频内时间戳(修复处理速度跟不上帧率导致的速度测量失真)

用法:
  python fall_detect.py            # 摄像头
  python fall_detect.py video.mp4  # 视频文件
  python fall_detect.py video.mp4 --headless  # 无窗口模式,只打印事件(用于测试)
按键:
  Q 退出 | B 标定床区域(然后在画面上点左上角、右下角两个点)
"""
import json
import sys
import threading
import time
from collections import deque

import cv2
import numpy as np
from ultralytics import YOLO

try:
    import winsound  # Windows 蜂鸣报警
except ImportError:
    winsound = None

MODEL_PATH = r"C:\Users\zhang\Downloads\yolo26n-pose.pt"
ROI_FILE = "bed_roi.json"

CONF = 0.4               # 检测置信度
DROP_SPEED = 0.30        # 下坠速度阈值: 每秒下坠超过画面高度的 30% 视为"突然倒下"
DROP_WINDOW = 1.0        # 用最近多少秒内的位移计算下坠速度
IMMOBILE_TIME = 5.0      # 快路径: 疑似跌倒后持续不动多少秒报警
DOWN_ALARM_TIME = 10.0   # 慢路径: 水平躺地持续多少秒不起来直接报警
IMMOBILE_STD = 20        # 静止判定: 重心抖动标准差小于该像素值视为"不动"
TRACK_GRACE = 2.0        # 目标丢失多少秒后才删除轨迹(防检测闪烁)
MERGE_DIST = 200         # ID合并: 新ID出现在旧轨迹该距离内时继承其状态(防闪烁换ID)
MERGE_TIME = 5.0         # 丢失轨迹保留为"影子"的秒数

L_SHOULDER, R_SHOULDER = 5, 6
L_HIP, R_HIP = 11, 12


# ---------- 基础判断 ----------

def is_horizontal(box, kpts):
    """身体是否处于水平状态(宽高比 / 躯干角度)"""
    x1, y1, x2, y2 = box
    w, h = x2 - x1, y2 - y1
    if h <= 0:
        return False
    if w / h > 1.0:
        return True
    if kpts is not None:
        pts = [kpts[i] for i in (L_SHOULDER, R_SHOULDER, L_HIP, R_HIP)]
        if all(p[0] > 0 and p[1] > 0 for p in pts):
            shoulder = (pts[0] + pts[1]) / 2
            hip = (pts[2] + pts[3]) / 2
            dx, dy = abs(shoulder[0] - hip[0]), abs(shoulder[1] - hip[1])
            if dy > 1e-3 and dx / dy > 1.2:
                return True
    return False


def hip_point(box, kpts):
    """髋部中心(关键点不可见时退化为检测框中心)"""
    if kpts is not None:
        pts = [kpts[i] for i in (L_HIP, R_HIP)]
        if all(p[0] > 0 and p[1] > 0 for p in pts):
            return (pts[0] + pts[1]) / 2
    return np.array([(box[0] + box[2]) / 2, (box[1] + box[3]) / 2])


def in_bed(pt, roi):
    if roi is None:
        return False
    return roi[0] <= pt[0] <= roi[2] and roi[1] <= pt[1] <= roi[3]


# ---------- 单人状态追踪 ----------

class PersonTracker:
    """每个追踪 ID 一份: 记录历史位置,维护 正常/疑似/报警 状态"""

    def __init__(self):
        self.hist = deque(maxlen=300)  # (time, hip_xy)
        self.state = "NORMAL"          # NORMAL / SUSPECT / ALARM
        self.down_since = None         # 开始水平躺地的时间
        self.last_seen = 0.0
        self.alarm_beeped = False

    def update(self, box, kpts, roi, frame_h, now, log=print):
        self.last_seen = now
        hip = hip_point(box, kpts)
        self.hist.append((now, hip))

        horizontal = is_horizontal(box, kpts)
        bed = in_bed(hip, roi)
        sudden = self._sudden_drop(frame_h, now)
        immobile = self._immobile(now)

        prev = self.state
        if horizontal and not bed:
            if self.down_since is None:
                self.down_since = now
            down_dur = now - self.down_since
            # 快路径: 抓到下坠瞬间 -> 疑似 -> 不动5秒 -> 报警
            if self.state == "NORMAL" and sudden:
                self.state = "SUSPECT"
            if self.state == "SUSPECT" and down_dur >= IMMOBILE_TIME and immobile:
                self.state = "ALARM"
            # 慢路径兜底: 水平躺地超过10秒不起来 -> 报警
            if down_dur >= DOWN_ALARM_TIME:
                self.state = "ALARM"
        else:
            self._reset()

        if self.state != prev:
            mm, ss = divmod(int(now), 60)
            log(f"[{mm:02d}:{ss:02d}] 状态变化: {prev} -> {self.state}")
        return self.state, hip

    def _sudden_drop(self, frame_h, now):
        old = None
        for t, p in self.hist:
            if now - t >= DROP_WINDOW:
                old = (t, p)
            else:
                break
        if old is None:
            return False
        dt = now - old[0]
        speed = (self.hist[-1][1][1] - old[1][1]) / dt / frame_h
        return speed > DROP_SPEED

    def _immobile(self, now):
        pts = [p for t, p in self.hist if now - t <= IMMOBILE_TIME]
        if len(pts) < 10:
            return False
        arr = np.array(pts)
        return arr[:, 0].std() < IMMOBILE_STD and arr[:, 1].std() < IMMOBILE_STD

    def _reset(self):
        self.state = "NORMAL"
        self.down_since = None
        self.alarm_beeped = False


# ---------- 床区域标定 ----------

mouse_clicks = []


def on_mouse(event, x, y, flags, param):
    if event == cv2.EVENT_LBUTTONDOWN:
        mouse_clicks.append((x, y))


def load_roi():
    try:
        with open(ROI_FILE, encoding="utf-8") as f:
            d = json.load(f)
        return (d["x1"], d["y1"], d["x2"], d["y2"])
    except Exception:
        return None


def save_roi(roi):
    with open(ROI_FILE, "w", encoding="utf-8") as f:
        json.dump({"x1": roi[0], "y1": roi[1], "x2": roi[2], "y2": roi[3]}, f)


def beep():
    if winsound:
        threading.Thread(target=winsound.Beep, args=(1200, 800), daemon=True).start()


# ---------- 主循环 ----------

def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    headless = "--headless" in sys.argv
    source = args[0] if args else 0
    is_file = isinstance(source, str)  # 视频文件用视频内时间戳,摄像头用墙上时钟
    t_start = float(args[1]) if len(args) > 1 else 0.0   # 可选: 从第几秒开始
    t_end = float(args[2]) if len(args) > 2 else float("inf")  # 可选: 到第几秒结束
    t0 = time.time()

    model = YOLO(MODEL_PATH)
    cap = cv2.VideoCapture(source)
    if not cap.isOpened():
        print(f"无法打开视频源: {source}")
        return
    if is_file and t_start > 0:
        cap.set(cv2.CAP_PROP_POS_MSEC, t_start * 1000)

    win = "Fall Detection (Q quit / B mark bed)"
    if not headless:
        cv2.namedWindow(win)
        cv2.setMouseCallback(win, on_mouse)

    roi = load_roi()
    marking_bed = False
    trackers = {}  # track_id -> PersonTracker
    lost = {}      # track_id -> (PersonTracker, 丢失时刻)  "影子"轨迹,用于ID合并
    zones = []     # 倒地计时区域列表,每个区域独立计时(支持多人场景)

    print("运行中... Q 退出 | B 标定床区域")

    while True:
        ok, frame = cap.read()
        if not ok:
            break
        now = cap.get(cv2.CAP_PROP_POS_MSEC) / 1000 if is_file else time.time() - t0
        if now > t_end:
            break
        fh = frame.shape[0]

        results = model.track(frame, persist=True, conf=CONF, verbose=False)[0]
        if not headless:
            frame = results.plot()

        any_alarm = False
        horizontal_hips = []  # 本帧所有"水平且不在床上"的人的髋部位置
        if results.boxes is not None and results.boxes.id is not None:
            ids = results.boxes.id.int().cpu().tolist()
            boxes = results.boxes.xyxy.cpu().numpy()
            kpts_all = results.keypoints.xy.cpu().numpy() if results.keypoints is not None and len(results.keypoints) else None

            for i, tid in enumerate(ids):
                kpts = kpts_all[i] if kpts_all is not None else None
                hip = hip_point(boxes[i], kpts)
                # ID合并: 新ID出现在旧轨迹附近时继承其状态(同一个人闪烁后换了ID)
                # 同时搜索"影子"(lost)和"本帧未出现但还在宽限期内"的活动轨迹
                if tid not in trackers:
                    best_id, best_src, best_d = None, None, MERGE_DIST
                    for gid, (g, gt) in lost.items():
                        if now - gt > MERGE_TIME or not g.hist:
                            continue
                        d = np.hypot(*(hip - g.hist[-1][1]))
                        if d < best_d:
                            best_id, best_src, best_d = gid, lost, d
                    for oid, g in trackers.items():
                        if oid in ids or now - g.last_seen < 0.3 or not g.hist:
                            continue
                        d = np.hypot(*(hip - g.hist[-1][1]))
                        if d < best_d:
                            best_id, best_src, best_d = oid, trackers, d
                    if best_id is not None:
                        trackers[tid] = best_src.pop(best_id)[0] if best_src is lost else best_src.pop(best_id)
                        print(f"    [merge] ID{best_id} -> ID{tid} (距离 {best_d:.0f}px)")
                    else:
                        if "--debug" in sys.argv:
                            cands = [(oid, round(np.hypot(*(hip - g.hist[-1][1])))) for oid, g in trackers.items() if g.hist]
                            cands += [(gid, round(np.hypot(*(hip - g.hist[-1][1])))) for gid, (g, _) in lost.items() if g.hist]
                            print(f"    [debug] 新ID{tid} hip=({hip[0]:.0f},{hip[1]:.0f}) 候选距离: {cands}")
                        trackers[tid] = PersonTracker()
                tr = trackers[tid]
                state, hip = tr.update(boxes[i], kpts, roi, fh, now,
                                       log=lambda m: print(f"ID{tid} {m}"))
                if is_horizontal(boxes[i], kpts) and not in_bed(hip, roi):
                    horizontal_hips.append(hip)
                if headless:
                    if state == "ALARM":
                        any_alarm = True
                        if not tr.alarm_beeped:
                            tr.alarm_beeped = True
                    continue

                x1, y1 = int(boxes[i][0]), int(boxes[i][1])
                if state == "ALARM":
                    any_alarm = True
                    color, text = (0, 0, 255), f"ID{tid} FALL!!!"
                    if not tr.alarm_beeped:
                        beep()
                        tr.alarm_beeped = True
                elif state == "SUSPECT":
                    color, text = (0, 165, 255), f"ID{tid} fall?"
                else:
                    color, text = (0, 255, 0), f"ID{tid} OK"
                cv2.putText(frame, text, (x1, max(y1 - 10, 20)),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)

        # 清理: 丢失的轨迹转为"影子"(保留MERGE_TIME秒供ID合并), 超期才彻底删除
        for tid in list(trackers):
            if now - trackers[tid].last_seen > TRACK_GRACE:
                lost[tid] = (trackers.pop(tid), now)
        for gid in list(lost):
            if now - lost[gid][1] > MERGE_TIME:
                del lost[gid]

        # ===== 区域倒地计时(核心报警逻辑,不依赖追踪ID,支持多人场景) =====
        for h in horizontal_hips:
            best, bd = None, 300.0
            for z in zones:
                d = float(np.hypot(*(h - z["pos"])))
                if d < bd:
                    best, bd = z, d
            if best is not None:  # 归入最近区域,计时延续
                best["last_seen"] = now
                best["pos"] = h
            else:                 # 新位置有人倒地,新建计时区域
                zones.append({"pos": h, "since": now, "alarmed": False, "last_seen": now})
                mm, ss = divmod(int(now), 60)
                print(f"[{mm:02d}:{ss:02d}] 检测到有人倒地,开始计时...")

        for z in zones:
            dur = now - z["since"]
            if dur >= DOWN_ALARM_TIME and not z["alarmed"]:
                z["alarmed"] = True
                mm, ss = divmod(int(now), 60)
                print(f"[{mm:02d}:{ss:02d}] !!! 跌倒报警 !!! 已倒地 {dur:.0f} 秒未起身")
                beep()
            if z["alarmed"]:
                any_alarm = True

        # 人爬起来/离开画面超过4秒,区域解除(宽限4秒以桥接检测闪烁)
        for z in zones[:]:
            if now - z["last_seen"] > 4.0:
                if z["alarmed"]:
                    mm, ss = divmod(int(now), 60)
                    print(f"[{mm:02d}:{ss:02d}] 报警解除: 人已起身")
                zones.remove(z)

        if headless:
            continue

        # 画床区域
        if roi:
            cv2.rectangle(frame, (roi[0], roi[1]), (roi[2], roi[3]), (255, 128, 0), 2)
            cv2.putText(frame, "BED", (roi[0] + 5, roi[1] + 25),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 128, 0), 2)

        # 画倒地计时区域
        for z in zones:
            zx, zy = int(z["pos"][0]), int(z["pos"][1])
            dur = now - z["since"]
            color = (0, 0, 255) if z["alarmed"] else (0, 165, 255)
            cv2.circle(frame, (zx, zy), 40, color, 3)
            cv2.putText(frame, f"down {dur:.0f}s", (zx - 50, zy + 70),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.9, color, 2)

        if any_alarm:
            cv2.rectangle(frame, (0, 0), (frame.shape[1], 60), (0, 0, 255), -1)
            cv2.putText(frame, "WARNING: FALL DETECTED!", (10, 42),
                        cv2.FONT_HERSHEY_SIMPLEX, 1.2, (255, 255, 255), 3)

        cv2.imshow(win, frame)
        key = cv2.waitKey(1) & 0xFF
        if key == ord("q"):
            break
        elif key == ord("b"):
            marking_bed = True
            mouse_clicks.clear()
            print("请在画面上点击床区域的 左上角 和 右下角")

        # 床区域标定: 收集两个点击点
        if marking_bed and len(mouse_clicks) >= 2:
            (ax, ay), (bx, by) = mouse_clicks[:2]
            roi = (min(ax, bx), min(ay, by), max(ax, bx), max(ay, by))
            save_roi(roi)
            marking_bed = False
            print(f"床区域已保存: {roi}")

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
