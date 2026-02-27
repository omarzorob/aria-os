package ai.aria.os.tools

import android.bluetooth.BluetoothAdapter
import android.content.ContentResolver
import android.content.Context
import android.content.Intent
import android.media.AudioManager
import android.net.wifi.WifiManager
import android.provider.Settings
import android.util.Log
import ai.aria.os.tools.base.AriaTool

/**
 * SettingsTool — change device settings like brightness, volume, WiFi, Bluetooth, DND.
 */
class SettingsTool(private val context: Context) : AriaTool() {

    companion object {
        const val TAG = "SettingsTool"
    }

    private val audioManager: AudioManager =
        context.getSystemService(Context.AUDIO_SERVICE) as AudioManager

    override val description = "Change device settings. Supports: brightness, volume, wifi, bluetooth, " +
        "airplane_mode, flashlight, do_not_disturb, ringer_mode."

    override val inputSchema = mapOf(
        "type" to "object",
        "properties" to mapOf(
            "setting" to mapOf(
                "type" to "string",
                "enum" to listOf(
                    "brightness", "volume", "volume_media", "volume_ringer",
                    "wifi", "bluetooth", "airplane_mode",
                    "ringer_mode", "do_not_disturb", "open_settings"
                ),
                "description" to "Which setting to change"
            ),
            "value" to mapOf(
                "type" to "string",
                "description" to "New value. For toggles: 'on'/'off'. " +
                    "For brightness/volume: 0-100 (percent). For ringer_mode: 'normal'/'silent'/'vibrate'."
            )
        ),
        "required" to listOf("setting", "value")
    )

    override suspend fun execute(input: Map<String, Any>): String {
        val setting = input.getString("setting").lowercase()
        val value = input.getString("value").lowercase()

        return when (setting) {
            "brightness" -> setBrightness(value)
            "volume", "volume_media" -> setVolume(AudioManager.STREAM_MUSIC, value)
            "volume_ringer" -> setVolume(AudioManager.STREAM_RING, value)
            "wifi" -> setWifi(value)
            "bluetooth" -> setBluetooth(value)
            "airplane_mode" -> openAirplaneModeSettings()
            "ringer_mode" -> setRingerMode(value)
            "do_not_disturb" -> setDoNotDisturb(value)
            "open_settings" -> openSettings(value)
            else -> "Error: Unknown setting '$setting'"
        }
    }

    private fun setBrightness(value: String): String {
        // Check if we have WRITE_SETTINGS permission
        if (!Settings.System.canWrite(context)) {
            // Open settings to grant permission
            val intent = Intent(Settings.ACTION_MANAGE_WRITE_SETTINGS).apply {
                flags = Intent.FLAG_ACTIVITY_NEW_TASK
            }
            context.startActivity(intent)
            return "Please grant 'Modify system settings' permission for Aria, then try again."
        }

        val percent = value.replace("%", "").toIntOrNull()?.coerceIn(0, 100)
            ?: return "Error: Brightness value must be 0-100"

        val brightnessValue = (percent * 255 / 100)

        // Disable auto-brightness first
        Settings.System.putInt(
            context.contentResolver,
            Settings.System.SCREEN_BRIGHTNESS_MODE,
            Settings.System.SCREEN_BRIGHTNESS_MODE_MANUAL
        )
        Settings.System.putInt(
            context.contentResolver,
            Settings.System.SCREEN_BRIGHTNESS,
            brightnessValue
        )

        Log.i(TAG, "Set brightness to $percent% ($brightnessValue)")
        return "☀️ Brightness set to $percent%"
    }

    private fun setVolume(streamType: Int, value: String): String {
        val percent = value.replace("%", "").toIntOrNull()?.coerceIn(0, 100)
            ?: return "Error: Volume value must be 0-100"

        val maxVol = audioManager.getStreamMaxVolume(streamType)
        val targetVol = (percent * maxVol / 100)
        audioManager.setStreamVolume(streamType, targetVol, AudioManager.FLAG_SHOW_UI)

        val streamName = if (streamType == AudioManager.STREAM_MUSIC) "Media" else "Ringer"
        Log.i(TAG, "Set $streamName volume to $percent%")
        return "🔊 $streamName volume set to $percent%"
    }

    @Suppress("DEPRECATION")
    private fun setWifi(value: String): String {
        // Android 10+ doesn't allow apps to toggle WiFi directly
        // Open WiFi settings instead
        val intent = Intent(Settings.ACTION_WIFI_SETTINGS).apply {
            flags = Intent.FLAG_ACTIVITY_NEW_TASK
        }
        context.startActivity(intent)
        return "📶 Opening WiFi settings (Android 10+ requires manual toggle)"
    }

    @Suppress("DEPRECATION")
    private fun setBluetooth(value: String): String {
        val intent = Intent(Settings.ACTION_BLUETOOTH_SETTINGS).apply {
            flags = Intent.FLAG_ACTIVITY_NEW_TASK
        }
        context.startActivity(intent)
        return "🔵 Opening Bluetooth settings"
    }

    private fun openAirplaneModeSettings(): String {
        val intent = Intent(Settings.ACTION_AIRPLANE_MODE_SETTINGS).apply {
            flags = Intent.FLAG_ACTIVITY_NEW_TASK
        }
        context.startActivity(intent)
        return "✈️ Opening Airplane Mode settings"
    }

    private fun setRingerMode(value: String): String {
        val mode = when (value) {
            "silent" -> {
                audioManager.ringerMode = AudioManager.RINGER_MODE_SILENT
                "Silent"
            }
            "vibrate" -> {
                audioManager.ringerMode = AudioManager.RINGER_MODE_VIBRATE
                "Vibrate"
            }
            "normal", "on", "ring" -> {
                audioManager.ringerMode = AudioManager.RINGER_MODE_NORMAL
                "Normal"
            }
            else -> return "Error: ringer_mode value must be 'normal', 'silent', or 'vibrate'"
        }
        return "🔔 Ringer mode set to $mode"
    }

    private fun setDoNotDisturb(value: String): String {
        val intent = Intent(Settings.ACTION_NOTIFICATION_POLICY_ACCESS_SETTINGS).apply {
            flags = Intent.FLAG_ACTIVITY_NEW_TASK
        }
        context.startActivity(intent)
        return "🔕 Opening Do Not Disturb settings"
    }

    private fun openSettings(value: String): String {
        val action = when (value) {
            "accessibility" -> Settings.ACTION_ACCESSIBILITY_SETTINGS
            "app", "apps" -> Settings.ACTION_APPLICATION_SETTINGS
            "battery" -> Settings.ACTION_BATTERY_SAVER_SETTINGS
            "display" -> Settings.ACTION_DISPLAY_SETTINGS
            "sound" -> Settings.ACTION_SOUND_SETTINGS
            "location" -> Settings.ACTION_LOCATION_SOURCE_SETTINGS
            else -> Settings.ACTION_SETTINGS
        }
        val intent = Intent(action).apply {
            flags = Intent.FLAG_ACTIVITY_NEW_TASK
        }
        context.startActivity(intent)
        return "⚙️ Opened ${value.ifBlank { "Android" }} settings"
    }
}
