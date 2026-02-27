package ai.aria.os

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.os.Build
import io.flutter.embedding.android.FlutterActivity
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.plugin.common.EventChannel
import io.flutter.plugin.common.MethodChannel
import ai.aria.os.agent.AriaAgentService

class MainActivity : FlutterActivity() {

    private val METHOD_CHANNEL = "ai.aria.os/agent"
    private val EVENT_CHANNEL = "ai.aria.os/replies"

    private var replyEventSink: EventChannel.EventSink? = null

    private val replyReceiver = object : BroadcastReceiver() {
        override fun onReceive(context: Context, intent: Intent) {
            val text = intent.getStringExtra("text") ?: return
            runOnUiThread {
                replyEventSink?.success(text)
            }
        }
    }

    override fun configureFlutterEngine(flutterEngine: FlutterEngine) {
        super.configureFlutterEngine(flutterEngine)

        // MethodChannel: Flutter → Kotlin commands
        MethodChannel(
            flutterEngine.dartExecutor.binaryMessenger,
            METHOD_CHANNEL
        ).setMethodCallHandler { call, result ->
            when (call.method) {
                "sendMessage" -> {
                    val message = call.argument<String>("message") ?: ""
                    val intent = Intent(this, AriaAgentService::class.java).apply {
                        action = AriaAgentService.ACTION_SEND_MESSAGE
                        putExtra(AriaAgentService.EXTRA_MESSAGE, message)
                    }
                    startService(intent)
                    result.success(null)
                }
                "startListening" -> {
                    val intent = Intent(this, AriaAgentService::class.java).apply {
                        action = AriaAgentService.ACTION_START_LISTENING
                    }
                    startService(intent)
                    result.success(null)
                }
                "stopListening" -> {
                    val intent = Intent(this, AriaAgentService::class.java).apply {
                        action = AriaAgentService.ACTION_STOP_LISTENING
                    }
                    startService(intent)
                    result.success(null)
                }
                "getStatus" -> {
                    result.success(mapOf("running" to true, "version" to "0.1.0"))
                }
                else -> result.notImplemented()
            }
        }

        // EventChannel: Kotlin → Flutter replies
        EventChannel(
            flutterEngine.dartExecutor.binaryMessenger,
            EVENT_CHANNEL
        ).setStreamHandler(object : EventChannel.StreamHandler {
            override fun onListen(arguments: Any?, events: EventChannel.EventSink?) {
                replyEventSink = events
            }
            override fun onCancel(arguments: Any?) {
                replyEventSink = null
            }
        })

        // Start Aria agent service
        val serviceIntent = Intent(this, AriaAgentService::class.java)
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            startForegroundService(serviceIntent)
        } else {
            startService(serviceIntent)
        }
    }

    override fun onResume() {
        super.onResume()
        val filter = IntentFilter(AriaAgentService.ACTION_REPLY)
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            registerReceiver(replyReceiver, filter, Context.RECEIVER_NOT_EXPORTED)
        } else {
            registerReceiver(replyReceiver, filter)
        }
    }

    override fun onPause() {
        super.onPause()
        try {
            unregisterReceiver(replyReceiver)
        } catch (e: IllegalArgumentException) {
            // Not registered
        }
    }
}
