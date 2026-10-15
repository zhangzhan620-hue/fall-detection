# -*- coding: utf-8 -*-
"""老人防摔智能摄像头 - 最终版 (姿势识别 + 运动学双重跌倒确认)
原理: 人呈现"躺倒"姿态(躯干水平且框横宽)并持续0.5秒后, 做多重判据:
  1. 空间判据: 地面线/脚踝比值判断躯干是否贴地——弯腰/下蹲时躯干悬空, 排除
  2. 躯干角速度 > 60°/秒 (从竖直快速转成水平)  => 真摔倒
  3. 或重心峰值下落速度 > 0.30 画面高/秒        => 真摔倒
确认摔倒后: 本地蜂鸣 + 红色警报 + 保存现场截图(alerts/) + ntfy手机推送(带截图)
监控视频流: 局域网内手机/浏览器打开 http://电脑IP:8080/video.mjpg 实时看画面
用法:
  python pose_action_demo.py              摄像头实时(默认)
  python pose_action_demo.py 视频 [起始秒] [结束秒] [--no-push 关闭推送]
按键: Q 退出 | 空格 暂停 | G 地面线标定 | C 清除 | F 刷新地板分割
"""
import os
import sys
import threading
import time
from collections import deque

import cv2
import numpy as np
from ultralytics import YOLO

try:
    import winsound
except ImportError:
    winsound = None

# 报警/监控模块(缺失不影响主功能)
try:
    import alert_push
except ImportError:
    alert_push = None
try:
    import video_server
except ImportError:
    video_server = None


def resource_path(rel):
    """兼容 PyInstaller 打包后的资源路径"""
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(sys.argv[0])))
    return os.path.join(base, rel)


POSE_MODEL = resource_path(os.path.join("models", "yolo26n-pose.pt"))
DROP_SPEED = 0.30      # 重心下落速度阈值(画面高度/秒)
ANGULAR_SPEED = 60     # 躯干角速度阈值(度/秒)
LOOKBACK = 2.5         # 变成躺倒时, 回溯多少秒的运动数据
SNAPSHOT_DIR = "alerts"  # 报警截图保存目录
FLOOR_SEG = False      # 语义分割建模地板(SegFormer-b0/ADE20K)——已停用, 判定链自动回退
FLOOR_SEG_INTERVAL = 10.0  # 地板掩码刷新间隔(秒)

NOSE = 0
L_SHOULDER, R_SHOULDER = 5, 6
L_HIP, R_HIP = 11, 12
L_ANKLE, R_ANKLE = 15, 16


def get_pt(kpts, conf, idx):
    if conf is not None and conf[idx] < 0.25:
        return None
    p = kpts[idx]
    return p if p[0] > 0 and p[1] > 0 else None


def torso_info(kpts, conf):
    """返回 (躯干角[与竖直夹角], 髋部中点)
    优先用双肩+双髋; 关键点不全时退化用单侧肩髋对; 再不行用框宽高比估算"""
    ls, rs = get_pt(kpts, conf, L_SHOULDER), get_pt(kpts, conf, R_SHOULDER)
    lh, rh = get_pt(kpts, conf, L_HIP), get_pt(kpts, conf, R_HIP)
    hips = [p for p in (lh, rh) if p is not None]
    hip_mid = (lh + rh) / 2 if lh is not None and rh is not None else (hips[0] if hips else None)

    pairs = []
    if ls is not None and rs is not None and lh is not None and rh is not None:
        pairs.append(((ls + rs) / 2, (lh + rh) / 2))
    if ls is not None and lh is not None:
        pairs.append((ls, lh))
    if rs is not None and rh is not None:
        pairs.append((rs, rh))
    if not pairs:
        return None, hip_mid
    shoulder, hip = pairs[0]
    dx, dy = abs(shoulder[0] - hip[0]), abs(shoulder[1] - hip[1])
    angle = float(np.degrees(np.arctan2(dx, max(dy, 1e-3))))
    return angle, hip_mid


def classify_posture(box, torso_angle):
    x1, y1, x2, y2 = box
    w, h = x2 - x1, y2 - y1
    if h <= 0:
        return "UNKNOWN"
    aspect = w / h
    # 躺倒必须"躯干水平"且"框横宽"同时满足——弯腰时躯干角也很大,但框不会变宽
    if (torso_angle is not None and torso_angle > 55 and aspect > 1.0) or aspect > 1.3:
        return "LYING"
    if torso_angle is not None and torso_angle > 30:
        return "BENDING"
    if aspect > 0.55:
        return "SITTING"
    return "STANDING"


POSTURE_CN = {"STANDING": "站立", "SITTING": "坐着", "BENDING": "弯腰", "LYING": "躺倒", "UNKNOWN": "未知"}


def beep():
    if winsound:
        threading.Thread(target=winsound.Beep, args=(1200, 800), daemon=True).start()


def save_snapshot(frame):
    os.makedirs(SNAPSHOT_DIR, exist_ok=True)
    path = os.path.join(SNAPSHOT_DIR, f"fall_{time.strftime('%Y%m%d_%H%M%S')}.jpg")
    cv2.imwrite(path, frame)
    return path


class FloorSegmentor:
    """SegFormer 语义分割建模地板: 后台线程定期更新地板掩码与距离场"""

    def __init__(self):
        self.pipe = None
        self.mask = None   # 地板掩码 0/1 (帧尺寸)
        self.dist = None   # 每个像素到最近地板像素的距离
        self.last_run = 0.0
        self.busy = False
        self.lock = threading.Lock()

    def _load(self):
        os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")
        from transformers import pipeline
        self.pipe = pipeline("image-segmentation",
                             model="nvidia/segformer-b0-finetuned-ade-512-512")

    def maybe_update(self, raw_frame, now, has_person):
        if not FLOOR_SEG or self.busy:
            return
        # 地板是静止的: 首次必须分割; 之后仅当画面没人且间隔够久才自动更新(或按F手动)
        need = self.mask is None or (not has_person and now - self.last_run > 60.0)
        if not need:
            return
        self.busy = True
        self.last_run = now
        threading.Thread(target=self._worker, args=(raw_frame.copy(),), daemon=True).start()

    def _worker(self, frame):
        try:
            if self.pipe is None:
                print("[地板分割] 首次加载 SegFormer-b0 模型...")
                self._load()
            from PIL import Image
            img = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
            m = None
            for r in self.pipe(img):
                if r.get("label") == "floor":
                    m = np.array(r["mask"])
                    break
            if m is not None:
                m = cv2.resize(m, (frame.shape[1], frame.shape[0]))
                mb = (m > 128).astype(np.uint8)
                d = cv2.distanceTransform(1 - mb, cv2.DIST_L2, 3)
                with self.lock:
                    self.mask, self.dist = mb, d
                print(f"[地板分割] 已更新, 地板占比 {mb.mean()*100:.0f}%")
        except Exception as e:
            print("[地板分割] 失败:", e)
        finally:
            self.busy = False

    def dist_to_floor(self, x, y):
        with self.lock:
            if self.dist is None:
                return None
            h, w = self.dist.shape
            return float(self.dist[min(max(int(y), 0), h - 1), min(max(int(x), 0), w - 1)])


class MotionHistory:
    """记录一个人的运动历史: (时间, 髋部y, 躯干角)"""

    def __init__(self):
        self.hist = deque(maxlen=120)
        self.was_lying = False
        self.lying_since = None   # 开始呈现躺倒姿态的时刻
        self.analyzed = False     # 本次躺倒是否已做过跌倒分析
        self.leg_samples = deque(maxlen=40)  # 站立时的"脚踝-髋部"像素距离样本

    @property
    def leg_len(self):
        """自校准腿长标尺(像素): 站立时脚踝≈地面, 踝髋距离即腿长"""
        if len(self.leg_samples) >= 5:
            return float(np.median(self.leg_samples))
        return None

    def add(self, t, hip_y, angle):
        self.hist.append((t, hip_y, angle))

    def analyze_fall(self, t, frame_h):
        """变成躺倒的瞬间调用: 回溯LOOKBACK秒, 计算峰值角速度和下落速度"""
        pts = [(tt, y, a) for tt, y, a in self.hist if t - tt <= LOOKBACK]
        if len(pts) < 5:
            return False, 0.0, 0.0

        # 峰值下落速度: 任意0.5秒窗口内髋部下降速度
        peak_speed = 0.0
        for i in range(len(pts)):
            for j in range(i + 1, len(pts)):
                dt = pts[j][0] - pts[i][0]
                if 0.3 <= dt <= 1.5:
                    speed = (pts[j][1] - pts[i][1]) / dt / frame_h
                    peak_speed = max(peak_speed, speed)

        # 峰值角速度: 相邻有效角度采样之间
        peak_ang = 0.0
        valid = [(tt, a) for tt, _, a in pts if a is not None]
        for i in range(1, len(valid)):
            dt = valid[i][0] - valid[i - 1][0]
            if dt > 0.001:
                w = abs(valid[i][1] - valid[i - 1][1]) / dt
                peak_ang = max(peak_ang, w)

        confirmed = peak_speed > DROP_SPEED or peak_ang > ANGULAR_SPEED
        return confirmed, peak_speed, peak_ang


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    no_push = "--no-push" in sys.argv
    video = args[0] if args else "cam"   # 默认摄像头
    t_start = float(args[1]) if len(args) > 1 else 0.0
    t_end = float(args[2]) if len(args) > 2 else float("inf")

    # 摄像头模式: python pose_action_demo.py cam [编号]
    use_cam = video.lower() in ("cam", "camera") or video.isdigit()
    cam_idx = int(video) if video.isdigit() else 0

    model = YOLO(POSE_MODEL)
    cap = cv2.VideoCapture(cam_idx, cv2.CAP_DSHOW) if use_cam else cv2.VideoCapture(video)
    if not cap.isOpened():
        print(f"无法打开视频源: {video}")
        return
    if not use_cam and t_start > 0:
        cap.set(cv2.CAP_PROP_POS_MSEC, t_start * 1000)
    t0 = time.time()

    # 启动监控视频流(局域网手机/浏览器可看)
    stream_on = video_server is not None
    if stream_on:
        try:
            video_server.start_video_server(8080)
        except Exception as e:
            print("[监控] 视频流启动失败:", e)
            stream_on = False
    push_on = alert_push is not None and not no_push
    print("[推送] ntfy 手机推送已启用" if push_on else "[推送] 已关闭")

    win = "Pose + Motion Fall Confirm (Q quit / Space pause)"
    people = {}  # id -> MotionHistory
    fall_msg = {}  # id -> (过期时间, 文本)  确认结果在屏幕上停留几秒

    # ---- 地面线标定: y = a*x + b ----
    ground_clicks = []            # 手动标定的地面点(按G后鼠标点击)
    ankle_pts = deque(maxlen=300)  # 自动收集的脚踝点(站立时脚踝在地面上)
    ground_line = None            # (a, b)
    mark_mode = False

    def fit_ground():
        pts = list(ground_clicks) + list(ankle_pts)
        if len(pts) < 2:
            return None
        xs = np.array([p[0] for p in pts])
        ys = np.array([p[1] for p in pts])
        a, b = np.polyfit(xs, ys, 1)
        return a, b

    def on_mouse(event, x, y, flags, param):
        if mark_mode and event == cv2.EVENT_LBUTTONDOWN:
            ground_clicks.append((x, y))
            print(f"地面标定点 +1: ({x}, {y})  当前共 {len(ground_clicks)} 个")

    cv2.namedWindow(win)
    cv2.setMouseCallback(win, on_mouse)

    floorseg = FloorSegmentor()

    print(f"播放 {video} 从 {t_start}s, Q 退出 | G 地面标定模式 | C 清除标定点 | F 刷新地板分割")

    paused = False
    while True:
        if not paused:
            ok, frame = cap.read()
            if not ok:
                break
            # 摄像头用墙上时钟(处理多快时间就过多快); 视频文件用视频内时间戳
            t = (time.time() - t0) if use_cam else cap.get(cv2.CAP_PROP_POS_MSEC) / 1000
            if not use_cam and t > t_end:
                break
            fh = frame.shape[0]
            fw = frame.shape[1]

            r = model.track(frame, persist=True, conf=0.2, verbose=False)[0]
            has_person = r.boxes is not None and len(r.boxes) > 0
            floorseg.maybe_update(frame, t, has_person)  # 原始帧跑地板分割(后台线程; 有人时不刷新)
            frame = r.plot()

            if r.boxes is not None and r.boxes.id is not None:
                ids = r.boxes.id.int().cpu().tolist()
                boxes = r.boxes.xyxy.cpu().numpy()
                kpts_all = r.keypoints.xy.cpu().numpy()
                conf_all = r.keypoints.conf.cpu().numpy() if r.keypoints.conf is not None else None

                for i, tid in enumerate(ids):
                    conf_i = conf_all[i] if conf_all is not None else None
                    angle, hip = torso_info(kpts_all[i], conf_i)
                    posture = classify_posture(boxes[i], angle)

                    # 脚踝(地面参考点): 站立时踝髋距离 = 腿长标尺
                    la = get_pt(kpts_all[i], conf_i, L_ANKLE)
                    ra = get_pt(kpts_all[i], conf_i, R_ANKLE)
                    ankles = [p for p in (la, ra) if p is not None]
                    ankle_y = max(p[1] for p in ankles) if ankles else None

                    # 躯干三点(鼻子/肩中心/髋中心)——弯腰与摔倒的本质区别在躯干是否贴地
                    nose = get_pt(kpts_all[i], conf_i, NOSE)
                    ls = get_pt(kpts_all[i], conf_i, L_SHOULDER)
                    rs = get_pt(kpts_all[i], conf_i, R_SHOULDER)
                    shoulder_mid = ((ls + rs) / 2 if ls is not None and rs is not None
                                    else (ls if ls is not None else rs))
                    lw = get_pt(kpts_all[i], conf_i, 9)   # 左腕
                    rw = get_pt(kpts_all[i], conf_i, 10)  # 右腕

                    mh = people.setdefault(tid, MotionHistory())
                    if hip is not None:
                        mh.add(t, hip[1], angle)
                    if posture == "STANDING" and hip is not None and ankle_y is not None \
                            and ankle_y > hip[1] + 20:
                        mh.leg_samples.append(ankle_y - hip[1])
                        # 站立时的脚踝位置即地面点, 自动收集用于拟合地面线
                        for p in ankles:
                            ankle_pts.append((p[0], p[1]))

                    x1, y1 = int(boxes[i][0]), int(boxes[i][1])
                    is_lying = posture == "LYING"

                    # === 关键逻辑: 躺倒姿态持续0.5秒后才回溯分析 ===
                    # (弯腰捡东西只是瞬间"像躺倒", 持续确认可过滤)
                    if is_lying:
                        if not mh.was_lying:
                            mh.lying_since = t
                            mh.analyzed = False
                        elif not mh.analyzed and hip is not None and t - mh.lying_since >= 0.5:
                            mh.analyzed = True
                            # 空间判据(三级优先): 分割地板距离场 > 地面线 > 脚踝比值
                            # 弯腰: 手可摸地但肩/髋/头悬空; 摔倒: 躯干三点全部贴地
                            on_ground = None
                            ratio = None
                            df = floorseg.dist_to_floor(hip[0], hip[1]) if mh.leg_len else None
                            if df is not None:
                                ratio = df / mh.leg_len
                                on_ground = ratio < 0.30
                                # 躯干深度校验: 肩、头也必须贴地(缺点的子项自动跳过)
                                for pt, thr in ((shoulder_mid, 0.45), (nose, 0.55)):
                                    if pt is not None and on_ground:
                                        dpt = floorseg.dist_to_floor(pt[0], pt[1])
                                        if dpt is not None and dpt / mh.leg_len > thr:
                                            on_ground = False
                                            ratio = dpt / mh.leg_len
                            elif ground_line is not None and mh.leg_len:
                                gy = ground_line[0] * hip[0] + ground_line[1]
                                ratio = (gy - hip[1]) / mh.leg_len
                                on_ground = ratio < 0.30
                            elif ankle_y is not None and mh.leg_len:
                                ratio = (ankle_y - hip[1]) / mh.leg_len
                                on_ground = ratio < 0.35
                            if on_ground is False:
                                fall_msg[tid] = (t + 2.0, f"bending/squat, torso above floor ({ratio:.2f})")
                                mm, ss = divmod(int(t), 60)
                                print(f"[{mm:02d}:{ss:02d}] ID{tid} 弯腰/下蹲(躯干离地板{ratio:.2f}个腿长), 不报警")
                            else:
                                confirmed, spd, ang = mh.analyze_fall(t, fh)
                                if confirmed:
                                    fall_msg[tid] = (t + 4.0, f"FALL CONFIRMED! v={spd:.2f} w={ang:.0f}deg/s")
                                    mm, ss = divmod(int(t), 60)
                                    print(f"[{mm:02d}:{ss:02d}] ID{tid} 确认摔倒! 峰速={spd:.2f} 角速度={ang:.0f}°/s 髋高比={ratio if ratio is None else round(ratio,2)}")
                                    beep()
                                    shot = save_snapshot(frame)
                                    print(f"[截图] 已保存: {shot}")
                                    if push_on:
                                        alert_push.send_fall_alert(
                                            f"峰速={spd:.2f} 角速度={ang:.0f}°/s", image_path=shot)
                                else:
                                    fall_msg[tid] = (t + 3.0, f"slow lie down (v={spd:.2f} w={ang:.0f})")
                                    mm, ss = divmod(int(t), 60)
                                    print(f"[{mm:02d}:{ss:02d}] ID{tid} 缓慢躺下,不报警 (峰速={spd:.2f} 角速度={ang:.0f}°/s)")
                    else:
                        mh.lying_since = None
                        mh.analyzed = False
                    mh.was_lying = is_lying

                    # 标签颜色和文字
                    if tid in fall_msg and t < fall_msg[tid][0]:
                        msg = fall_msg[tid][1]
                        color = (0, 0, 255) if "CONFIRMED" in msg else (200, 200, 200)
                        cv2.putText(frame, f"ID{tid} {msg}", (x1, max(y1 - 35, 45)),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
                    color = {"LYING": (0, 165, 255), "BENDING": (0, 255, 255)}.get(posture, (0, 255, 0))
                    label = f"ID{tid} {POSTURE_CN[posture]}"
                    if angle is not None:
                        label += f" {angle:.0f}deg"
                    cv2.putText(frame, label, (x1, max(y1 - 10, 70)),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)

                    # 关键点触地可视化: 绿实点=接触地板, 灰圈=悬空(阈值15像素)
                    for pt in (nose, shoulder_mid, hip, lw, rw, la, ra):
                        if pt is None:
                            continue
                        dpt = floorseg.dist_to_floor(pt[0], pt[1])
                        if dpt is None:
                            continue
                        touching = dpt < 15
                        cv2.circle(frame, (int(pt[0]), int(pt[1])),
                                   7 if touching else 5,
                                   (0, 220, 0) if touching else (150, 150, 150),
                                   -1 if touching else 1)

            for tid in list(people):
                if not people[tid].hist or t - people[tid].hist[-1][0] > 2.0:
                    del people[tid]

        # ---- 地板掩码叠加显示(淡绿色) ----
        with floorseg.lock:
            fm = None if floorseg.mask is None else floorseg.mask
        if fm is not None:
            frame[fm > 0] = (frame[fm > 0].astype(np.float32) * 0.85
                             + np.array([0, 200, 0], dtype=np.float32) * 0.15).astype(np.uint8)

        # ---- 拟合与绘制地面线 ----
        if len(ground_clicks) >= 2 or len(ankle_pts) >= 10:
            gl = fit_ground()
            if gl is not None:
                ground_line = gl
        if ground_line is not None:
            a, b = ground_line
            cv2.line(frame, (0, int(b)), (fw, int(a * fw + b)), (0, 200, 0), 2)
            cv2.putText(frame, "GROUND", (10, max(int(b) - 8, 20)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 200, 0), 2)
        for (cx, cy) in ground_clicks:
            cv2.circle(frame, (cx, cy), 5, (0, 200, 0), -1)
        if mark_mode:
            cv2.putText(frame, "GROUND MARK MODE: click floor points, press G to finish",
                        (10, fh - 15), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 200, 0), 2)

        # ---- 全局警报横幅: 有未过期的摔倒确认 ----
        if any("CONFIRMED" in m and t < exp for exp, m in fall_msg.values()):
            cv2.rectangle(frame, (0, 0), (fw, 60), (0, 0, 255), -1)
            cv2.putText(frame, "WARNING: FALL DETECTED!", (10, 42),
                        cv2.FONT_HERSHEY_SIMPLEX, 1.2, (255, 255, 255), 3)

        # ---- 推流到局域网(手机看监控画面) ----
        if stream_on:
            video_server.frame_buffer.update(frame)

        cv2.imshow(win, frame)
        key = cv2.waitKey(30) & 0xFF
        if key == ord("q"):
            break
        elif key == ord(" "):
            paused = not paused
        elif key == ord("g"):
            mark_mode = not mark_mode
            if not mark_mode and len(ground_clicks) >= 2:
                ground_line = fit_ground()
                print(f"地面线已标定: y = {ground_line[0]:.3f}x + {ground_line[1]:.1f} (手动{len(ground_clicks)}点+自动{len(ankle_pts)}点)")
        elif key == ord("c"):
            ground_clicks.clear()
            ankle_pts.clear()
            ground_line = None
            print("地面标定点已清除")
        elif key == ord("f"):
            floorseg.last_run = 0  # 下一帧强制刷新地板分割
            print("手动刷新地板分割...")

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
