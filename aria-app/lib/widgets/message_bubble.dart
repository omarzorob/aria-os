import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:intl/intl.dart';
import '../app.dart';

class MessageBubble extends StatelessWidget {
  final ChatMessage message;
  final bool isFirst;

  const MessageBubble({
    super.key,
    required this.message,
    this.isFirst = false,
  });

  @override
  Widget build(BuildContext context) {
    final isUser = message.isUser;
    final timeStr = DateFormat('h:mm a').format(message.timestamp);

    return Padding(
      padding: EdgeInsets.only(
        left: isUser ? 60 : 12,
        right: isUser ? 12 : 60,
        top: isFirst ? 8 : 4,
        bottom: 4,
      ),
      child: Column(
        crossAxisAlignment:
            isUser ? CrossAxisAlignment.end : CrossAxisAlignment.start,
        children: [
          // Bubble
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
            decoration: BoxDecoration(
              color: isUser
                  ? const Color(0xFF00d4ff).withOpacity(0.15)
                  : const Color(0xFF111118),
              borderRadius: BorderRadius.only(
                topLeft: Radius.circular(isUser ? 18 : (isFirst ? 4 : 18)),
                topRight: Radius.circular(isUser ? (isFirst ? 4 : 18) : 18),
                bottomLeft: const Radius.circular(18),
                bottomRight: const Radius.circular(18),
              ),
              border: Border.all(
                color: isUser
                    ? const Color(0xFF00d4ff).withOpacity(0.25)
                    : Colors.white.withOpacity(0.06),
                width: 1,
              ),
            ),
            child: _MessageText(text: message.text, isUser: isUser),
          ),

          // Timestamp
          Padding(
            padding: const EdgeInsets.only(top: 3, left: 4, right: 4),
            child: Text(
              timeStr,
              style: const TextStyle(color: Colors.white24, fontSize: 11),
            ),
          ),
        ],
      ),
    )
        .animate()
        .slideY(
          begin: 0.2,
          end: 0,
          duration: 250.ms,
          curve: Curves.easeOut,
        )
        .fadeIn(duration: 250.ms);
  }
}

/// Renders message text with basic markdown-like formatting.
class _MessageText extends StatelessWidget {
  final String text;
  final bool isUser;

  const _MessageText({required this.text, required this.isUser});

  @override
  Widget build(BuildContext context) {
    // Parse inline bold (**text**) and code (`text`)
    final spans = _parseText(text, isUser);
    return RichText(
      text: TextSpan(children: spans),
    );
  }

  List<TextSpan> _parseText(String text, bool isUser) {
    final spans = <TextSpan>[];
    final baseColor = isUser ? const Color(0xFF00d4ff) : Colors.white;
    const baseSize = 15.0;

    // Simple state machine for bold + code
    final regex = RegExp(r'\*\*(.*?)\*\*|`(.*?)`');
    int lastEnd = 0;

    for (final match in regex.allMatches(text)) {
      // Add text before match
      if (match.start > lastEnd) {
        spans.add(TextSpan(
          text: text.substring(lastEnd, match.start),
          style: TextStyle(color: baseColor, fontSize: baseSize, height: 1.4),
        ));
      }

      // Bold
      if (match.group(1) != null) {
        spans.add(TextSpan(
          text: match.group(1),
          style: TextStyle(
            color: baseColor,
            fontSize: baseSize,
            fontWeight: FontWeight.w700,
            height: 1.4,
          ),
        ));
      }
      // Code
      else if (match.group(2) != null) {
        spans.add(TextSpan(
          text: match.group(2),
          style: TextStyle(
            color: const Color(0xFF00d4ff),
            fontSize: baseSize - 1,
            fontFamily: 'monospace',
            backgroundColor: const Color(0xFF0a0a0f),
            height: 1.4,
          ),
        ));
      }

      lastEnd = match.end;
    }

    // Remaining text
    if (lastEnd < text.length) {
      spans.add(TextSpan(
        text: text.substring(lastEnd),
        style: TextStyle(color: baseColor, fontSize: baseSize, height: 1.4),
      ));
    }

    // Fallback for plain text
    if (spans.isEmpty) {
      spans.add(TextSpan(
        text: text,
        style: TextStyle(color: baseColor, fontSize: baseSize, height: 1.4),
      ));
    }

    return spans;
  }
}
