package com.fallalert.app

import android.app.Activity
import android.content.Intent
import android.graphics.BitmapFactory
import android.graphics.Color
import android.net.Uri
import android.os.Bundle
import android.view.Gravity
import android.view.WindowManager
import android.widget.Button
import android.widget.ImageView
import android.widget.LinearLayout
import android.widget.TextView
import java.net.URL

class AlertActivity : Activity() {

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        // 锁屏上也能显示 + 点亮屏幕
        setShowWhenLocked(true)
        setTurnScreenOn(true)
        window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)

        val detail = intent.getStringExtra("detail") ?: "检测到疑似摔倒"
        val imageUrl = intent.getStringExtra("image")

        val root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setBackgroundColor(Color.rgb(183, 28, 28))   // 深红警报色
            setPadding(40, 80, 40, 40)
            gravity = Gravity.CENTER_HORIZONTAL
        }
        root.addView(TextView(this).apply {
            text = "⚠ 检测到疑似摔倒！"
            textSize = 30f
            setTextColor(Color.WHITE)
            gravity = Gravity.CENTER
        })
        root.addView(TextView(this).apply {
            text = detail
            textSize = 16f
            setTextColor(Color.WHITE)
            gravity = Gravity.CENTER
            setPadding(0, 20, 0, 20)
        })

        val img = ImageView(this).apply {
            adjustViewBounds = true
            scaleType = ImageView.ScaleType.FIT_CENTER
        }
        root.addView(img, LinearLayout.LayoutParams(-1, 0, 1f))

        if (imageUrl != null) {
            Thread {
                try {
                    val bytes = URL(imageUrl).readBytes()
                    val bmp = BitmapFactory.decodeByteArray(bytes, 0, bytes.size)
                    runOnUiThread { img.setImageBitmap(bmp) }
                } catch (_: Exception) {
                }
            }.start()
        }

        root.addView(Button(this).apply {
            text = "查看实时监控"
            setOnClickListener {
                AlertService.stopAlarm()
                startActivity(Intent(this@AlertActivity, MonitorActivity::class.java))
                finish()
            }
        })
        if (MainActivity.emergencyPhone().isNotEmpty()) {
            root.addView(Button(this).apply {
                text = "📞 立即呼叫家属（${MainActivity.emergencyPhone()}）"
                setOnClickListener { callFamily() }
            })
            // 警报弹出后 5 秒自动拨打电话
            img.postDelayed({ callFamily() }, 5000)
        }
        root.addView(Button(this).apply {
            text = "我已知晓（停止响铃）"
            setOnClickListener {
                AlertService.stopAlarm()
                finish()
            }
        })
        setContentView(root)
    }

    private fun callFamily() {
        val phone = MainActivity.emergencyPhone()
        if (phone.isEmpty()) return
        try {
            startActivity(Intent(Intent.ACTION_CALL, Uri.parse("tel:$phone")))
        } catch (e: SecurityException) {
            // 未授权电话权限则跳拨号盘
            startActivity(Intent(Intent.ACTION_DIAL, Uri.parse("tel:$phone")))
        }
    }

    override fun onDestroy() {
        AlertService.stopAlarm()
        super.onDestroy()
    }
}
