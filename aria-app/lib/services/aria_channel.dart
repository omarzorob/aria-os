import 'package:flutter/services.dart';

/// AriaChannel — Dart-side bridge to the Kotlin AriaAgentService.
///
/// Uses:
/// - MethodChannel for commands (Flutter → Kotlin)
/// - EventChannel for replies (Kotlin → Flutter)
class AriaChannel {
  static const _methodChannel = MethodChannel('ai.aria.os/agent');
  static const _eventChannel = EventChannel('ai.aria.os/replies');

  // Stream of reply texts from Aria
  static Stream<String> get replies {
    return _eventChannel
        .receiveBroadcastStream()
        .map((event) => event.toString());
  }

  /// Send a text message to AriaAgentService.
  static Future<void> sendMessage(String message) async {
    await _methodChannel.invokeMethod('sendMessage', {'message': message});
  }

  /// Start voice listening mode.
  static Future<void> startListening() async {
    await _methodChannel.invokeMethod('startListening');
  }

  /// Stop voice listening.
  static Future<void> stopListening() async {
    await _methodChannel.invokeMethod('stopListening');
  }

  /// Open Android Accessibility Settings.
  static Future<void> openAccessibilitySettings() async {
    await _methodChannel.invokeMethod('getStatus'); // triggers the settings open
    // Direct settings open is done via platform intent
    const platform = MethodChannel('ai.aria.os/agent');
    try {
      await platform.invokeMethod('openAccessibilitySettings');
    } catch (_) {
      // If not implemented, ignore — user can navigate manually
    }
  }

  /// Get current service status.
  static Future<Map<String, dynamic>> getStatus() async {
    final result = await _methodChannel.invokeMethod<Map>('getStatus');
    return Map<String, dynamic>.from(result ?? {});
  }
}
