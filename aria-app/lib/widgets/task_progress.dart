import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';

/// TaskProgress — shows a list of in-progress tasks with status icons.
/// Used to display multi-step operations (e.g., "Sending SMS → Done").
class TaskProgress extends StatelessWidget {
  final List<TaskItem> tasks;

  const TaskProgress({super.key, required this.tasks});

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: const Color(0xFF0D0D15),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(
          color: const Color(0xFF00d4ff).withOpacity(0.15),
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text(
            'Working...',
            style: TextStyle(
              color: Color(0xFF00d4ff),
              fontSize: 12,
              fontWeight: FontWeight.w600,
              letterSpacing: 0.5,
            ),
          ),
          const SizedBox(height: 8),
          ...tasks.asMap().entries.map((entry) {
            return _TaskRow(task: entry.value, index: entry.key);
          }),
        ],
      ),
    );
  }
}

class _TaskRow extends StatelessWidget {
  final TaskItem task;
  final int index;

  const _TaskRow({required this.task, required this.index});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 3),
      child: Row(
        children: [
          _StatusIcon(status: task.status),
          const SizedBox(width: 8),
          Expanded(
            child: Text(
              task.description,
              style: TextStyle(
                color: task.status == TaskStatus.pending
                    ? Colors.white38
                    : Colors.white70,
                fontSize: 13,
              ),
            ),
          ),
          if (task.status == TaskStatus.running)
            const SizedBox(
              width: 12,
              height: 12,
              child: CircularProgressIndicator(
                strokeWidth: 1.5,
                color: Color(0xFF00d4ff),
              ),
            ),
        ],
      ),
    )
        .animate(delay: (index * 100).ms)
        .fadeIn(duration: 200.ms)
        .slideX(begin: -0.1, end: 0);
  }
}

class _StatusIcon extends StatelessWidget {
  final TaskStatus status;
  const _StatusIcon({required this.status});

  @override
  Widget build(BuildContext context) {
    switch (status) {
      case TaskStatus.pending:
        return const Icon(Icons.circle_outlined, size: 14, color: Colors.white24);
      case TaskStatus.running:
        return const Icon(Icons.play_arrow_rounded, size: 14, color: Color(0xFF00d4ff));
      case TaskStatus.completed:
        return const Icon(Icons.check_circle_rounded, size: 14, color: Colors.green);
      case TaskStatus.failed:
        return const Icon(Icons.cancel_rounded, size: 14, color: Colors.red);
    }
  }
}

// ─── Data Model ──────────────────────────────────────────────────────────────

enum TaskStatus { pending, running, completed, failed }

class TaskItem {
  final String description;
  final TaskStatus status;
  final String? result;

  const TaskItem({
    required this.description,
    this.status = TaskStatus.pending,
    this.result,
  });

  TaskItem copyWith({TaskStatus? status, String? result}) {
    return TaskItem(
      description: description,
      status: status ?? this.status,
      result: result ?? this.result,
    );
  }
}
