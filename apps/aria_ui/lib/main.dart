/// P1-29: Aria OS Chat UI
///
/// Minimal Flutter chat interface for Aria OS.
/// Dark theme. Shows conversation history with user/agent bubbles.
/// Text input at bottom. Sends messages to Aria agent via HTTP (localhost:8765).
/// Clean, minimal design inspired by Signal + ChatGPT.

import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'voice_mode.dart';
import 'task_progress.dart';

const String kAgentUrl = 'http://localhost:8765';
const String kAgentSendEndpoint = '/chat';

void main() {
  runApp(const AriaApp());
}

class AriaApp extends StatelessWidget {
  const AriaApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Aria',
      debugShowCheckedModeBanner: false,
      theme: _buildDarkTheme(),
      home: const ChatScreen(),
    );
  }

  ThemeData _buildDarkTheme() {
    const bg = Color(0xFF0D0D0D);
    const surface = Color(0xFF1A1A1A);
    const primary = Color(0xFF6C63FF);
    const textPrimary = Color(0xFFEEEEEE);
    const textSecondary = Color(0xFF888888);

    return ThemeData(
      brightness: Brightness.dark,
      scaffoldBackgroundColor: bg,
      colorScheme: const ColorScheme.dark(
        primary: primary,
        surface: surface,
        onPrimary: Colors.white,
        onSurface: textPrimary,
      ),
      fontFamily: 'Inter',
      appBarTheme: const AppBarTheme(
        backgroundColor: bg,
        elevation: 0,
        titleTextStyle: TextStyle(
          color: textPrimary,
          fontSize: 17,
          fontWeight: FontWeight.w600,
          letterSpacing: 0.3,
        ),
        iconTheme: IconThemeData(color: textSecondary),
      ),
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: surface,
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(24),
          borderSide: BorderSide.none,
        ),
        contentPadding: const EdgeInsets.symmetric(horizontal: 18, vertical: 12),
        hintStyle: const TextStyle(color: textSecondary, fontSize: 15),
      ),
    );
  }
}

// ---------------------------------------------------------------------------
// Data model
// ---------------------------------------------------------------------------

enum MessageRole { user, assistant, system }

class ChatMessage {
  final String id;
  final MessageRole role;
  final String content;
  final DateTime timestamp;
  final bool isLoading;

  const ChatMessage({
    required this.id,
    required this.role,
    required this.content,
    required this.timestamp,
    this.isLoading = false,
  });

  ChatMessage copyWith({String? content, bool? isLoading}) => ChatMessage(
        id: id,
        role: role,
        content: content ?? this.content,
        timestamp: timestamp,
        isLoading: isLoading ?? this.isLoading,
      );
}

// ---------------------------------------------------------------------------
// Chat Screen
// ---------------------------------------------------------------------------

class ChatScreen extends StatefulWidget {
  const ChatScreen({super.key});

  @override
  State<ChatScreen> createState() => _ChatScreenState();
}

class _ChatScreenState extends State<ChatScreen>
    with SingleTickerProviderStateMixin {
  final List<ChatMessage> _messages = [];
  final TextEditingController _inputController = TextEditingController();
  final ScrollController _scrollController = ScrollController();
  final FocusNode _inputFocusNode = FocusNode();

  bool _isLoading = false;
  bool _showVoiceMode = false;
  bool _showTaskPanel = false;
  String _currentTask = '';
  List<TaskStep> _taskSteps = [];

  @override
  void initState() {
    super.initState();
    _addSystemWelcome();
  }

  @override
  void dispose() {
    _inputController.dispose();
    _scrollController.dispose();
    _inputFocusNode.dispose();
    super.dispose();
  }

  void _addSystemWelcome() {
    _messages.add(ChatMessage(
      id: 'welcome',
      role: MessageRole.assistant,
      content: 'Hi! I\'m Aria. What can I do for you?',
      timestamp: DateTime.now(),
    ));
  }

  // ---------------------------------------------------------------------------
  // Messaging
  // ---------------------------------------------------------------------------

  Future<void> _sendMessage(String text) async {
    if (text.trim().isEmpty) return;

    final userMessage = ChatMessage(
      id: DateTime.now().millisecondsSinceEpoch.toString(),
      role: MessageRole.user,
      content: text.trim(),
      timestamp: DateTime.now(),
    );

    final loadingId = '${userMessage.id}_loading';
    final loadingMessage = ChatMessage(
      id: loadingId,
      role: MessageRole.assistant,
      content: '',
      timestamp: DateTime.now(),
      isLoading: true,
    );

    setState(() {
      _messages.add(userMessage);
      _messages.add(loadingMessage);
      _isLoading = true;
    });

    _inputController.clear();
    _scrollToBottom();

    try {
      final response = await _callAgent(text.trim());
      setState(() {
        final idx = _messages.indexWhere((m) => m.id == loadingId);
        if (idx >= 0) {
          _messages[idx] = _messages[idx].copyWith(
            content: response,
            isLoading: false,
          );
        }
      });
    } catch (e) {
      setState(() {
        final idx = _messages.indexWhere((m) => m.id == loadingId);
        if (idx >= 0) {
          _messages[idx] = _messages[idx].copyWith(
            content: 'Sorry, I couldn\'t connect to the agent. '
                'Make sure Aria is running on port 8765.',
            isLoading: false,
          );
        }
      });
    } finally {
      setState(() => _isLoading = false);
      _scrollToBottom();
    }
  }

  Future<String> _callAgent(String message) async {
    final uri = Uri.parse('$kAgentUrl$kAgentSendEndpoint');
    final response = await http
        .post(
          uri,
          headers: {'Content-Type': 'application/json'},
          body: jsonEncode({'message': message}),
        )
        .timeout(const Duration(seconds: 30));

    if (response.statusCode == 200) {
      final data = jsonDecode(response.body) as Map<String, dynamic>;
      return data['response'] as String? ?? 'Done.';
    } else {
      throw Exception('Agent returned ${response.statusCode}');
    }
  }

  void _scrollToBottom() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (_scrollController.hasClients) {
        _scrollController.animateTo(
          _scrollController.position.maxScrollExtent,
          duration: const Duration(milliseconds: 250),
          curve: Curves.easeOut,
        );
      }
    });
  }

  // ---------------------------------------------------------------------------
  // Build
  // ---------------------------------------------------------------------------

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: _buildAppBar(),
      body: Stack(
        children: [
          Column(
            children: [
              Expanded(child: _buildMessageList()),
              if (_showTaskPanel)
                TaskProgressPanel(
                  currentTask: _currentTask,
                  steps: _taskSteps,
                  onDismiss: () => setState(() => _showTaskPanel = false),
                ),
              _buildInputBar(),
            ],
          ),
          if (_showVoiceMode)
            VoiceModeOverlay(
              onClose: () => setState(() => _showVoiceMode = false),
              onTranscript: (text) {
                setState(() => _showVoiceMode = false);
                _sendMessage(text);
              },
            ),
        ],
      ),
    );
  }

  PreferredSizeWidget _buildAppBar() {
    return AppBar(
      title: Row(
        children: [
          Container(
            width: 32,
            height: 32,
            decoration: const BoxDecoration(
              color: Color(0xFF6C63FF),
              shape: BoxShape.circle,
            ),
            child: const Center(
              child: Text('A',
                  style: TextStyle(
                      color: Colors.white,
                      fontSize: 16,
                      fontWeight: FontWeight.bold)),
            ),
          ),
          const SizedBox(width: 10),
          const Text('Aria'),
          const SizedBox(width: 6),
          Container(
            width: 8,
            height: 8,
            decoration: const BoxDecoration(
              color: Color(0xFF4CAF50),
              shape: BoxShape.circle,
            ),
          ),
        ],
      ),
      actions: [
        IconButton(
          icon: const Icon(Icons.task_alt_rounded, size: 20),
          onPressed: () => setState(() => _showTaskPanel = !_showTaskPanel),
          tooltip: 'Task progress',
        ),
        IconButton(
          icon: const Icon(Icons.more_horiz_rounded, size: 20),
          onPressed: _showOptionsMenu,
          tooltip: 'Options',
        ),
      ],
    );
  }

  Widget _buildMessageList() {
    return ListView.builder(
      controller: _scrollController,
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
      itemCount: _messages.length,
      itemBuilder: (context, index) {
        return _MessageBubble(message: _messages[index]);
      },
    );
  }

  Widget _buildInputBar() {
    return SafeArea(
      child: Container(
        color: const Color(0xFF0D0D0D),
        padding: const EdgeInsets.fromLTRB(12, 8, 12, 12),
        child: Row(
          children: [
            Expanded(
              child: TextField(
                controller: _inputController,
                focusNode: _inputFocusNode,
                style: const TextStyle(color: Color(0xFFEEEEEE), fontSize: 15),
                maxLines: 5,
                minLines: 1,
                textCapitalization: TextCapitalization.sentences,
                decoration: const InputDecoration(
                  hintText: 'Message Aria...',
                ),
                onSubmitted: _isLoading ? null : _sendMessage,
              ),
            ),
            const SizedBox(width: 8),
            _inputController.text.trim().isEmpty && !_isLoading
                ? _MicButton(
                    onTap: () => setState(() => _showVoiceMode = true),
                  )
                : _SendButton(
                    isLoading: _isLoading,
                    onTap: () => _sendMessage(_inputController.text),
                  ),
          ],
        ),
      ),
    );
  }

  void _showOptionsMenu() {
    showModalBottomSheet(
      context: context,
      backgroundColor: const Color(0xFF1A1A1A),
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(16)),
      ),
      builder: (_) => Padding(
        padding: const EdgeInsets.symmetric(vertical: 16, horizontal: 24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            ListTile(
              leading: const Icon(Icons.delete_outline_rounded,
                  color: Color(0xFF888888)),
              title: const Text('Clear conversation',
                  style: TextStyle(color: Color(0xFFEEEEEE))),
              onTap: () {
                Navigator.pop(context);
                setState(() {
                  _messages.clear();
                  _addSystemWelcome();
                });
              },
            ),
          ],
        ),
      ),
    );
  }
}

// ---------------------------------------------------------------------------
// Message Bubble Widget
// ---------------------------------------------------------------------------

class _MessageBubble extends StatelessWidget {
  final ChatMessage message;

  const _MessageBubble({required this.message});

  @override
  Widget build(BuildContext context) {
    final isUser = message.role == MessageRole.user;

    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: Row(
        mainAxisAlignment:
            isUser ? MainAxisAlignment.end : MainAxisAlignment.start,
        crossAxisAlignment: CrossAxisAlignment.end,
        children: [
          if (!isUser) _buildAvatar(),
          if (!isUser) const SizedBox(width: 8),
          Flexible(
            child: Container(
              constraints: BoxConstraints(
                maxWidth: MediaQuery.of(context).size.width * 0.75,
              ),
              decoration: BoxDecoration(
                color: isUser
                    ? const Color(0xFF6C63FF)
                    : const Color(0xFF1E1E1E),
                borderRadius: BorderRadius.only(
                  topLeft: const Radius.circular(18),
                  topRight: const Radius.circular(18),
                  bottomLeft: Radius.circular(isUser ? 18 : 4),
                  bottomRight: Radius.circular(isUser ? 4 : 18),
                ),
              ),
              padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
              child: message.isLoading
                  ? const _TypingIndicator()
                  : Text(
                      message.content,
                      style: TextStyle(
                        color: isUser
                            ? Colors.white
                            : const Color(0xFFEEEEEE),
                        fontSize: 15,
                        height: 1.45,
                      ),
                    ),
            ),
          ),
          if (isUser) const SizedBox(width: 8),
        ],
      ),
    );
  }

  Widget _buildAvatar() {
    return Container(
      width: 28,
      height: 28,
      decoration: const BoxDecoration(
        color: Color(0xFF6C63FF),
        shape: BoxShape.circle,
      ),
      child: const Center(
        child: Text('A',
            style: TextStyle(color: Colors.white, fontSize: 13,
                fontWeight: FontWeight.bold)),
      ),
    );
  }
}

// ---------------------------------------------------------------------------
// Typing Indicator
// ---------------------------------------------------------------------------

class _TypingIndicator extends StatefulWidget {
  const _TypingIndicator();

  @override
  State<_TypingIndicator> createState() => _TypingIndicatorState();
}

class _TypingIndicatorState extends State<_TypingIndicator>
    with SingleTickerProviderStateMixin {
  late final AnimationController _controller;

  @override
  void initState() {
    super.initState();
    _controller = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 900),
    )..repeat();
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      height: 18,
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: List.generate(3, (i) {
          return AnimatedBuilder(
            animation: _controller,
            builder: (_, __) {
              final phase = (_controller.value - i * 0.15).clamp(0.0, 1.0);
              final opacity = (0.3 + 0.7 * (1 - (phase - 0.5).abs() * 2)).clamp(0.3, 1.0);
              return Padding(
                padding: const EdgeInsets.symmetric(horizontal: 2),
                child: Opacity(
                  opacity: opacity,
                  child: const CircleAvatar(
                    radius: 4,
                    backgroundColor: Color(0xFF888888),
                  ),
                ),
              );
            },
          );
        }),
      ),
    );
  }
}

// ---------------------------------------------------------------------------
// Button widgets
// ---------------------------------------------------------------------------

class _SendButton extends StatelessWidget {
  final bool isLoading;
  final VoidCallback onTap;

  const _SendButton({required this.isLoading, required this.onTap});

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: isLoading ? null : onTap,
      child: Container(
        width: 44,
        height: 44,
        decoration: BoxDecoration(
          color: isLoading
              ? const Color(0xFF3A3A3A)
              : const Color(0xFF6C63FF),
          shape: BoxShape.circle,
        ),
        child: isLoading
            ? const Padding(
                padding: EdgeInsets.all(12),
                child: CircularProgressIndicator(
                  strokeWidth: 2,
                  color: Color(0xFF888888),
                ),
              )
            : const Icon(Icons.arrow_upward_rounded,
                color: Colors.white, size: 20),
      ),
    );
  }
}

class _MicButton extends StatelessWidget {
  final VoidCallback onTap;

  const _MicButton({required this.onTap});

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        width: 44,
        height: 44,
        decoration: const BoxDecoration(
          color: Color(0xFF1E1E1E),
          shape: BoxShape.circle,
        ),
        child: const Icon(Icons.mic_rounded,
            color: Color(0xFF888888), size: 22),
      ),
    );
  }
}
