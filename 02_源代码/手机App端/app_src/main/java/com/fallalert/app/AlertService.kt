package com.fallalert.app

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Context
import android.content.Intent
import android.media.Ringtone
import android.media.RingtoneManager
import android.net.Uri
import android.os.Build
import android.os.IBinder
import android.os.PowerManager
import android.os.VibrationEffect
import android.os.Vibrator
import org.json.JSONObject
import java.io.BufferedReader
import java.io.InputStreamReader
import java.net.HttpURLConnection
import java.net.URL

class AlertService : Service() {

    companion object {
        @Volatile var reconnectRequested = false
        private var ringtone: Ringtone? = null
        private var vibrator: Vibrator? = null

        fun startAlarm(ctx: Context) {
            if (ringtone == null) {
                val uri: Uri = RingtoneManager.getDefaultUri(RingtoneManager.TYPE_ALARM)
                ringtone = RingtoneManager.getRingtone(ctx.applicationContext, uri)
            }
            if (Build.VERSION.SDK_INT >= 28) ringtone?.isLooping = true
            ringtone?.play()
            vibrator = ctx.getSystemService(Context.VIBRATOR_SERVICE) as Vibrator
            if (Build.VERSION.SDK_INT >= 26) {
                vibrator?.vibrate(VibrationEffect.createWaveform(longArrayOf(0, 600, 400, 600), 0))
            } else {
                @Suppress("DEPRECATION") vibrator?.vibrate(longArrayOf(0, 600, 400, 600), 0)
            }
        }

        fun stopAlarm() {
            ringtone?.stop()
            vibrator?.cancel()
        }
    }

    private var running = false

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onCreate() {
        super.onCreate()
        val nm = getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        nm.createNotificationChannel(
            NotificationChannel("fall_alerts", "跌倒警报", NotificationManager.IMPORTANCE_HIGH).apply {
                description = "检测到摔倒时的高优先级报警"
                enableVibration(true)
            })
        nm.createNotificationChannel(
            NotificationChannel("service", "后台服务", NotificationManager.IMPORTANCE_MIN))
        startForeground(1, Notification.Builder(this, "service")
            .setContentTitle("跌倒警报服务运行中")
            .setContentText("报警推送通道连接中…")
            .setSmallIcon(android.R.drawable.ic_dialog_alert)
            .build())
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        if (!running) {
            running = true
            Thread { sseLoop() }.start()
        }
        return START_STICKY
    }

    private fun sseLoop() {
        while (running) {
            var conn: HttpURLConnection? = null
            try {
                MainActivity.setStatus("推送通道: 连接中…")
                conn = URL("${MainActivity.ntfyBase()}/${MainActivity.topic()}/sse")
                    .openConnection() as HttpURLConnection
                conn.connectTimeout = 15000
                conn.setRequestProperty("Accept", "text/event-stream")
                val reader = BufferedReader(InputStreamReader(conn.inputStream))
                MainActivity.setStatus("推送通道: 已连接 ✓")
                updateFgNotification("报警推送通道已连接")
                val data = StringBuilder()
                while (running && !reconnectRequested) {
                    val line = reader.readLine() ?: break
                    if (line.isEmpty()) {
                        if (data.isNotEmpty()) {
                            handleEvent(data.toString())
                            data.setLength(0)
                        }
                    } else if (line.startsWith("data:")) {
                        data.append(line.substring(5).trim())
                    }
                }
            } catch (e: Exception) {
                MainActivity.setStatus("推送通道: 断开（5 秒后重连）")
            } finally {
                reconnectRequested = false
                conn?.disconnect()
            }
            if (running) Thread.sleep(5000)
        }
    }

    private fun handleEvent(data: String) {
        try {
            val j = JSONObject(data)
            if (j.optString("event") != "message") return
            val priority = j.optInt("priority", 3)
            if (priority < 4) return          // 只处理高优先级(报警)消息
            val detail = j.optString("message", "检测到疑似摔倒")
            val attach = j.optJSONObject("attachment")?.optString("url")
            triggerAlert(detail, attach)
        } catch (_: Exception) {
        }
    }

    private fun triggerAlert(detail: String, imageUrl: String?) {
        // 唤醒屏幕
        val pm = getSystemService(Context.POWER_SERVICE) as PowerManager
        @Suppress("DEPRECATION")
        val wl = pm.newWakeLock(
            PowerManager.FULL_WAKE_LOCK or PowerManager.ACQUIRE_CAUSES_WAKEUP, "fallalert:wake")
        wl.acquire(10_000)

        startAlarm(this)

        // 全屏通知(后台/锁屏也能弹出警报页)
        val intent = Intent(this, AlertActivity::class.java).apply {
            putExtra("detail", detail)
            putExtra("image", imageUrl)
            addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        }
        val pi = PendingIntent.getActivity(this, 0, intent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE)
        val n = Notification.Builder(this, "fall_alerts")
            .setContentTitle("⚠ 检测到疑似摔倒！")
            .setContentText(detail)
            .setSmallIcon(android.R.drawable.ic_dialog_alert)
            .setFullScreenIntent(pi, true)
            .setContentIntent(pi)
            .setAutoCancel(true)
            .build()
        val nm = getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        nm.notify(2, n)

        // 前台时直接拉起页面
        startActivity(intent)
    }

    private fun updateFgNotification(text: String) {
        val n = Notification.Builder(this, "service")
            .setContentTitle("跌倒警报服务运行中")
            .setContentText(text)
            .setSmallIcon(android.R.drawable.ic_dialog_alert)
            .build()
        val nm = getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        nm.notify(1, n)
    }

    override fun onDestroy() {
        running = false
        stopAlarm()
        super.onDestroy()
    }
}
