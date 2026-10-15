# -*- coding: utf-8 -*-
"""4G 电话模块拨号报警（SIM800C / Air780E 等 AT 指令模块）
摔倒确认后: 模块直接拨打家属手机, 响铃 RING_SECONDS 秒后自动挂断
硬件: 模块插 USB(识别为串口), 装一张能打电话的 SIM 卡
自测: python call_module.py COM4 13800138000
"""
import sys
import threading
import time

try:
    import serial
except ImportError:
    serial = None

COM_PORT = "COM4"          # 模块串口（设备管理器里看）
FAMILY_PHONE = ""          # 家属手机号, 填入即启用
RING_SECONDS = 30          # 响铃多久无人接则挂断
VOICE_MSG = "家中老人疑似摔倒，请立即查看监控画面"   # 接通后播放的语音
VOICE_TIMES = 2            # 语音播放遍数
COOLDOWN = 120.0           # 拨号冷却(秒), 防重复呼叫

_last_call = 0.0


def _at(ser, cmd, wait=1.0):
    ser.write((cmd + "\r\n").encode())
    time.sleep(wait)
    return ser.read(ser.in_waiting or 1).decode(errors="ignore")


def _wait_answer(ser, timeout):
    """轮询 AT+CLCC 直到对方接通(呼叫进入通话态)或超时"""
    t0 = time.time()
    while time.time() - t0 < timeout:
        r = _at(ser, "AT+CLCC", wait=0.8)
        # 通话中: +CLCC: 1,0,0,... 第三个字段 stat=0 表示已接通
        if "+CLCC" in r:
            try:
                stat = int(r.split("+CLCC:")[1].split(",")[2])
                if stat == 0:
                    return True
            except (IndexError, ValueError):
                pass
    return False


def _speak(ser, text):
    """SIM800C 内置 TTS: 通话中播放中文合成语音"""
    _at(ser, 'AT+CSCS="UCS2"', wait=0.3)           # 切换到 UCS2 编码以支持中文
    _at(ser, "AT+CTTSPARAM=6,3,50,50,1", wait=0.3)  # 音量/语速/音调
    hex_text = text.encode("utf-16-be").hex().upper()
    for _ in range(VOICE_TIMES):
        _at(ser, f'AT+CTTS=1,"{hex_text}"', wait=len(text) * 0.35 + 2)
    _at(ser, 'AT+CSCS="GSM"', wait=0.3)


def _do_call(phone):
    with serial.Serial(COM_PORT, 115200, timeout=2) as ser:
        r = _at(ser, "AT")
        if "OK" not in r:
            raise RuntimeError(f"模块无响应: {r!r}")
        print(f"[电话] 模块在线, 拨打 {phone} ...")
        _at(ser, f"ATD{phone};", wait=0.5)      # 拨号
        if _wait_answer(ser, RING_SECONDS):
            print("[电话] 对方已接通, 播放报警语音...")
            _speak(ser, VOICE_MSG)
            _at(ser, "ATH")
            print("[电话] 语音播报完成, 已挂断")
        else:
            _at(ser, "ATH")
            print(f"[电话] {RING_SECONDS}s 无人接听, 已挂断")


def call_family(phone: str | None = None, force: bool = False) -> bool:
    """摔倒确认时调用; 模块未接/未配置时静默跳过, 不影响主流程"""
    global _last_call
    phone = phone or FAMILY_PHONE
    if not phone or serial is None:
        return False
    now = time.time()
    if not force and now - _last_call < COOLDOWN:
        print(f"[电话] 冷却中跳过（{COOLDOWN - (now - _last_call):.0f}s）")
        return False
    _last_call = now

    def _safe():
        try:
            _do_call(phone)
        except Exception as e:
            print(f"[电话] 拨号失败: {e}")
    threading.Thread(target=_safe, daemon=True).start()
    return True


if __name__ == "__main__":
    port = sys.argv[1] if len(sys.argv) > 1 else COM_PORT
    num = sys.argv[2] if len(sys.argv) > 2 else FAMILY_PHONE
    if not num:
        print("用法: python call_module.py <串口> <手机号>")
    else:
        COM_PORT = port
        call_family(num, force=True)
        time.sleep(RING_SECONDS + 5)
