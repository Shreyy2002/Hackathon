"""
Goal service — Goals context.
Requirements: 2.1, 2.2, 2.3

Provides:
  get_total_goal_weight  — sum of weights for an employee's existing goals
  compute_performance_score — weighted completion score in [0.0, 100.0]
  build_goal_tree        — convert flat Goal list into a nested tree of dicts
"""
from __future__ import annotations

from decimal import Decimal
from typing import Any, List
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.goal import Goal, GoalStatus


async def get_total_goal_weight(db: AsyncSession, employee_id: UUID) -> Decimal:
    """
    Sum of weights of all existing goals for an employee.

    Preconditions:
      - employee_id references an existing users row.
    Postconditions:
      - Returns Decimal >= 0.
      - Returns Decimal("0") when the employee has no goals.
    """
    result = await db.execute(
        select(func.coalesce(func.sum(Goal.weight), 0))
        .where(Goal.employee_id == employee_id)
    )
    return Decimal(str(result.scalar_one()))


def compute_performance_score(goals: List[Goal]) -> Decimal:
    """
    Weighted completion score across all approved goals.

    Preconditions:
      - goals may be empty.
      - Each goal.weight is a non-negative Decimal.
      - Each goal.progress is an int in [0, 100].

    Postconditions:
      - Return value is a Decimal in [0.00, 100.00].
      - Returns Decimal("0.0") when no approved goals exist.
      - Does not mutate any goal object.

    Loop invariants:
      - weighted_sum grows monotonically as each approved goal is processed.
      - All previously summed goals had status == approved.
    """
    approved = [g for g in goals if g.status == GoalStatus.approved]
    if not approved:
        return Decimal("0.0")

    total_weight = sum(Decimal(str(g.weight)) for g in approved)
    if total_weight == Decimal("0"):
        return Decimal("0.0")

    weighted_sum = sum(
        Decimal(str(g.progress)) * Decimal(str(g.weight)) for g in approved
    )
    return (weighted_sum / total_weight).quantize(Decimal("0.01"))


def build_goal_tree(all_goals: List[Goal]) -> List[Any]:
    """
    Convert a flat list of Goal ORM objects into a nested tree of dicts.

    Input:  flat list of Goal ORM objects for one employee.
    Output: list of root GoalRead-like dicts with children nested recursively.

    Preconditions:
      - all_goals contains only goals for a single employee.
      - No circular parent references exist (enforced by DB constraint).

    Postconditions:
      - Only root goals (parent_goal_id IS NULL) appear at the top level.
      - Each node's "children" list is recursively populated.
      - Orphaned goals (parent_goal_id references a goal not in all_goals)
        are silently dropped.

    Loop invariant:
      - goal_map is fully populated before the second pass begins.
      - Each iteration of the second pass processes exactly one goal.
    """
    from backend.app.schemas.goals import GoalRead

    # First pass: build id → dict map and initialise empty children lists.
    # Loop invariant: goal_map is fully populated after this pass completes.
    goal_map: dict[Any, Any] = {
        g.id: GoalRead.model_validate(g).model_dump(mode="json")
        for g in all_goals
    }
    for v in goal_map.values():
        v["children"] = []

    # Second pass: attach each node to its parent or to the roots list.
    roots: List[Any] = []
    for g in all_goals:
        node = goal_map[g.id]
        if g.parent_goal_id is None:
            roots.append(node)
        elif g.parent_goal_id in goal_map:
            goal_map[g.parent_goal_id]["children"].append(node)
        # else: orphan — silently drop

    return roots
