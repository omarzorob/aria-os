package ai.aria.os.tools

import android.content.Context
import android.util.Log
import com.google.gson.JsonParser
import ai.aria.os.tools.base.AriaTool
import okhttp3.OkHttpClient
import okhttp3.Request
import java.net.URLEncoder

/**
 * WeatherTool — gets current weather and forecasts using Open-Meteo API (no API key needed).
 *
 * Step 1: Geocode location name → lat/lon via Open-Meteo's geocoding API
 * Step 2: Fetch weather data from Open-Meteo weather API
 */
class WeatherTool(private val context: Context) : AriaTool() {

    companion object {
        const val TAG = "WeatherTool"
        const val GEO_URL = "https://geocoding-api.open-meteo.com/v1/search"
        const val WEATHER_URL = "https://api.open-meteo.com/v1/forecast"
    }

    private val client = OkHttpClient()

    override val description = "Get current weather conditions and forecast for any location. " +
        "No API key required. Provides temperature, conditions, humidity, and wind."

    override val inputSchema = mapOf(
        "type" to "object",
        "properties" to mapOf(
            "location" to mapOf(
                "type" to "string",
                "description" to "City or location name (e.g., 'Chicago', 'New York', 'London, UK')"
            ),
            "days" to mapOf(
                "type" to "integer",
                "description" to "Number of forecast days (1-7, default: 1 for current only)",
                "default" to 1
            )
        ),
        "required" to listOf("location")
    )

    override suspend fun execute(input: Map<String, Any>): String {
        val location = input.getString("location")
        val days = input.getInt("days", 1).coerceIn(1, 7)

        if (location.isBlank()) return "Error: 'location' is required"

        // Step 1: Geocode
        val (lat, lon, resolvedName) = geocode(location)
            ?: return "Error: Could not find location '$location'. Try a major city name."

        // Step 2: Fetch weather
        return fetchWeather(lat, lon, resolvedName, days)
    }

    private fun geocode(location: String): Triple<Double, Double, String>? {
        val encodedLocation = URLEncoder.encode(location, "UTF-8")
        val url = "$GEO_URL?name=$encodedLocation&count=1&language=en&format=json"

        return try {
            val response = client.newCall(Request.Builder().url(url).build()).execute()
            val body = response.body?.string() ?: return null
            val json = JsonParser.parseString(body).asJsonObject
            val results = json.getAsJsonArray("results") ?: return null
            if (results.size() == 0) return null

            val result = results[0].asJsonObject
            val lat = result.get("latitude").asDouble
            val lon = result.get("longitude").asDouble
            val name = result.get("name")?.asString ?: location
            val country = result.get("country")?.asString ?: ""
            Triple(lat, lon, "$name, $country".trimEnd(',', ' '))
        } catch (e: Exception) {
            Log.e(TAG, "Geocoding failed", e)
            null
        }
    }

    private fun fetchWeather(lat: Double, lon: Double, locationName: String, days: Int): String {
        val url = "$WEATHER_URL?latitude=$lat&longitude=$lon" +
            "&current=temperature_2m,relative_humidity_2m,apparent_temperature,precipitation,weather_code,wind_speed_10m,wind_direction_10m" +
            "&daily=weather_code,temperature_2m_max,temperature_2m_min,precipitation_sum" +
            "&temperature_unit=fahrenheit&wind_speed_unit=mph&precipitation_unit=inch" +
            "&timezone=auto&forecast_days=$days"

        return try {
            val response = client.newCall(Request.Builder().url(url).build()).execute()
            val body = response.body?.string() ?: return "Error: Empty weather response"
            val json = JsonParser.parseString(body).asJsonObject

            val current = json.getAsJsonObject("current")
            val temp = current.get("temperature_2m")?.asDouble?.let { "%.0f°F".format(it) } ?: "N/A"
            val feelsLike = current.get("apparent_temperature")?.asDouble?.let { "%.0f°F".format(it) } ?: "N/A"
            val humidity = current.get("relative_humidity_2m")?.asInt ?: 0
            val windSpeed = current.get("wind_speed_10m")?.asDouble?.let { "%.0f mph".format(it) } ?: "N/A"
            val weatherCode = current.get("weather_code")?.asInt ?: 0
            val conditions = weatherCodeToDescription(weatherCode)
            val precipitation = current.get("precipitation")?.asDouble ?: 0.0

            val sb = StringBuilder()
            sb.append("🌤️ Weather in $locationName:\n")
            sb.append("• Conditions: $conditions\n")
            sb.append("• Temperature: $temp (feels like $feelsLike)\n")
            sb.append("• Humidity: $humidity%\n")
            sb.append("• Wind: $windSpeed\n")
            if (precipitation > 0) sb.append("• Precipitation: ${"%.2f".format(precipitation)} in\n")

            if (days > 1) {
                val daily = json.getAsJsonObject("daily")
                val dates = daily.getAsJsonArray("time")
                val maxTemps = daily.getAsJsonArray("temperature_2m_max")
                val minTemps = daily.getAsJsonArray("temperature_2m_min")
                val codes = daily.getAsJsonArray("weather_code")

                sb.append("\n📅 Forecast:\n")
                for (i in 1 until minOf(days, dates.size())) {
                    val date = dates[i].asString
                    val max = maxTemps[i].asDouble
                    val min = minTemps[i].asDouble
                    val code = codes[i].asInt
                    sb.append("• $date: ${weatherCodeToDescription(code)}, High ${"%.0f".format(max)}°F / Low ${"%.0f".format(min)}°F\n")
                }
            }

            sb.toString().trimEnd()
        } catch (e: Exception) {
            Log.e(TAG, "Weather fetch failed", e)
            "Error fetching weather: ${e.message}"
        }
    }

    private fun weatherCodeToDescription(code: Int): String = when (code) {
        0 -> "Clear sky"
        1 -> "Mainly clear"
        2 -> "Partly cloudy"
        3 -> "Overcast"
        45, 48 -> "Foggy"
        51, 53, 55 -> "Drizzle"
        61, 63, 65 -> "Rain"
        66, 67 -> "Freezing rain"
        71, 73, 75 -> "Snow"
        77 -> "Snow grains"
        80, 81, 82 -> "Rain showers"
        85, 86 -> "Snow showers"
        95 -> "Thunderstorm"
        96, 99 -> "Thunderstorm with hail"
        else -> "Unknown ($code)"
    }
}
