import 'dart:async';
import 'dart:math' as math;
import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:provider/provider.dart';
import '../app.dart';
import '../services/aria_channel.dart';
import '../widgets/voice_waveform.dart';

class VoiceScreen extends StatefulWidget {
  const VoiceScreen({super.key});

  @override
  State<VoiceScreen> createState() => _VoiceScreenState();
}

class _VoiceScreenState extends State<VoiceScreen>
    with TickerProviderStateMixin {
  late AnimationController _pulseController;
  late AnimationController _glowController;
  StreamSubscription<String>? _replySub;
  VoiceState _localState = VoiceState.listening;
  String _statusText = 'Listening...';

  @override
  void initState() {
    super.initState();

    _pulseController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 1500),
    )..repeat(reverse: true);

    _glowController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 2000),
    )..repeat(reverse: true);

    _startListening();
    _subscribeToReplies();
  }

  Future<void> _startListening() async {
    setState(() {
      _localState = VoiceState.listening;
      _statusText = 'Listening...';
    });
    await AriaChannel.startListening();
  }

  void _subscribeToReplies() {
    _replySub = AriaChannel.replies.listen((reply) {
      if (mounted) {
        setState(() {
          _localState = VoiceState.speaking;
          _statusText = 'Speaking...';
        });

        // Update app state
        context.read<AriaState>().onReply(reply);

        // Return to listening after speaking (estimate based on text length)
        final speakDuration = Duration(
          milliseconds: (reply.length * 60).clamp(2000, 15000),
        );
        Future.delayed(speakDuration, () {
          if (mounted) {
            setState(() {
              _localState = VoiceState.idle;
              _statusText = 'Tap to speak';
            });
          }
        });
      }
    });
  }

  @override
  void dispose() {
    _pulseController.dispose();
    _glowController.dispose();
    _replySub?.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: () {
        if (_localState == VoiceState.idle) {
          _startListening();
        } else {
          Navigator.pop(context);
        }
      },
      child: Scaffold(
        backgroundColor: const Color(0xFF030308),
        body: SafeArea(
          child: Stack(
            children: [
              // Close button
              Positioned(
                top: 12,
                left: 12,
                child: IconButton(
                  icon: const Icon(Icons.close_rounded, color: Colors.white38),
                  onPressed: () => Navigator.pop(context),
                ),
              ),

              // Main content
              Center(
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    // Glowing circle with Aria text
                    _buildGlowingOrb(),

                    const SizedBox(height: 48),

                    // Status text
                    Text(
                      _statusText,
                      style: const TextStyle(
                        color: Colors.white60,
                        fontSize: 18,
                        fontWeight: FontWeight.w400,
                        letterSpacing: 1.0,
                      ),
                    ).animate().fadeIn(duration: 300.ms),

                    const SizedBox(height: 40),

                    // Waveform (shown only when listening or speaking)
                    if (_localState == VoiceState.listening ||
                        _localState == VoiceState.speaking)
                      SizedBox(
                        width: 200,
                        height: 48,
                        child: VoiceWaveform(
                          isActive: _localState == VoiceState.listening ||
                              _localState == VoiceState.speaking,
                          color: const Color(0xFF00d4ff),
                        ),
                      ),

                    if (_localState == VoiceState.thinking)
                      _buildThinkingDots(),
                  ],
                ),
              ),

              // Tap hint at bottom
              Positioned(
                bottom: 32,
                left: 0,
                right: 0,
                child: Text(
                  _localState == VoiceState.idle
                      ? 'Tap to speak'
                      : 'Tap anywhere to dismiss',
                  textAlign: TextAlign.center,
                  style: TextStyle(
                    color: Colors.white.withOpacity(0.2),
                    fontSize: 13,
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildGlowingOrb() {
    const accent = Color(0xFF00d4ff);

    return AnimatedBuilder(
      animation: _pulseController,
      builder: (context, child) {
        final pulse = _pulseController.value;
        final glowRadius = 60 + pulse * 30;

        return Stack(
          alignment: Alignment.center,
          children: [
            // Outer glow
            Container(
              width: glowRadius * 2,
              height: glowRadius * 2,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                color: accent.withOpacity(0.05 + pulse * 0.05),
              ),
            ),

            // Mid ring
            Container(
              width: 140,
              height: 140,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                border: Border.all(
                  color: accent.withOpacity(0.15 + pulse * 0.15),
                  width: 1.5,
                ),
              ),
            ),

            // Inner orb
            Container(
              width: 100,
              height: 100,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                gradient: RadialGradient(
                  colors: [
                    accent.withOpacity(0.3),
                    accent.withOpacity(0.05),
                  ],
                ),
                border: Border.all(
                  color: accent.withOpacity(0.4 + pulse * 0.3),
                  width: 2,
                ),
                boxShadow: [
                  BoxShadow(
                    color: accent.withOpacity(0.2 + pulse * 0.2),
                    blurRadius: 30 + pulse * 20,
                    spreadRadius: 0,
                  ),
                ],
              ),
              child: const Center(
                child: Text(
                  'ARIA',
                  style: TextStyle(
                    color: Color(0xFF00d4ff),
                    fontSize: 16,
                    fontWeight: FontWeight.w700,
                    letterSpacing: 4,
                  ),
                ),
              ),
            ),
          ],
        );
      },
    );
  }

  Widget _buildThinkingDots() {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: List.generate(3, (i) {
        return Container(
          margin: const EdgeInsets.symmetric(horizontal: 4),
          width: 8,
          height: 8,
          decoration: const BoxDecoration(
            color: Color(0xFF00d4ff),
            shape: BoxShape.circle,
          ),
        )
            .animate(onPlay: (c) => c.repeat())
            .scaleXY(
              begin: 0.6,
              end: 1.2,
              duration: 600.ms,
              delay: (i * 200).ms,
              curve: Curves.easeInOut,
            )
            .then()
            .scaleXY(begin: 1.2, end: 0.6, duration: 600.ms);
      }),
    );
  }
}
