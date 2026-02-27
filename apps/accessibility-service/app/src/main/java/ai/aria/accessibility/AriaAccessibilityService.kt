package ai.aria.accessibility

import android.accessibilityservice.AccessibilityService
import android.accessibilityservice.GestureDescription
import android.graphics.Path
import android.graphics.Rect
import android.util.Log
import android.view.accessibility.AccessibilityEvent
import android.view.accessibility.AccessibilityNodeInfo
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch

class AriaAccessibilityService : AccessibilityService() {

    companion object {
        const val TAG = "AriaService"
        var instance: AriaAccessibilityService? = null
    }

    private lateinit var socketServer: SocketServer
    private val scope = CoroutineScope(Dispatchers.IO)

    override fun onServiceConnected() {
        super.onServiceConnected()
        instance = this
        Log.i(TAG, "Aria Accessibility Service connected")

        // Start JSON-RPC socket server
        socketServer = SocketServer(this)
        scope.launch {
            socketServer.start()
        }
    }

    override fun onAccessibilityEvent(event: AccessibilityEvent?) {
        // Events are available when needed
    }

    override fun onInterrupt() {
        Log.w(TAG, "Aria Accessibility Service interrupted")
    }

    override fun onDestroy() {
        super.onDestroy()
        instance = null
        socketServer.stop()
    }

    // === Public API for CommandHandler ===

    fun getRootNode(): AccessibilityNodeInfo? {
        return rootInActiveWindow
    }

    fun performTap(x: Float, y: Float) {
        val path = Path().apply { moveTo(x, y) }
        val stroke = GestureDescription.StrokeDescription(path, 0, 50)
        val gesture = GestureDescription.Builder().addStroke(stroke).build()
        dispatchGesture(gesture, null, null)
    }

    fun performSwipe(x1: Float, y1: Float, x2: Float, y2: Float, duration: Long = 300) {
        val path = Path().apply {
            moveTo(x1, y1)
            lineTo(x2, y2)
        }
        val stroke = GestureDescription.StrokeDescription(path, 0, duration)
        val gesture = GestureDescription.Builder().addStroke(stroke).build()
        dispatchGesture(gesture, null, null)
    }

    fun performBack() = performGlobalAction(GLOBAL_ACTION_BACK)
    fun performHome() = performGlobalAction(GLOBAL_ACTION_HOME)
    fun performRecents() = performGlobalAction(GLOBAL_ACTION_RECENTS)
    fun performNotifications() = performGlobalAction(GLOBAL_ACTION_NOTIFICATIONS)
}
