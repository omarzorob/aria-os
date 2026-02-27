import 'dart:math' as math;
import 'package:flutter/material.dart';

/// Animated voice waveform using a canvas painter.
/// Shows 7 bars that animate up/down when active.
class VoiceWaveform extends StatefulWidget {
  final bool isActive;
  final Color color;
  final int barCount;

  const VoiceWaveform({
    super.key,
    required this.isActive,
    this.color = const Color(0xFF00d4ff),
    this.barCount = 7,
  });

  @override
  State<VoiceWaveform> createState() => _VoiceWaveformState();
}

class _VoiceWaveformState extends State<VoiceWaveform>
    with TickerProviderStateMixin {
  late List<AnimationController> _controllers;
  late List<Animation<double>> _animations;

  @override
  void initState() {
    super.initState();
    _initAnimations();
    if (widget.isActive) _startAnimations();
  }

  void _initAnimations() {
    _controllers = List.generate(widget.barCount, (i) {
      return AnimationController(
        vsync: this,
        duration: Duration(milliseconds: 400 + (i * 80)),
      );
    });

    _animations = _controllers.map((c) {
      return Tween<double>(begin: 0.15, end: 1.0).animate(
        CurvedAnimation(parent: c, curve: Curves.easeInOut),
      );
    }).toList();
  }

  void _startAnimations() {
    for (int i = 0; i < _controllers.length; i++) {
      Future.delayed(Duration(milliseconds: i * 60), () {
        if (mounted && widget.isActive) {
          _controllers[i].repeat(reverse: true);
        }
      });
    }
  }

  void _stopAnimations() {
    for (final c in _controllers) {
      c.animateTo(0.15, duration: const Duration(milliseconds: 300));
    }
  }

  @override
  void didUpdateWidget(VoiceWaveform oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (widget.isActive != oldWidget.isActive) {
      if (widget.isActive) {
        _startAnimations();
      } else {
        _stopAnimations();
      }
    }
  }

  @override
  void dispose() {
    for (final c in _controllers) {
      c.dispose();
    }
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: Listenable.merge(_controllers),
      builder: (context, child) {
        return CustomPaint(
          painter: _WaveformPainter(
            values: _animations.map((a) => a.value).toList(),
            color: widget.color,
          ),
          size: Size.infinite,
        );
      },
    );
  }
}

class _WaveformPainter extends CustomPainter {
  final List<double> values;
  final Color color;

  _WaveformPainter({required this.values, required this.color});

  @override
  void paint(Canvas canvas, Size size) {
    final paint = Paint()
      ..color = color
      ..style = PaintingStyle.fill
      ..strokeCap = StrokeCap.round;

    final barWidth = 4.0;
    final spacing = (size.width - barWidth * values.length) / (values.length + 1);
    final maxBarHeight = size.height * 0.85;

    for (int i = 0; i < values.length; i++) {
      final x = spacing + i * (barWidth + spacing);
      final barHeight = maxBarHeight * values[i];
      final y = (size.height - barHeight) / 2;

      // Draw bar with rounded corners
      final rect = RRect.fromRectAndRadius(
        Rect.fromLTWH(x, y, barWidth, barHeight),
        const Radius.circular(3),
      );

      // Opacity based on height (taller bars are more opaque)
      paint.color = color.withOpacity(0.4 + values[i] * 0.6);
      canvas.drawRRect(rect, paint);
    }
  }

  @override
  bool shouldRepaint(_WaveformPainter old) {
    return old.values != values || old.color != color;
  }
}
