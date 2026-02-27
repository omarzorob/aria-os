/// P1-31: Task Progress Widget
///
/// Shows the current task Aria is executing.
/// Step list with checkmarks. Collapsible. Slides up from bottom.

import 'package:flutter/material.dart';

// ---------------------------------------------------------------------------
// Data models
// ---------------------------------------------------------------------------

enum StepStatus { pending, running, completed, failed }

class TaskStep {
  final String id;
  final String description;
  final StepStatus status;
  final String? detail;
  final Duration? duration;

  const TaskStep({
    required this.id,
    required this.description,
    required this.status,
    this.detail,
    this.duration,
  });

  TaskStep copyWith({
    StepStatus? status,
    String? detail,
    Duration? duration,
  }) =>
      TaskStep(
        id: id,
        description: description,
        status: status ?? this.status,
        detail: detail ?? this.detail,
        duration: duration ?? this.duration,
      );
}

// ---------------------------------------------------------------------------
// Task Progress Panel
// ---------------------------------------------------------------------------

class TaskProgressPanel extends StatefulWidget {
  final String currentTask;
  final List<TaskStep> steps;
  final VoidCallback? onDismiss;
  final bool initiallyExpanded;

  const TaskProgressPanel({
    super.key,
    required this.currentTask,
    required this.steps,
    this.onDismiss,
    this.initiallyExpanded = true,
  });

  @override
  State<TaskProgressPanel> createState() => _TaskProgressPanelState();
}

class _TaskProgressPanelState extends State<TaskProgressPanel>
    with SingleTickerProviderStateMixin {
  late final AnimationController _slideController;
  late final Animation<Offset> _slideAnimation;
  bool _expanded = true;

  @override
  void initState() {
    super.initState();
    _expanded = widget.initiallyExpanded;

    _slideController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 350),
    );

    _slideAnimation = Tween<Offset>(
      begin: const Offset(0, 1),
      end: Offset.zero,
    ).animate(CurvedAnimation(
      parent: _slideController,
      curve: Curves.easeOutCubic,
    ));

    _slideController.forward();
  }

  @override
  void dispose() {
    _slideController.dispose();
    super.dispose();
  }

  int get _completedCount =>
      widget.steps.where((s) => s.status == StepStatus.completed).length;

  int? get _runningIndex => widget.steps
      .indexWhere((s) => s.status == StepStatus.running)
      .let((i) => i >= 0 ? i : null);

  @override
  Widget build(BuildContext context) {
    return SlideTransition(
      position: _slideAnimation,
      child: Container(
        decoration: const BoxDecoration(
          color: Color(0xFF141414),
          border: Border(
            top: BorderSide(color: Color(0xFF2A2A2A), width: 1),
          ),
        ),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            _buildHeader(),
            if (_expanded) _buildStepList(),
          ],
        ),
      ),
    );
  }

  Widget _buildHeader() {
    final running = _runningIndex != null;
    final progress = widget.steps.isEmpty
        ? 0.0
        : _completedCount / widget.steps.length;

    return InkWell(
      onTap: () => setState(() => _expanded = !_expanded),
      child: Padding(
        padding: const EdgeInsets.fromLTRB(16, 12, 12, 10),
        child: Row(
          children: [
            // Status icon
            _StatusIcon(isRunning: running),
            const SizedBox(width: 12),
            // Task label
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    widget.currentTask.isEmpty
                        ? 'No active task'
                        : widget.currentTask,
                    style: const TextStyle(
                      color: Color(0xFFEEEEEE),
                      fontSize: 14,
                      fontWeight: FontWeight.w600,
                    ),
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                  ),
                  if (widget.steps.isNotEmpty)
                    Text(
                      '$_completedCount / ${widget.steps.length} steps',
                      style: const TextStyle(
                        color: Color(0xFF888888),
                        fontSize: 12,
                      ),
                    ),
                ],
              ),
            ),
            // Progress indicator
            if (widget.steps.isNotEmpty)
              SizedBox(
                width: 36,
                height: 36,
                child: Stack(
                  alignment: Alignment.center,
                  children: [
                    CircularProgressIndicator(
                      value: progress,
                      strokeWidth: 3,
                      backgroundColor: const Color(0xFF2A2A2A),
                      color: progress == 1.0
                          ? const Color(0xFF4CAF50)
                          : const Color(0xFF6C63FF),
                    ),
                    Text(
                      '${(progress * 100).round()}%',
                      style: const TextStyle(
                        color: Color(0xFFEEEEEE),
                        fontSize: 9,
                      ),
                    ),
                  ],
                ),
              ),
            const SizedBox(width: 8),
            // Expand / collapse chevron
            Icon(
              _expanded ? Icons.expand_more_rounded : Icons.expand_less_rounded,
              color: const Color(0xFF555555),
              size: 20,
            ),
            // Dismiss button
            if (widget.onDismiss != null)
              GestureDetector(
                onTap: widget.onDismiss,
                child: const Padding(
                  padding: EdgeInsets.only(left: 8),
                  child: Icon(Icons.close_rounded,
                      color: Color(0xFF555555), size: 18),
                ),
              ),
          ],
        ),
      ),
    );
  }

  Widget _buildStepList() {
    if (widget.steps.isEmpty) {
      return const Padding(
        padding: EdgeInsets.fromLTRB(16, 0, 16, 16),
        child: Text(
          'No steps yet.',
          style: TextStyle(color: Color(0xFF555555), fontSize: 13),
        ),
      );
    }

    return AnimatedSize(
      duration: const Duration(milliseconds: 250),
      curve: Curves.easeOut,
      child: ConstrainedBox(
        constraints: const BoxConstraints(maxHeight: 240),
        child: ListView.separated(
          shrinkWrap: true,
          padding: const EdgeInsets.fromLTRB(16, 0, 16, 14),
          itemCount: widget.steps.length,
          separatorBuilder: (_, __) => const Divider(
            color: Color(0xFF222222),
            height: 1,
            thickness: 1,
          ),
          itemBuilder: (context, index) {
            return _StepTile(
              step: widget.steps[index],
              isLast: index == widget.steps.length - 1,
            );
          },
        ),
      ),
    );
  }
}

// ---------------------------------------------------------------------------
// Step Tile Widget
// ---------------------------------------------------------------------------

class _StepTile extends StatelessWidget {
  final TaskStep step;
  final bool isLast;

  const _StepTile({required this.step, required this.isLast});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 9),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _buildStatusWidget(),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  step.description,
                  style: TextStyle(
                    color: _textColor,
                    fontSize: 13.5,
                    fontWeight: step.status == StepStatus.running
                        ? FontWeight.w600
                        : FontWeight.w400,
                    decoration: step.status == StepStatus.completed
                        ? TextDecoration.none
                        : null,
                  ),
                ),
                if (step.detail != null && step.detail!.isNotEmpty)
                  Padding(
                    padding: const EdgeInsets.only(top: 2),
                    child: Text(
                      step.detail!,
                      style: const TextStyle(
                        color: Color(0xFF666666),
                        fontSize: 11.5,
                      ),
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                    ),
                  ),
              ],
            ),
          ),
          if (step.duration != null)
            Text(
              _formatDuration(step.duration!),
              style: const TextStyle(color: Color(0xFF555555), fontSize: 11),
            ),
        ],
      ),
    );
  }

  Widget _buildStatusWidget() {
    switch (step.status) {
      case StepStatus.completed:
        return Container(
          width: 20,
          height: 20,
          decoration: const BoxDecoration(
            color: Color(0xFF4CAF50),
            shape: BoxShape.circle,
          ),
          child: const Icon(Icons.check_rounded, color: Colors.white, size: 13),
        );
      case StepStatus.running:
        return const SizedBox(
          width: 20,
          height: 20,
          child: CircularProgressIndicator(
            strokeWidth: 2.5,
            color: Color(0xFF6C63FF),
          ),
        );
      case StepStatus.failed:
        return Container(
          width: 20,
          height: 20,
          decoration: const BoxDecoration(
            color: Color(0xFFE53935),
            shape: BoxShape.circle,
          ),
          child: const Icon(Icons.close_rounded, color: Colors.white, size: 13),
        );
      case StepStatus.pending:
        return Container(
          width: 20,
          height: 20,
          decoration: BoxDecoration(
            border: Border.all(color: const Color(0xFF3A3A3A), width: 2),
            shape: BoxShape.circle,
          ),
        );
    }
  }

  Color get _textColor {
    switch (step.status) {
      case StepStatus.completed:
        return const Color(0xFF888888);
      case StepStatus.running:
        return const Color(0xFFEEEEEE);
      case StepStatus.failed:
        return const Color(0xFFE57373);
      case StepStatus.pending:
        return const Color(0xFF666666);
    }
  }

  String _formatDuration(Duration d) {
    if (d.inSeconds < 60) return '${d.inSeconds}s';
    if (d.inMinutes < 60) return '${d.inMinutes}m ${d.inSeconds % 60}s';
    return '${d.inHours}h ${d.inMinutes % 60}m';
  }
}

// ---------------------------------------------------------------------------
// Status indicator (animated pulse for running state)
// ---------------------------------------------------------------------------

class _StatusIcon extends StatefulWidget {
  final bool isRunning;

  const _StatusIcon({required this.isRunning});

  @override
  State<_StatusIcon> createState() => _StatusIconState();
}

class _StatusIconState extends State<_StatusIcon>
    with SingleTickerProviderStateMixin {
  late final AnimationController _pulse;
  late final Animation<double> _animation;

  @override
  void initState() {
    super.initState();
    _pulse = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 800),
    )..repeat(reverse: true);
    _animation = Tween<double>(begin: 0.5, end: 1.0).animate(
      CurvedAnimation(parent: _pulse, curve: Curves.easeInOut),
    );
  }

  @override
  void dispose() {
    _pulse.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    if (!widget.isRunning) {
      return Container(
        width: 8,
        height: 8,
        margin: const EdgeInsets.symmetric(vertical: 8),
        decoration: const BoxDecoration(
          color: Color(0xFF4CAF50),
          shape: BoxShape.circle,
        ),
      );
    }

    return AnimatedBuilder(
      animation: _animation,
      builder: (_, __) => Opacity(
        opacity: _animation.value,
        child: Container(
          width: 8,
          height: 8,
          margin: const EdgeInsets.symmetric(vertical: 8),
          decoration: const BoxDecoration(
            color: Color(0xFF6C63FF),
            shape: BoxShape.circle,
          ),
        ),
      ),
    );
  }
}

// ---------------------------------------------------------------------------
// Extension helper
// ---------------------------------------------------------------------------

extension _LetExt<T> on T {
  R let<R>(R Function(T) f) => f(this);
}
