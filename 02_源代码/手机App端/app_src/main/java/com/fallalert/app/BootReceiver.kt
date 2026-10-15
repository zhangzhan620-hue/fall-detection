package com.fallalert.app

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.os.Build

/** 开机自启报警服务 */
class BootReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        if (intent.action == Intent.ACTION_BOOT_COMPLETED) {
            val i = Intent(context, AlertService::class.java)
            if (Build.VERSION.SDK_INT >= 26) context.startForegroundService(i)
            else context.startService(i)
        }
    }
}
