package ai.aria.os

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.os.Build
import android.util.Log
import ai.aria.os.agent.AriaAgentService

/**
 * BootReceiver — automatically starts AriaAgentService when the device boots.
 *
 * Requires: RECEIVE_BOOT_COMPLETED permission in AndroidManifest.xml
 */
class BootReceiver : BroadcastReceiver() {

    companion object {
        const val TAG = "BootReceiver"
    }

    override fun onReceive(context: Context, intent: Intent) {
        val action = intent.action
        if (action == Intent.ACTION_BOOT_COMPLETED || action == "android.intent.action.QUICKBOOT_POWERON") {
            Log.i(TAG, "Boot completed — starting Aria Agent Service")

            val serviceIntent = Intent(context, AriaAgentService::class.java)
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                context.startForegroundService(serviceIntent)
            } else {
                context.startService(serviceIntent)
            }
        }
    }
}
