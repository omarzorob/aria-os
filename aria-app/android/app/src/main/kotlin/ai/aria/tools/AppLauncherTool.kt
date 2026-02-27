package ai.aria.os.tools

import android.content.Context
import android.content.Intent
import android.content.pm.ResolveInfo
import android.util.Log
import ai.aria.os.tools.base.AriaTool

/**
 * AppLauncherTool — launches installed apps by name or package name.
 */
class AppLauncherTool(private val context: Context) : AriaTool() {

    companion object {
        const val TAG = "AppLauncherTool"
    }

    override val description = "Launch an installed app by name (e.g., 'Spotify', 'Gmail', 'Maps') " +
        "or by package name (e.g., 'com.spotify.music')."

    override val inputSchema = mapOf(
        "type" to "object",
        "properties" to mapOf(
            "app_name" to mapOf(
                "type" to "string",
                "description" to "App name (e.g., 'Spotify', 'Gmail') or package name (e.g., 'com.spotify.music')"
            )
        ),
        "required" to listOf("app_name")
    )

    override suspend fun execute(input: Map<String, Any>): String {
        val appName = input.getString("app_name")
        if (appName.isBlank()) return "Error: 'app_name' is required"

        val pm = context.packageManager

        // Try direct package name first
        pm.getLaunchIntentForPackage(appName)?.let { intent ->
            intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
            context.startActivity(intent)
            return "✅ Launched $appName"
        }

        // Search by label name
        val launchIntent = Intent(Intent.ACTION_MAIN).apply {
            addCategory(Intent.CATEGORY_LAUNCHER)
        }
        val apps: List<ResolveInfo> = pm.queryIntentActivities(launchIntent, 0)

        val query = appName.lowercase()
        val match = apps.firstOrNull { info ->
            val label = info.loadLabel(pm).toString().lowercase()
            label.contains(query) || query.contains(label)
        }

        if (match != null) {
            val packageName = match.activityInfo.packageName
            val launchable = pm.getLaunchIntentForPackage(packageName)
            if (launchable != null) {
                launchable.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                context.startActivity(launchable)
                val label = match.loadLabel(pm).toString()
                Log.i(TAG, "Launched '$label' ($packageName)")
                return "✅ Launched $label"
            }
        }

        // Suggest close matches
        val suggestions = apps
            .filter { it.loadLabel(pm).toString().lowercase().contains(query.take(3)) }
            .take(3)
            .map { it.loadLabel(pm).toString() }

        return if (suggestions.isNotEmpty()) {
            "App '$appName' not found. Did you mean: ${suggestions.joinToString(", ")}?"
        } else {
            "App '$appName' not found. Make sure it's installed on the device."
        }
    }
}
