package ai.aria.accessibility

import android.util.Log
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import java.io.BufferedReader
import java.io.InputStreamReader
import java.io.PrintWriter
import java.net.ServerSocket
import java.net.Socket
import java.net.SocketException

/**
 * JSON-RPC socket server listening on port 7765.
 *
 * Protocol:
 * - Each command is a single line of JSON terminated by '\n'
 * - Each response is a single line of JSON terminated by '\n'
 * - Multiple commands can be sent on the same connection
 * - Connection is kept alive until client disconnects
 *
 * Request format:  {"method": "ping", "params": {}}
 * Response format: {"success": true, "result": ...}
 *                  {"success": false, "error": "..."}
 */
class SocketServer(private val service: AriaAccessibilityService) {

    companion object {
        const val TAG = "AriaSocketServer"
        const val PORT = 7765
    }

    private var serverSocket: ServerSocket? = null
    private val commandHandler = CommandHandler(service)
    private val scope = CoroutineScope(Dispatchers.IO)

    /**
     * Start accepting client connections. Blocks until stop() is called.
     * Each client connection is handled in its own coroutine.
     */
    fun start() {
        try {
            serverSocket = ServerSocket(PORT)
            Log.i(TAG, "Aria JSON-RPC server started on port $PORT")

            while (!serverSocket!!.isClosed) {
                try {
                    val clientSocket = serverSocket!!.accept()
                    Log.d(TAG, "Client connected: ${clientSocket.inetAddress.hostAddress}")
                    scope.launch {
                        handleClient(clientSocket)
                    }
                } catch (e: SocketException) {
                    if (serverSocket?.isClosed == true) {
                        Log.i(TAG, "Server socket closed, stopping accept loop")
                        break
                    } else {
                        Log.e(TAG, "Socket error accepting connection", e)
                    }
                }
            }
        } catch (e: Exception) {
            Log.e(TAG, "Failed to start server on port $PORT", e)
        }
    }

    /**
     * Handle a single client connection: read lines of JSON, dispatch each, write response.
     */
    private fun handleClient(clientSocket: Socket) {
        try {
            val reader = BufferedReader(InputStreamReader(clientSocket.getInputStream(), Charsets.UTF_8))
            val writer = PrintWriter(clientSocket.getOutputStream(), true, Charsets.UTF_8)

            clientSocket.use {
                var line: String?
                while (reader.readLine().also { line = it } != null) {
                    val commandJson = line!!.trim()
                    if (commandJson.isEmpty()) continue

                    Log.d(TAG, "Received command: $commandJson")
                    val response = commandHandler.handle(commandJson)
                    Log.d(TAG, "Sending response: $response")
                    writer.println(response)
                }
            }
        } catch (e: SocketException) {
            Log.d(TAG, "Client disconnected: ${e.message}")
        } catch (e: Exception) {
            Log.e(TAG, "Error handling client", e)
        } finally {
            if (!clientSocket.isClosed) {
                try { clientSocket.close() } catch (_: Exception) {}
            }
        }
    }

    /**
     * Stop the server and close the server socket.
     */
    fun stop() {
        try {
            serverSocket?.close()
            serverSocket = null
            Log.i(TAG, "Aria JSON-RPC server stopped")
        } catch (e: Exception) {
            Log.e(TAG, "Error stopping server", e)
        }
    }
}
