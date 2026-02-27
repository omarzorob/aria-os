package ai.aria.os.accessibility

import android.accessibilityservice.AccessibilityService
import android.accessibilityservice.GestureDescription
import android.content.ClipData
import android.content.ClipboardManager
import android.content.Context
import android.graphics.Path
import android.graphics.Rect
import android.os.Bundle
import android.util.Log
import android.view.accessibility.AccessibilityEvent
import android.view.accessibility.AccessibilityNodeInfo

/**
 * AriaAccessibilityService — gives Aria the ability to read and control any app on the device.
 *
 * Capabilities:
 * - Read all text visible on screen
 * - Find UI elements by text or content description
 * - Tap, swipe, type text
 * - Navigate: back, home, recents
 * - Get current app package name
 */
class AriaAccessibilityService : AccessibilityService() {

    companion object {
        const val TAG = "AriaA11y"

        /** Singleton instance — set when the service connects */
        @Volatile
        var instance: AriaAccessibilityService? = null

        fun isConnected(): Boolean = instance != null
    }

    // ─── Lifecycle ─────────────────────────────────────────────────────────────

    override fun onServiceConnected() {
        instance = this
        Log.i(TAG, "Aria Accessibility Service connected")
    }

    override fun onAccessibilityEvent(event: AccessibilityEvent?) {
        // Could be used in Phase 2 to reactively monitor screen changes
    }

    override fun onInterrupt() {
        Log.w(TAG, "Aria Accessibility Service interrupted")
    }

    override fun onDestroy() {
        super.onDestroy()
        instance = null
        Log.i(TAG, "Aria Accessibility Service destroyed")
    }

    // ─── Screen Reading ─────────────────────────────────────────────────────────

    /**
     * Get all visible text on the current screen.
     */
    fun getScreenText(): String {
        return rootInActiveWindow?.let { root ->
            val sb = StringBuilder()
            extractText(root, sb)
            root.recycle()
            sb.toString().trim()
        } ?: ""
    }

    /**
     * Get a structured snapshot of the screen: text + content descriptions.
     */
    fun getScreenSnapshot(): List<Map<String, String>> {
        val result = mutableListOf<Map<String, String>>()
        rootInActiveWindow?.let { root ->
            collectNodes(root, result)
            root.recycle()
        }
        return result
    }

    /**
     * Find a node by its visible text (case-insensitive, partial match).
     */
    fun findNodeByText(text: String): AccessibilityNodeInfo? {
        val root = rootInActiveWindow ?: return null
        return root.findAccessibilityNodeInfosByText(text).firstOrNull()
    }

    /**
     * Find a node by content description.
     */
    fun findNodeByDescription(description: String): AccessibilityNodeInfo? {
        val root = rootInActiveWindow ?: return null
        return findNodeRecursive(root) { node ->
            node.contentDescription?.toString()?.contains(description, ignoreCase = true) == true
        }
    }

    private fun extractText(node: AccessibilityNodeInfo?, sb: StringBuilder) {
        node ?: return
        node.text?.let { if (it.isNotBlank()) sb.append(it).append(" ") }
        node.contentDescription?.let {
            if (it.isNotBlank() && node.text == null) sb.append(it).append(" ")
        }
        for (i in 0 until node.childCount) {
            extractText(node.getChild(i), sb)
        }
    }

    private fun collectNodes(node: AccessibilityNodeInfo?, result: MutableList<Map<String, String>>) {
        node ?: return
        val text = node.text?.toString()
        val desc = node.contentDescription?.toString()
        if (!text.isNullOrBlank() || !desc.isNullOrBlank()) {
            result.add(mapOf(
                "text" to (text ?: ""),
                "description" to (desc ?: ""),
                "class" to (node.className?.toString() ?: ""),
                "clickable" to node.isClickable.toString()
            ))
        }
        for (i in 0 until node.childCount) {
            collectNodes(node.getChild(i), result)
        }
    }

    private fun findNodeRecursive(
        node: AccessibilityNodeInfo,
        predicate: (AccessibilityNodeInfo) -> Boolean
    ): AccessibilityNodeInfo? {
        if (predicate(node)) return node
        for (i in 0 until node.childCount) {
            val child = node.getChild(i) ?: continue
            val found = findNodeRecursive(child, predicate)
            if (found != null) return found
        }
        return null
    }

    // ─── Actions ─────────────────────────────────────────────────────────────

    /**
     * Tap at a specific screen coordinate.
     */
    fun tapAt(x: Float, y: Float) {
        val path = Path().apply { moveTo(x, y) }
        val gesture = GestureDescription.Builder()
            .addStroke(GestureDescription.StrokeDescription(path, 0, 50))
            .build()
        dispatchGesture(gesture, null, null)
        Log.d(TAG, "Tapped at ($x, $y)")
    }

    /**
     * Tap a node found by text.
     */
    fun tapNodeWithText(text: String): Boolean {
        val node = findNodeByText(text) ?: return false
        val bounds = Rect()
        node.getBoundsInScreen(bounds)
        val cx = bounds.centerX().toFloat()
        val cy = bounds.centerY().toFloat()
        tapAt(cx, cy)
        node.recycle()
        return true
    }

    /**
     * Perform click action on a node by text (uses AccessibilityAction, not gesture).
     */
    fun clickNodeWithText(text: String): Boolean {
        val node = findNodeByText(text) ?: return false
        val result = node.performAction(AccessibilityNodeInfo.ACTION_CLICK)
        node.recycle()
        return result
    }

    /**
     * Type text into the currently focused field.
     */
    fun typeText(text: String): Boolean {
        val root = rootInActiveWindow ?: return false
        val focused = findNodeRecursive(root) { it.isFocused && it.isEditable }
        if (focused != null) {
            val args = Bundle()
            args.putCharSequence(AccessibilityNodeInfo.ACTION_ARGUMENT_SET_TEXT_CHARSEQUENCE, text)
            val result = focused.performAction(AccessibilityNodeInfo.ACTION_SET_TEXT, args)
            focused.recycle()
            return result
        }
        // Fallback: put text in clipboard and paste
        val clipboard = getSystemService(Context.CLIPBOARD_SERVICE) as ClipboardManager
        clipboard.setPrimaryClip(ClipData.newPlainText("aria_text", text))
        return focused?.performAction(AccessibilityNodeInfo.ACTION_PASTE) ?: false
    }

    /**
     * Swipe from one point to another.
     */
    fun swipe(x1: Float, y1: Float, x2: Float, y2: Float, durationMs: Long = 300) {
        val path = Path().apply {
            moveTo(x1, y1)
            lineTo(x2, y2)
        }
        val gesture = GestureDescription.Builder()
            .addStroke(GestureDescription.StrokeDescription(path, 0, durationMs))
            .build()
        dispatchGesture(gesture, null, null)
        Log.d(TAG, "Swiped ($x1,$y1) → ($x2,$y2)")
    }

    /**
     * Scroll up by swiping up in the center of the screen.
     */
    fun scrollUp() {
        swipe(500f, 1200f, 500f, 400f)
    }

    /**
     * Scroll down by swiping down in the center of the screen.
     */
    fun scrollDown() {
        swipe(500f, 400f, 500f, 1200f)
    }

    // ─── Navigation ──────────────────────────────────────────────────────────

    fun pressBack(): Boolean = performGlobalAction(GLOBAL_ACTION_BACK)
    fun pressHome(): Boolean = performGlobalAction(GLOBAL_ACTION_HOME)
    fun pressRecents(): Boolean = performGlobalAction(GLOBAL_ACTION_RECENTS)
    fun pressNotifications(): Boolean = performGlobalAction(GLOBAL_ACTION_NOTIFICATIONS)

    /**
     * Get the package name of the currently active app.
     */
    fun getCurrentApp(): String = rootInActiveWindow?.packageName?.toString() ?: ""

    /**
     * Get the title of the currently active window.
     */
    fun getCurrentWindowTitle(): String {
        return windows?.firstOrNull { it.isActive }?.title?.toString() ?: ""
    }
}
