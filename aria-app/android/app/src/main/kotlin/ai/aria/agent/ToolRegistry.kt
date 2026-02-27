package ai.aria.os.agent

import android.content.Context
import ai.aria.os.tools.*
import ai.aria.os.tools.base.AriaTool

class ToolRegistry(private val context: Context) {

    private val tools: Map<String, AriaTool> = mapOf(
        "send_sms" to SmsTool(context),
        "make_call" to PhoneTool(context),
        "search_contacts" to ContactsTool(context),
        "get_calendar_events" to CalendarTool(context),
        "launch_app" to AppLauncherTool(context),
        "open_browser" to BrowserTool(context),
        "get_weather" to WeatherTool(context),
        "get_directions" to MapsTool(context),
        "control_music" to MusicTool(context),
        "change_setting" to SettingsTool(context),
        "get_notifications" to NotificationsTool(context),
        "web_search" to WebSearchTool(context),
    )

    fun getTool(name: String): AriaTool? = tools[name]

    fun getToolSchemas(): List<Map<String, Any>> = tools.map { (name, tool) ->
        mapOf(
            "name" to name,
            "description" to tool.description,
            "input_schema" to tool.inputSchema
        )
    }

    fun listTools(): List<String> = tools.keys.toList()
}
