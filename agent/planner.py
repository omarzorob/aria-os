"""
Task Planner — breaks complex multi-step requests into executable steps.

Example: "Order my usual from Chipotle and text Sarah I'll be home by 7"
→ Step 1: food_order(restaurant="Chipotle", items="usual order")
→ Step 2: send_sms(contact="Sarah", message="I'll be home by 7")
"""

import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class StepStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"


@dataclass
class Step:
    id: int
    description: str
    tool: str
    inputs: dict[str, Any]
    status: StepStatus = StepStatus.PENDING
    result: str | None = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "description": self.description,
            "tool": self.tool,
            "inputs": self.inputs,
            "status": self.status.value,
            "result": self.result,
        }


@dataclass
class Plan:
    goal: str
    steps: list[Step] = field(default_factory=list)

    def add_step(self, description: str, tool: str, inputs: dict) -> Step:
        step = Step(
            id=len(self.steps) + 1,
            description=description,
            tool=tool,
            inputs=inputs,
        )
        self.steps.append(step)
        return step

    def next_step(self) -> Step | None:
        return next((s for s in self.steps if s.status == StepStatus.PENDING), None)

    def is_complete(self) -> bool:
        return all(s.status in (StepStatus.DONE, StepStatus.FAILED) for s in self.steps)

    def progress(self) -> str:
        done = sum(1 for s in self.steps if s.status == StepStatus.DONE)
        return f"{done}/{len(self.steps)} steps complete"

    def summary(self) -> str:
        lines = [f"Goal: {self.goal}", ""]
        for s in self.steps:
            icon = {"pending": "⬜", "running": "🔄", "done": "✅", "failed": "❌"}[s.status.value]
            lines.append(f"{icon} Step {s.id}: {s.description}")
            if s.result and s.status == StepStatus.DONE:
                lines.append(f"   → {s.result[:80]}")
        return "\n".join(lines)


class Planner:
    """
    Uses the LLM to decompose a complex request into a plan,
    then executes steps sequentially.
    """

    SYSTEM = """You are a task planner for Aria, an AI phone assistant.
Given a user request, output a JSON plan with steps to complete it.

Output format:
{
  "steps": [
    {"description": "what this step does", "tool": "tool_name", "inputs": {...}},
    ...
  ]
}

Only use tools that exist. Keep steps minimal. Output ONLY valid JSON."""

    def __init__(self, client, tools: list[dict]):
        self.client = client
        self.tools = tools
        self.tool_names = [t["name"] for t in tools]

    def create_plan(self, goal: str) -> Plan:
        """Ask the LLM to plan out how to achieve the goal."""
        tools_desc = "\n".join(f"- {t['name']}: {t['description']}" for t in self.tools)

        response = self.client.messages.create(
            model="claude-opus-4-6",
            max_tokens=1024,
            system=self.SYSTEM,
            messages=[{
                "role": "user",
                "content": f"Available tools:\n{tools_desc}\n\nUser request: {goal}"
            }]
        )

        try:
            data = json.loads(response.content[0].text)
            plan = Plan(goal=goal)
            for s in data.get("steps", []):
                if s.get("tool") in self.tool_names:
                    plan.add_step(s["description"], s["tool"], s.get("inputs", {}))
            return plan
        except (json.JSONDecodeError, KeyError):
            # Fallback: single-step plan (let the agent figure it out)
            plan = Plan(goal=goal)
            return plan

    def execute_plan(self, plan: Plan, tool_executor) -> str:
        """Execute all steps in the plan, return final summary."""
        for step in plan.steps:
            step.status = StepStatus.RUNNING
            result = tool_executor(step.tool, step.inputs)
            step.result = result
            step.status = StepStatus.DONE if "error" not in result.lower() else StepStatus.FAILED

        return plan.summary()
