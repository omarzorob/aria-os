import 'dart:async';
import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:provider/provider.dart';
import '../app.dart';
import '../services/aria_channel.dart';
import '../widgets/message_bubble.dart';
import '../widgets/task_progress.dart';

class ChatScreen extends StatefulWidget {
  const ChatScreen({super.key});

  @override
  State<ChatScreen> createState() => _ChatScreenState();
}

class _ChatScreenState extends State<ChatScreen> {
  final TextEditingController _controller = TextEditingController();
  final ScrollController _scrollController = ScrollController();
  StreamSubscription<String>? _replySub;

  @override
  void initState() {
    super.initState();
    _subscribeToReplies();
  }

  void _subscribeToReplies() {
    _replySub = AriaChannel.replies.listen((reply) {
      if (mounted) {
        context.read<AriaState>().onReply(reply);
        _scrollToBottom();
      }
    });
  }

  void _scrollToBottom() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (_scrollController.hasClients) {
        _scrollController.animateTo(
          _scrollController.position.maxScrollExtent,
          duration: const Duration(milliseconds: 300),
          curve: Curves.easeOut,
        );
      }
    });
  }

  Future<void> _send() async {
    final text = _controller.text.trim();
    if (text.isEmpty) return;
    _controller.clear();
    await context.read<AriaState>().sendMessage(text);
    _scrollToBottom();
  }

  @override
  void dispose() {
    _replySub?.cancel();
    _controller.dispose();
    _scrollController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final state = context.watch<AriaState>();
    final theme = Theme.of(context);

    return Scaffold(
      backgroundColor: theme.scaffoldBackgroundColor,
      appBar: AppBar(
        title: Row(
          children: [
            Container(
              width: 8,
              height: 8,
              decoration: const BoxDecoration(
                color: Color(0xFF00d4ff),
                shape: BoxShape.circle,
              ),
            ).animate(onPlay: (c) => c.repeat()).shimmer(
              duration: 2.seconds,
              color: const Color(0xFF00d4ff),
            ),
            const SizedBox(width: 10),
            const Text('Aria'),
          ],
        ),
        actions: [
          IconButton(
            icon: const Icon(Icons.mic_rounded),
            tooltip: 'Voice mode',
            onPressed: () => Navigator.pushNamed(context, '/voice'),
          ),
          IconButton(
            icon: const Icon(Icons.settings_outlined),
            tooltip: 'Settings',
            onPressed: () => Navigator.pushNamed(context, '/settings'),
          ),
        ],
      ),
      body: Column(
        children: [
          // Message list
          Expanded(
            child: state.messages.isEmpty
                ? _buildEmptyState(theme)
                : ListView.builder(
                    controller: _scrollController,
                    padding: const EdgeInsets.symmetric(vertical: 12),
                    itemCount: state.messages.length + (state.isTyping ? 1 : 0),
                    itemBuilder: (ctx, index) {
                      if (index == state.messages.length && state.isTyping) {
                        return const TypingIndicator();
                      }
                      final msg = state.messages[index];
                      return MessageBubble(
                        message: msg,
                        isFirst: index == 0 ||
                            state.messages[index - 1].isUser != msg.isUser,
                      );
                    },
                  ),
          ),

          // Divider
          Divider(
            height: 1,
            color: Colors.white.withOpacity(0.06),
          ),

          // Input bar
          _buildInputBar(theme),
        ],
      ),
    );
  }

  Widget _buildEmptyState(ThemeData theme) {
    return Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(
            Icons.auto_awesome_rounded,
            size: 48,
            color: const Color(0xFF00d4ff).withOpacity(0.5),
          )
              .animate(onPlay: (c) => c.repeat())
              .shimmer(duration: 3.seconds, color: const Color(0xFF00d4ff)),
          const SizedBox(height: 16),
          Text(
            'Hey, I\'m Aria',
            style: theme.textTheme.headlineSmall?.copyWith(
              color: Colors.white70,
              fontWeight: FontWeight.w600,
            ),
          ),
          const SizedBox(height: 8),
          Text(
            'Ask me anything or tell me what to do.',
            style: theme.textTheme.bodyMedium?.copyWith(
              color: Colors.white38,
            ),
          ),
          const SizedBox(height: 32),
          _buildSuggestion('What\'s the weather today?'),
          _buildSuggestion('Send a text to Mom'),
          _buildSuggestion('Open Spotify'),
        ],
      ),
    );
  }

  Widget _buildSuggestion(String text) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4),
      child: GestureDetector(
        onTap: () {
          _controller.text = text;
          _send();
        },
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
          decoration: BoxDecoration(
            border: Border.all(color: const Color(0xFF00d4ff).withOpacity(0.3)),
            borderRadius: BorderRadius.circular(20),
          ),
          child: Text(
            text,
            style: const TextStyle(color: Color(0xFF00d4ff), fontSize: 14),
          ),
        ),
      ),
    );
  }

  Widget _buildInputBar(ThemeData theme) {
    return SafeArea(
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
        child: Row(
          children: [
            // Text field
            Expanded(
              child: TextField(
                controller: _controller,
                style: const TextStyle(color: Colors.white, fontSize: 15),
                decoration: const InputDecoration(
                  hintText: 'Ask Aria anything...',
                ),
                textInputAction: TextInputAction.send,
                onSubmitted: (_) => _send(),
                maxLines: null,
                keyboardType: TextInputType.multiline,
              ),
            ),
            const SizedBox(width: 8),

            // Mic button
            _ActionButton(
              icon: Icons.mic_rounded,
              onTap: () => Navigator.pushNamed(context, '/voice'),
            ),
            const SizedBox(width: 6),

            // Send button
            _ActionButton(
              icon: Icons.send_rounded,
              filled: true,
              onTap: _send,
            ),
          ],
        ),
      ),
    );
  }
}

class _ActionButton extends StatelessWidget {
  final IconData icon;
  final VoidCallback onTap;
  final bool filled;

  const _ActionButton({
    required this.icon,
    required this.onTap,
    this.filled = false,
  });

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        width: 44,
        height: 44,
        decoration: BoxDecoration(
          color: filled
              ? const Color(0xFF00d4ff)
              : const Color(0xFF00d4ff).withOpacity(0.12),
          borderRadius: BorderRadius.circular(22),
        ),
        child: Icon(
          icon,
          color: filled ? Colors.black : const Color(0xFF00d4ff),
          size: 20,
        ),
      ),
    );
  }
}

class TypingIndicator extends StatelessWidget {
  const TypingIndicator({super.key});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(left: 16, top: 4, bottom: 4),
      child: Row(
        children: [
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
            decoration: BoxDecoration(
              color: const Color(0xFF111118),
              borderRadius: BorderRadius.circular(18),
            ),
            child: Row(
              mainAxisSize: MainAxisSize.min,
              children: List.generate(3, (i) {
                return Container(
                  margin: const EdgeInsets.symmetric(horizontal: 2),
                  width: 6,
                  height: 6,
                  decoration: const BoxDecoration(
                    color: Color(0xFF00d4ff),
                    shape: BoxShape.circle,
                  ),
                )
                    .animate(onPlay: (c) => c.repeat())
                    .slideY(
                      begin: 0,
                      end: -0.8,
                      duration: 500.ms,
                      delay: (i * 150).ms,
                      curve: Curves.easeInOut,
                    )
                    .then()
                    .slideY(begin: -0.8, end: 0, duration: 500.ms);
              }),
            ),
          ),
        ],
      ),
    );
  }
}
