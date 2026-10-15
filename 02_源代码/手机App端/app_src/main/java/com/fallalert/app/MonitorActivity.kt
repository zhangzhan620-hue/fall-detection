package com.fallalert.app

import android.app.Activity
import android.graphics.BitmapFactory
import android.graphics.Color
import android.os.Bundle
import android.view.ViewGroup
import android.widget.FrameLayout
import android.widget.ImageView
import android.widget.TextView
import java.io.ByteArrayOutputStream
import java.net.HttpURLConnection
import java.net.URL

/** MJPEG 实时监控画面: 扫描 JPEG 帧头帧尾(FF D8 / FF D9)逐帧解码 */
class MonitorActivity : Activity() {

    @Volatile private var running = false
    private var conn: HttpURLConnection? = null
    private lateinit var status: TextView
    private lateinit var img: ImageView

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val root = FrameLayout(this).apply { setBackgroundColor(Color.BLACK) }
        img = ImageView(this).apply { scaleType = ImageView.ScaleType.FIT_CENTER }
        root.addView(img, FrameLayout.LayoutParams(-1, -1))
        status = TextView(this).apply {
            setTextColor(Color.GREEN)
            textSize = 14f
            setPadding(20, 20, 20, 20)
        }
        root.addView(status)
        setContentView(root)
    }

    override fun onResume() {
        super.onResume()
        running = true
        Thread { streamLoop() }.start()
    }

    private fun streamLoop() {
        while (running) {
            try {
                setStatus("连接监控: ${MainActivity.videoUrl()}")
                conn = URL(MainActivity.videoUrl()).openConnection() as HttpURLConnection
                conn!!.connectTimeout = 10000
                val input = conn!!.inputStream
                setStatus("监控已连接 ✓")
                val chunk = ByteArray(16384)
                var cur = ByteArrayOutputStream()
                var started = false
                var prev = 0
                while (running) {
                    val n = input.read(chunk)
                    if (n < 0) break
                    var i = 0
                    while (i < n) {
                        val b = chunk[i].toInt() and 0xFF
                        if (!started) {
                            if (prev == 0xFF && b == 0xD8) {
                                cur = ByteArrayOutputStream()
                                cur.write(0xFF); cur.write(0xD8)
                                started = true
                            }
                        } else {
                            cur.write(b)
                            if (prev == 0xFF && b == 0xD9) {
                                val bytes = cur.toByteArray()
                                val bmp = BitmapFactory.decodeByteArray(bytes, 0, bytes.size)
                                if (bmp != null) {
                                    runOnUiThread {
                                        if (running) img.setImageBitmap(bmp)
                                    }
                                }
                                started = false
                                cur = ByteArrayOutputStream()
                            }
                        }
                        prev = b
                        i++
                    }
                }
            } catch (e: Exception) {
                setStatus("监控断开（3 秒后重连）: ${e.message}")
            } finally {
                conn?.disconnect()
            }
            if (running) Thread.sleep(3000)
        }
    }

    private fun setStatus(s: String) = runOnUiThread { status.text = s }

    override fun onPause() {
        running = false
        conn?.disconnect()
        super.onPause()
    }
}
