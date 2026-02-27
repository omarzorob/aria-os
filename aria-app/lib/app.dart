import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:provider/provider.dart';
import 'screens/chat_screen.dart';
import 'screens/voice_screen.dart';
import 'screens/settings_screen.dart';
import 'services/aria_channel.dart';

// ─── App State ───────────────────────────────────────────────────────────────

class AriaState extends ChangeNotifier {
  final List<ChatMessage> messages = [];
  bool isTyping = false;
  bool voiceMode = false;
  VoiceState voiceState = VoiceState.idle;

  void addMessage(ChatMessage message) {
    messages.add(message);
    notifyListeners();
  }

  void setTyping(bool value) {
    isTyping = value;
    notifyListeners();
  }

  void setVoiceMode(bool value) {
    voiceMode = value;
    notifyListeners();
  }

  void setVoiceState(VoiceState state) {
    voiceState = state;
    notifyListeners();
  }

  Future<void> sendMessage(String text) async {
    if (text.trim().isEmpty) return;

    addMessage(ChatMessage(
      text: text,
      isUser: true,
      timestamp: DateTime.now(),
    ));
    setTyping(true);

    await AriaChannel.sendMessage(text);
  }

  void onReply(String reply) {
    setTyping(false);
    addMessage(ChatMessage(
      text: reply,
      isUser: false,
      timestamp: DateTime.now(),
    ));
  }
}

class ChatMessage {
  final String text;
  final bool isUser;
  final DateTime timestamp;

  const ChatMessage({
    required this.text,
    required this.isUser,
    required this.timestamp,
  });
}

enum VoiceState { idle, listening, thinking, speaking }

// ─── App Root ────────────────────────────────────────────────────────────────

class AriaApp extends StatelessWidget {
  const AriaApp({super.key});

  @override
  Widget build(BuildContext context) {
    return ChangeNotifierProvider(
      create: (_) => AriaState(),
      child: MaterialApp(
        title: 'Aria',
        debugShowCheckedModeBanner: false,
        theme: _buildTheme(),
        initialRoute: '/',
        routes: {
          '/': (ctx) => const ChatScreen(),
          '/voice': (ctx) => const VoiceScreen(),
          '/settings': (ctx) => const SettingsScreen(),
        },
      ),
    );
  }

  ThemeData _buildTheme() {
    const background = Color(0xFF0a0a0f);
    const surface = Color(0xFF111118);
    const accent = Color(0xFF00d4ff);
    const onSurface = Color(0xFFE8E8F0);

    return ThemeData(
      brightness: Brightness.dark,
      scaffoldBackgroundColor: background,
      colorScheme: const ColorScheme.dark(
        background: background,
        surface: surface,
        primary: accent,
        onBackground: onSurface,
        onSurface: onSurface,
      ),
      appBarTheme: AppBarTheme(
        backgroundColor: background,
        elevation: 0,
        titleTextStyle: GoogleFonts.inter(
          color: onSurface,
          fontSize: 18,
          fontWeight: FontWeight.w600,
          letterSpacing: 0.5,
        ),
        iconTheme: const IconThemeData(color: accent),
      ),
      textTheme: GoogleFonts.interTextTheme(
        ThemeData.dark().textTheme,
      ).apply(bodyColor: onSurface, displayColor: onSurface),
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: surface,
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(24),
          borderSide: BorderSide.none,
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(24),
          borderSide: const BorderSide(color: accent, width: 1.5),
        ),
        hintStyle: TextStyle(color: onSurface.withOpacity(0.4)),
        contentPadding: const EdgeInsets.symmetric(horizontal: 20, vertical: 14),
      ),
      iconTheme: const IconThemeData(color: accent),
      useMaterial3: true,
    );
  }
}
