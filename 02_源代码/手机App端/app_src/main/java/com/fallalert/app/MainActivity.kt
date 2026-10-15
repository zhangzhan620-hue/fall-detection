package com.fallalert.app

import android.app.Activity
import android.content.Context
import android.content.Intent
import android.content.SharedPreferences
import android.graphics.Color
import android.os.Build
import android.os.Bundle
import android.view.Gravity
import android.widget.Button
import android.widget.EditText
import android.widget.LinearLayout
import android.widget.TextView

class MainActivity : Activity() {

    companion object {
        lateinit var prefs: SharedPreferences
        fun videoUrl() = prefs.getString("video_url", "http://192.168.1.4:8080/video.mjpg")!!
        fun topic() = prefs.getString("topic", "fangshuai-fall-a1b2c3d4e5f6")!!
        fun ntfyBase() = prefs.getString("ntfy_base", "https://ntfy.sh")!!
        fun emergencyPhone() = prefs.getString("emergency_phone", "")!!
        var connStatus: TextView? = null
        fun setStatus(s: String) {
            connStatus?.post { connStatus?.text = s }
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        prefs = getSharedPreferences("fall_alert", Context.MODE_PRIVATE)

        if (Build.VERSION.SDK_INT >= 33) {
            requestPermissions(arrayOf(android.Manifest.permission.POST_NOTIFICATIONS,
                android.Manifest.permission.CALL_PHONE), 1)
        } else if (Build.VERSION.SDK_INT >= 23) {
            requestPermissions(arrayOf(android.Manifest.permission.CALL_PHONE), 1)
        }
        startAlertService()

        val root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(40, 60, 40, 40)
        }
        root.addView(TextView(this).apply {
            text = "跌倒警报接收端"
            textSize = 24f
            setTextColor(Color.BLACK)
            gravity = Gravity.CENTER
        })
        val status = TextView(this).apply {
            text = "推送通道: 连接中..."
            textSize = 14f
            setPadding(0, 24, 0, 24)
        }
        connStatus = status
        root.addView(status)

        fun field(label: String, key: String, def: String): EditText {
            root.addView(TextView(this).apply { text = label; setTextColor(Color.DKGRAY) })
            val et = EditText(this).apply { setText(prefs.getString(key, def)) }
            root.addView(et)
            return et
        }
        val etVideo = field("监控视频流地址（已默认填好，一般不用改）", "video_url", "http://192.168.1.4:8080/video.mjpg")
        val etTopic = field("报警频道（与电脑端 alert_push.py 的 TOPIC 一致）", "topic", "fangshuai-fall-a1b2c3d4e5f6")
        val etPhone = field("紧急联系电话（摔倒时本机自动拨打，可留空）", "emergency_phone", "")

        root.addView(Button(this).apply {
            text = "保存设置并重连"
            setOnClickListener {
                prefs.edit()
                    .putString("video_url", etVideo.text.toString().trim())
                    .putString("topic", etTopic.text.toString().trim())
                    .putString("emergency_phone", etPhone.text.toString().trim())
                    .apply()
                AlertService.reconnectRequested = true
                startAlertService()
                setStatus("已保存，重连中...")
            }
        })
        root.addView(Button(this).apply {
            text = "打开实时监控画面"
            setOnClickListener { startActivity(Intent(this@MainActivity, MonitorActivity::class.java)) }
        })
        root.addView(Button(this).apply {
            text = "测试警报（响铃 + 弹窗）"
            setOnClickListener {
                startActivity(Intent(this@MainActivity, AlertActivity::class.java).apply {
                    putExtra("detail", "这是一条本机测试警报")
                })
                AlertService.startAlarm(this@MainActivity)
            }
        })
        root.addView(TextView(this).apply {
            text = "\n24小时在线（只靠正规机制，逐一检查）：\n" +
                    "· 本App使用前台服务常驻（通知栏可见，可随时关）\n" +
                    "· 系统设置→应用→本App→电池→选「不限制」\n" +
                    "· 系统设置→应用→本App→自启动→允许\n" +
                    "· 通知权限保持开启\n" +
                    "· 即使本App被清理，微信PushPlus推送仍可送达（兜底通道）"
            textSize = 13f
            setTextColor(Color.GRAY)
            setPadding(0, 40, 0, 0)
        })
        setContentView(root)
    }

    private fun startAlertService() {
        val i = Intent(this, AlertService::class.java)
        if (Build.VERSION.SDK_INT >= 26) startForegroundService(i) else startService(i)
    }

    override fun onDestroy() {
        connStatus = null
        super.onDestroy()
    }
}
