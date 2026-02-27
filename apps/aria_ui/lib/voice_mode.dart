/// P1-30: Aria OS Voice Mode UI
///
/// Full-screen dark overlay for voice interaction.
/// Animated waveform using Canvas painter.
/// States: Listening → Thinking → Speaking
/// Tap anywhere to dismiss.

import 'dart:math';
import 'package:flutter/material.dart';

// ---------------------------------------------------------------------------
// Voice mode state enum
// ---------------------------------------------------------------------------

enum VoiceState {
  idle,
  listening,
  thinking,
  speaking,
}

// ---------------------------------------------------------------------------
// Voice Mode Overlay
// ---------------------------------------------------------------------------

class VoiceModeOverlay extends StatefulWidget {
  final VoidCallback onClose;
  final ValueChanged<String>? onTranscript;

  const VoiceModeOverlay({
    super.key,
    required this.onClose,
    this.onTranscript,
  });

  @override
  State<VoiceModeOverlay> createState() => _VoiceModeOverlayState();
}

class _VoiceModeOverlayState extends State<VoiceModeOverlay>
    with TickerProviderStateMixin {
  late final AnimationController _waveController;
  late final AnimationController _pulseController;
  late final AnimationController _fadeController;
  VoiceState _state = VoiceState.listening;

  // Mock waveform amplitude data (will be replaced by real audio levels)
  final List<double> _amplitudes = List.generate(32, (i) => 0.1);

  @override
  void initState() {
    super.initState();

    _waveController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 600),
    )..repeat(reverse: true);

    _pulseController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 1500),
    )..repeat(reverse: true);

    _fadeController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 300),
    )..forward();

    // Simulate state transitions for demo
    Future.delayed(const Duration(seconds: 3), () {
      if (mounted) setState(() => _state = VoiceState.thinking);
    });
    Future.delayed(const Duration(seconds: 5), () {
      if (mounted) setState(() => _state = VoiceState.speaking);
    });
  }

  @override
  void dispose() {
    _waveController.dispose();
    _pulseController.dispose();
    _fadeController.dispose();
    super.dispose();
  }

  // Update amplitudes (called from audio stream in real implementation)
  void updateAmplitudes(List<double> newAmplitudes) {
    if (mounted) {
      setState(() {
        for (int i = 0; i < _amplitudes.length && i < newAmplitudes.length; i++) {
          _amplitudes[i] = newAmplitudes[i];
        }
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return FadeTransition(
      opacity: _fadeController,
      child: GestureDetector(
        onTap: widget.onClose,
        child: Container(
          color: Colors.black.withAlpha(230),
          child: SafeArea(
            child: Column(
              children: [
                _buildTopBar(),
                const Spacer(),
                _buildStateLabel(),
                const SizedBox(height: 40),
                _buildWaveform(),
                const SizedBox(height: 40),
                _buildOrb(),
                const Spacer(),
                _buildBottomHint(),
                const SizedBox(height: 32),
              ],
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildTopBar() {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 16),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          const Row(
            children: [
              CircleAvatar(
                radius: 14,
                backgroundColor: Color(0xFF6C63FF),
                child: Text('A',
                    style: TextStyle(color: Colors.white,
                        fontSize: 13, fontWeight: FontWeight.bold)),
              ),
              SizedBox(width: 8),
              Text('Aria',
                  style: TextStyle(color: Colors.white,
                      fontSize: 16, fontWeight: FontWeight.w600)),
            ],
          ),
          GestureDetector(
            onTap: widget.onClose,
            child: Container(
              width: 36,
              height: 36,
              decoration: BoxDecoration(
                color: Colors.white.withAlpha(20),
                shape: BoxShape.circle,
              ),
              child: const Icon(Icons.close_rounded,
                  color: Colors.white70, size: 18),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildStateLabel() {
    return AnimatedSwitcher(
      duration: const Duration(milliseconds: 300),
      child: Text(
        _stateLabel,
        key: ValueKey(_state),
        style: TextStyle(
          color: Colors.white.withAlpha(180),
          fontSize: 18,
          fontWeight: FontWeight.w400,
          letterSpacing: 1.2,
        ),
      ),
    );
  }

  Widget _buildWaveform() {
    return AnimatedBuilder(
      animation: _waveController,
      builder: (context, _) {
        return SizedBox(
          height: 80,
          width: double.infinity,
          child: CustomPaint(
            painter: _WaveformPainter(
              amplitudes: _amplitudes,
              animValue: _waveController.value,
              state: _state,
              color: _stateColor,
            ),
          ),
        );
      },
    );
  }

  Widget _buildOrb() {
    return AnimatedBuilder(
      animation: _pulseController,
      builder: (context, _) {
        final scale = _state == VoiceState.listening
            ? 1.0 + _pulseController.value * 0.08
            : 1.0;
        final glowRadius = _state == VoiceState.listening
            ? 30.0 + _pulseController.value * 20
            : 20.0;

        return Transform.scale(
          scale: scale,
          child: Container(
            width: 88,
            height: 88,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              color: _stateColor.withAlpha(220),
              boxShadow: [
                BoxShadow(
                  color: _stateColor.withAlpha(100),
                  blurRadius: glowRadius,
                  spreadRadius: 4,
                ),
              ],
            ),
            child: Icon(
              _stateIcon,
              color: Colors.white,
              size: 36,
            ),
          ),
        );
      },
    );
  }

  Widget _buildBottomHint() {
    return Text(
      'Tap anywhere to dismiss',
      style: TextStyle(
        color: Colors.white.withAlpha(80),
        fontSize: 13,
      ),
    );
  }

  // ---------------------------------------------------------------------------
  // Helpers
  // ---------------------------------------------------------------------------

  String get _stateLabel {
    switch (_state) {
      case VoiceState.idle:
        return 'Tap to speak';
      case VoiceState.listening:
        return 'Listening...';
      case VoiceState.thinking:
        return 'Thinking...';
      case VoiceState.speaking:
        return 'Speaking...';
    }
  }

  Color get _stateColor {
    switch (_state) {
      case VoiceState.idle:
        return const Color(0xFF555555);
      case VoiceState.listening:
        return const Color(0xFF6C63FF);
      case VoiceState.thinking:
        return const Color(0xFFFFAA33);
      case VoiceState.speaking:
        return const Color(0xFF33CC88);
    }
  }

  IconData get _stateIcon {
    switch (_state) {
      case VoiceState.idle:
        return Icons.mic_none_rounded;
      case VoiceState.listening:
        return Icons.mic_rounded;
      case VoiceState.thinking:
        return Icons.auto_awesome_rounded;
      case VoiceState.speaking:
        return Icons.volume_up_rounded;
    }
  }
}

// ---------------------------------------------------------------------------
// Waveform Painter
// ---------------------------------------------------------------------------

class _WaveformPainter extends CustomPainter {
  final List<double> amplitudes;
  final double animValue;
  final VoiceState state;
  final Color color;

  _WaveformPainter({
    required this.amplitudes,
    required this.animValue,
    required this.state,
    required this.color,
  });

  @override
  void paint(Canvas canvas, Size size) {
    final barCount = amplitudes.length;
    final barWidth = size.width / (barCount * 2);
    final centerY = size.height / 2;
    final rng = Random(42); // Deterministic seed for stable idle animation

    final paint = Paint()
      ..color = color
      ..strokeCap = StrokeCap.round
      ..strokeWidth = barWidth * 0.85;

    for (int i = 0; i < barCount; i++) {
      final x = (i * 2 + 1) * barWidth;

      double amplitude;
      if (state == VoiceState.idle) {
        // Subtle idle animation
        amplitude = 0.08 + sin(animValue * 2 * pi + i * 0.3) * 0.04;
      } else if (state == VoiceState.thinking) {
        // Slow sine wave
        amplitude = 0.2 + sin(animValue * 2 * pi - i * 0.2) * 0.15;
      } else if (state == VoiceState.speaking) {
        // Medium consistent wave
        amplitude = 0.3 + sin(animValue * 2 * pi + i * 0.4) * 0.25;
      } else {
        // Listening: use real amplitudes + animation
        final base = amplitudes[i].clamp(0.0, 1.0);
        amplitude = base * (0.6 + animValue * 0.4);
        amplitude = amplitude.clamp(0.05, 1.0);
      }

      final barHeight = (size.height * 0.9) * amplitude;
      final opacity = 0.5 + amplitude * 0.5;

      paint.color = color.withAlpha((opacity * 255).toInt().clamp(0, 255));

      canvas.drawLine(
        Offset(x, centerY - barHeight / 2),
        Offset(x, centerY + barHeight / 2),
        paint,
      );
    }
  }

  @override
  bool shouldRepaint(_WaveformPainter old) =>
      old.animValue != animValue ||
      old.state != state ||
      old.amplitudes != amplitudes;
}
