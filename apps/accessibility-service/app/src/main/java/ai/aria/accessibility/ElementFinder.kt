package ai.aria.accessibility

import android.graphics.Rect
import android.view.accessibility.AccessibilityNodeInfo

data class UIElement(
    val id: String,                       // viewIdResourceName
    val text: String,                     // text content
    val contentDescription: String,
    val className: String,                // e.g. android.widget.Button
    val bounds: Map<String, Int>,         // left, top, right, bottom
    val isClickable: Boolean,
    val isEditable: Boolean,
    val isScrollable: Boolean,
    val isEnabled: Boolean,
    val childCount: Int,
    val nodeHashCode: Int                 // used as temp id for tapping
)

object ElementFinder {

    /**
     * Recursively traverse the accessibility node tree starting from [root]
     * and return a flat list of [UIElement] data objects.
     */
    fun findAllElements(root: AccessibilityNodeInfo?): List<UIElement> {
        val results = mutableListOf<UIElement>()
        if (root == null) return results
        traverse(root, results)
        return results
    }

    /**
     * Find elements whose text or content description contains [text] (case-insensitive).
     */
    fun findByText(root: AccessibilityNodeInfo?, text: String): List<UIElement> {
        return findAllElements(root).filter { element ->
            element.text.contains(text, ignoreCase = true) ||
            element.contentDescription.contains(text, ignoreCase = true)
        }
    }

    /**
     * Find elements whose viewIdResourceName matches [viewId] (exact match or contains).
     */
    fun findById(root: AccessibilityNodeInfo?, viewId: String): List<UIElement> {
        return findAllElements(root).filter { element ->
            element.id == viewId || element.id.contains(viewId)
        }
    }

    /**
     * Find a node by its hashCode for tapping. Returns the matching AccessibilityNodeInfo.
     * Note: caller is responsible for recycling the node after use.
     */
    fun findNodeByHash(root: AccessibilityNodeInfo?, hashCode: Int): AccessibilityNodeInfo? {
        if (root == null) return null
        if (root.hashCode() == hashCode) return root
        for (i in 0 until root.childCount) {
            val child = root.getChild(i) ?: continue
            val found = findNodeByHash(child, hashCode)
            if (found != null) return found
        }
        return null
    }

    /**
     * Collect all visible text from the node tree as a single string.
     */
    fun getScreenText(root: AccessibilityNodeInfo?): String {
        val sb = StringBuilder()
        collectText(root, sb)
        return sb.toString().trim()
    }

    private fun traverse(node: AccessibilityNodeInfo, results: MutableList<UIElement>) {
        val rect = Rect()
        node.getBoundsInScreen(rect)

        val element = UIElement(
            id = node.viewIdResourceName ?: "",
            text = node.text?.toString() ?: "",
            contentDescription = node.contentDescription?.toString() ?: "",
            className = node.className?.toString() ?: "",
            bounds = mapOf(
                "left" to rect.left,
                "top" to rect.top,
                "right" to rect.right,
                "bottom" to rect.bottom
            ),
            isClickable = node.isClickable,
            isEditable = node.isEditable,
            isScrollable = node.isScrollable,
            isEnabled = node.isEnabled,
            childCount = node.childCount,
            nodeHashCode = node.hashCode()
        )

        results.add(element)

        for (i in 0 until node.childCount) {
            val child = node.getChild(i) ?: continue
            traverse(child, results)
        }
    }

    private fun collectText(node: AccessibilityNodeInfo?, sb: StringBuilder) {
        if (node == null) return

        val text = node.text?.toString()
        val desc = node.contentDescription?.toString()

        if (!text.isNullOrBlank()) {
            sb.append(text).append("\n")
        } else if (!desc.isNullOrBlank()) {
            sb.append(desc).append("\n")
        }

        for (i in 0 until node.childCount) {
            collectText(node.getChild(i), sb)
        }
    }
}
