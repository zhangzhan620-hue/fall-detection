# -*- coding: utf-8 -*-
"""阿里云语音服务(VMS) 智能语音电话报警
摔倒确认后: 阿里云直接拨打家属手机, 接通后 TTS 播报话术模板(如"检测到老人疑似摔倒, 请立即查看")
开通步骤:
  1. 阿里云控制台开通"语音服务"(需企业实名 + 话术模板审核备案)
  2. 创建 TTS 话术模板, 记下模板ID (TTS_CODE)
  3. 创建 AccessKey (RAM 子账号, 仅授权语音服务)
  4. 把下面三个空填上即启用; 不填则自动跳过, 不影响其他报警通道
"""
import json
import threading
import time

ACCESS_KEY_ID = ""       # RAM AccessKey ID
ACCESS_KEY_SECRET = ""   # RAM AccessKey Secret
TTS_CODE = ""            # 审核通过的话术模板ID, 形如 TTS_123456789
CALLED_NUMBER = ""       # 家属手机号(被叫)
COOLDOWN = 120.0         # 呼叫冷却(秒)

_last_call = 0.0
_client = None


def _get_client():
    global _client
    if _client is None:
        from alibabacloud_dyvmsapi20170525.client import Client
        from alibabacloud_tea_openapi.models import Config
        _client = Client(Config(
            access_key_id=ACCESS_KEY_ID,
            access_key_secret=ACCESS_KEY_SECRET,
            endpoint="dyvmsapi.aliyuncs.com"))
    return _client


def _do_call():
    from alibabacloud_dyvmsapi20170525 import models
    req = models.SingleCallByTtsRequest(
        called_number=CALLED_NUMBER,
        tts_code=TTS_CODE,
        tts_param=json.dumps({"time": time.strftime("%H点%M分")}, ensure_ascii=False),
        play_times=2,          # 语音播 2 遍
        called_show_number=None)  # 外显号码(控制台选号后填)
    resp = _get_client().single_call_by_tts(req)
    print(f"[阿里云电话] 呼叫结果: {resp.body.code} {resp.body.message}")


def call_voice_alert(force: bool = False) -> bool:
    """摔倒确认时调用; 未配置时静默跳过"""
    global _last_call
    if not (ACCESS_KEY_ID and ACCESS_KEY_SECRET and TTS_CODE and CALLED_NUMBER):
        return False
    now = time.time()
    if not force and now - _last_call < COOLDOWN:
        print(f"[阿里云电话] 冷却中跳过（{COOLDOWN - (now - _last_call):.0f}s）")
        return False
    _last_call = now

    def _safe():
        try:
            _do_call()
        except Exception as e:
            print(f"[阿里云电话] 呼叫失败: {e}")
    threading.Thread(target=_safe, daemon=True).start()
    return True


if __name__ == "__main__":
    # 测试: 填好配置后 python aliyun_voice.py
    call_voice_alert(force=True)
    time.sleep(5)
