package ai.aria.accessibility

import android.os.Bundle
import android.util.Log
import android.view.accessibility.AccessibilityNodeInfo
import com.google.gson.Gson
import com.google.gson.JsonObject
import com.google.gson.JsonParser

/**
 * CommandHandler processes JSON-RPC command strings and returns JSON response strings.
 * All interaction with the AccessibilityService goes through this class.
 */
class CommandHandler(private val service: AriaAccessibilityService) {

    companion object {
        const val TAG = "AriaCommandHandler"
    }

    private val gson = Gson()

    /**
     * Handle a raw JSON command string and return a JSON response string.
     */
    fun handle(commandJson: String): String {
        return try {
            val obj = JsonParser.parseString(commandJson).asJsonObject
            val method = obj.get("method")?.asString ?: return error("Missing 'method' field")
            val params = if (obj.has("params") && !obj.get("params").isJsonNull)
                obj.getAsJsonObject("params")
            else
                JsonObject()

            dispatch(method, params)
        } catch (e: Exception) {
            Log.e(TAG, "Error handling command: $commandJson", e)
            error("Parse error: ${e.message}")
        }
    }

    private fun dispatch(method: String, params: JsonObject): String {
        return try {
            when (method) {
                "ping" -> success(mapOf("status" to "ok", "service" to "aria-accessibility"))

                "get_screen_elements" -> {
                    val root = service.getRootNode()
                    val elements = ElementFinder.findAllElements(root)
                    success(elements)
                }

                "get_screen_text" -> {
                    val root = service.getRootNode()
                    val text = ElementFinder.getScreenText(root)
                    success(mapOf("text" to text))
                }

                "get_focused_app" -> {
                    val root = service.getRootNode()
                    val packageName = root?.packageName?.toString() ?: ""
                    success(mapOf("package" to packageName))
                }

                "find_element_by_text" -> {
                    val text = params.get("text")?.asString ?: return error("Missing param: text")
                    val root = service.getRootNode()
                    val elements = ElementFinder.findByText(root, text)
                    success(elements)
                }

                "find_element_by_id" -> {
                    val id = params.get("id")?.asString ?: return error("Missing param: id")
                    val root = service.getRootNode()
                    val elements = ElementFinder.findById(root, id)
                    success(elements)
                }

                "tap_element" -> {
                    val nodeId = params.get("nodeId")?.asInt ?: return error("Missing param: nodeId")
                    val root = service.getRootNode()
                    val node = ElementFinder.findNodeByHash(root, nodeId)
                        ?: return error("Node not found with id: $nodeId")

                    val clicked = node.performAction(AccessibilityNodeInfo.ACTION_CLICK)
                    success(mapOf("clicked" to clicked))
                }

                "tap_coords" -> {
                    val x = params.get("x")?.asFloat ?: return error("Missing param: x")
                    val y = params.get("y")?.asFloat ?: return error("Missing param: y")
                    service.performTap(x, y)
                    success(mapOf("tapped" to true, "x" to x, "y" to y))
                }

                "swipe" -> {
                    val x1 = params.get("x1")?.asFloat ?: return error("Missing param: x1")
                    val y1 = params.get("y1")?.asFloat ?: return error("Missing param: y1")
                    val x2 = params.get("x2")?.asFloat ?: return error("Missing param: x2")
                    val y2 = params.get("y2")?.asFloat ?: return error("Missing param: y2")
                    val duration = params.get("duration")?.asLong ?: 300L
                    service.performSwipe(x1, y1, x2, y2, duration)
                    success(mapOf("swiped" to true))
                }

                "type_text" -> {
                    val text = params.get("text")?.asString ?: return error("Missing param: text")
                    val root = service.getRootNode()
                    val focusedNode = root?.findFocus(AccessibilityNodeInfo.FOCUS_INPUT)

                    if (focusedNode != null) {
                        val args = Bundle()
                        args.putString(
                            AccessibilityNodeInfo.ACTION_ARGUMENT_SET_TEXT_CHARSEQUENCE,
                            text
                        )
                        val done = focusedNode.performAction(AccessibilityNodeInfo.ACTION_SET_TEXT, args)
                        success(mapOf("typed" to done, "text" to text))
                    } else {
                        error("No focused input field found")
                    }
                }

                "press_back" -> {
                    service.performBack()
                    success(mapOf("action" to "back"))
                }

                "press_home" -> {
                    service.performHome()
                    success(mapOf("action" to "home"))
                }

                "press_recents" -> {
                    service.performRecents()
                    success(mapOf("action" to "recents"))
                }

                "press_notifications" -> {
                    service.performNotifications()
                    success(mapOf("action" to "notifications"))
                }

                "scroll_forward" -> {
                    val nodeId = params.get("nodeId")?.asInt
                    val root = service.getRootNode()
                    val node = if (nodeId != null) {
                        ElementFinder.findNodeByHash(root, nodeId)
                    } else {
                        root
                    }
                    val scrolled = node?.performAction(AccessibilityNodeInfo.ACTION_SCROLL_FORWARD) ?: false
                    success(mapOf("scrolled" to scrolled, "direction" to "forward"))
                }

                "scroll_backward" -> {
                    val nodeId = params.get("nodeId")?.asInt
                    val root = service.getRootNode()
                    val node = if (nodeId != null) {
                        ElementFinder.findNodeByHash(root, nodeId)
                    } else {
                        root
                    }
                    val scrolled = node?.performAction(AccessibilityNodeInfo.ACTION_SCROLL_BACKWARD) ?: false
                    success(mapOf("scrolled" to scrolled, "direction" to "backward"))
                }

                else -> error("Unknown method: $method")
            }
        } catch (e: Exception) {
            Log.e(TAG, "Error dispatching method: $method", e)
            error("Execution error: ${e.message}")
        }
    }

    private fun success(result: Any): String {
        val response = mapOf("success" to true, "result" to result)
        return gson.toJson(response)
    }

    private fun error(message: String): String {
        val response = mapOf("success" to false, "error" to message)
        return gson.toJson(response)
    }
}
