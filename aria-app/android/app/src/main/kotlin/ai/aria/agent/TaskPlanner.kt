package ai.aria.os.agent

import android.util.Log

/**
 * TaskPlanner — decomposes complex multi-step requests into an ordered list of tasks.
 *
 * Phase 1: simple passthrough (Claude handles planning natively via tool calls).
 * Phase 2: will pre-plan complex workflows, track progress, handle failures with retries.
 */
class TaskPlanner {

    companion object {
        const val TAG = "TaskPlanner"
    }

    data class Task(
        val id: String,
        val description: String,
        val toolName: String?,
        val toolInput: Map<String, Any>,
        var status: TaskStatus = TaskStatus.PENDING,
        var result: String? = null
    )

    enum class TaskStatus {
        PENDING, RUNNING, COMPLETED, FAILED, SKIPPED
    }

    data class Plan(
        val tasks: List<Task>,
        val description: String
    )

    /**
     * Analyze a user message and decide if it needs explicit multi-step planning.
     * Returns true if the request is complex enough to warrant a plan.
     */
    fun needsPlanning(userMessage: String): Boolean {
        val msg = userMessage.lowercase()
        val multiStepIndicators = listOf(
            "and then", "after that", "first", "then", "finally",
            "step", "in order", "sequence", "one by one"
        )
        return multiStepIndicators.any { msg.contains(it) }
    }

    /**
     * Creates a simple sequential plan for a known multi-step workflow.
     * In Phase 1, Claude handles most planning — this is used for very explicit sequences.
     */
    fun createPlan(description: String, tasks: List<Task>): Plan {
        Log.d(TAG, "Creating plan: $description with ${tasks.size} tasks")
        return Plan(tasks = tasks, description = description)
    }

    /**
     * Execute a plan task by task, stopping on failure unless skipOnError is true.
     */
    suspend fun executePlan(plan: Plan, registry: ToolRegistry, skipOnError: Boolean = false): List<Task> {
        for (task in plan.tasks) {
            if (task.status == TaskStatus.SKIPPED) continue

            task.status = TaskStatus.RUNNING
            Log.d(TAG, "Executing task: ${task.description}")

            try {
                val tool = task.toolName?.let { registry.getTool(it) }
                task.result = tool?.execute(task.toolInput) ?: "No tool specified"
                task.status = TaskStatus.COMPLETED
                Log.d(TAG, "Task completed: ${task.description} → ${task.result}")
            } catch (e: Exception) {
                task.status = TaskStatus.FAILED
                task.result = "Failed: ${e.message}"
                Log.e(TAG, "Task failed: ${task.description}", e)
                if (!skipOnError) break
            }
        }
        return plan.tasks
    }

    /**
     * Summarize a completed plan's results into a human-readable string.
     */
    fun summarizePlan(tasks: List<Task>): String {
        return tasks.joinToString("\n") { task ->
            val icon = when (task.status) {
                TaskStatus.COMPLETED -> "✅"
                TaskStatus.FAILED -> "❌"
                TaskStatus.SKIPPED -> "⏭️"
                TaskStatus.PENDING -> "⏳"
                TaskStatus.RUNNING -> "🔄"
            }
            "$icon ${task.description}: ${task.result ?: "not started"}"
        }
    }
}
