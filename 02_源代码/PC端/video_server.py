# -*- coding: utf-8 -*-
"""MJPEG 视频监控流服务器: 把检测画面实时流给手机/浏览器
接口:
  /video.mjpg  实时视频流(监控画面)
  /shot.jpg    当前帧快照
"""
import socket
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import cv2


class FrameBuffer:
    """检测循环往这里塞最新帧, 视频流从这里取"""

    def __init__(self):
        self.lock = threading.Lock()
        self.jpeg = None

    def update(self, frame, quality=70):
        ok, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, quality])
        if ok:
            with self.lock:
                self.jpeg = buf.tobytes()

    def get(self):
        with self.lock:
            return self.jpeg


frame_buffer = FrameBuffer()


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path.startswith("/video.mjpg"):
            self.send_response(200)
            self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=frame")
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            while True:
                data = frame_buffer.get()
                if data:
                    try:
                        self.wfile.write(b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + data + b"\r\n")
                    except (BrokenPipeError, ConnectionResetError):
                        break
                time.sleep(0.08)  # ~12fps
        elif self.path.startswith("/shot.jpg"):
            data = frame_buffer.get()
            if data:
                self.send_response(200)
                self.send_header("Content-Type", "image/jpeg")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
            else:
                self.send_error(503)
        else:
            self.send_error(404)

    def log_message(self, *args):
        pass


def lan_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except OSError:
        return "127.0.0.1"


def start_video_server(port=8080):
    srv = ThreadingHTTPServer(("0.0.0.0", port), _Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    print(f"[监控] 视频流: http://{lan_ip()}:{port}/video.mjpg （局域网内手机/浏览器可打开）")
    return srv


if __name__ == "__main__":
    # 自测: 用测试图当画面
    start_video_server()
    img = cv2.imread("cam_test.jpg")
    while True:
        frame_buffer.update(img)
        time.sleep(0.1)
