"""
Seed the database with three hardcoded demo personas, two draft goals for Alex,
and one timeline event per goal.

Run with:
    cd backend && python seed.py

Idempotent — safe to run multiple times. Uses deterministic UUIDs that match
the frontend RoleSwitcher.tsx.
"""
import asyncio
import os
import sys
from decimal import Decimal
from uuid import UUID

# Ensure the workspace root is on sys.path so `backend.app.*` imports resolve
# when running as `cd backend && python seed.py`
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.app.database import AsyncSessionLocal, engine, Base  # noqa: E402
from backend.app.models import (  # noqa: E402
    User,
    UserRole,
    Goal,
    GoalStatus,
    GoalHealth,
    TimelineEvent,
    EventType,
)

# ---------------------------------------------------------------------------
# Deterministic UUIDs — must match frontend RoleSwitcher.tsx
# ---------------------------------------------------------------------------
RIYA_ID     = UUID("11111111-1111-1111-1111-111111111111")
ALEX_ID     = UUID("22222222-2222-2222-2222-222222222222")
HR_ADMIN_ID = UUID("33333333-3333-3333-3333-333333333333")

GOAL1_ID = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
GOAL2_ID = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")


async def seed() -> None:
    # Ensure all tables exist (no-op if already created by Alembic)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as session:
        # ------------------------------------------------------------------
        # Users
        # ------------------------------------------------------------------
        riya = await session.get(User, RIYA_ID)
        if riya is None:
            riya = User(
                id=RIYA_ID,
                name="Riya",
                role=UserRole.manager,
                manager_id=None,
            )
            session.add(riya)
            print("Seeded user: Riya (manager)")
        else:
            print("Skipped (exists): Riya")

        alex = await session.get(User, ALEX_ID)
        if alex is None:
            alex = User(
                id=ALEX_ID,
                name="Alex",
                role=UserRole.employee,
                manager_id=RIYA_ID,
            )
            session.add(alex)
            print("Seeded user: Alex (employee)")
        else:
            print("Skipped (exists): Alex")

        hr_admin = await session.get(User, HR_ADMIN_ID)
        if hr_admin is None:
            hr_admin = User(
                id=HR_ADMIN_ID,
                name="HR Admin",
                role=UserRole.hr,
                manager_id=None,
            )
            session.add(hr_admin)
            print("Seeded user: HR Admin (hr)")
        else:
            print("Skipped (exists): HR Admin")

        # Flush so FKs are satisfied before inserting goals
        await session.flush()

        # ------------------------------------------------------------------
        # Goals for Alex
        # ------------------------------------------------------------------
        goal1_created = False
        goal1 = await session.get(Goal, GOAL1_ID)
        if goal1 is None:
            goal1 = Goal(
                id=GOAL1_ID,
                employee_id=ALEX_ID,
                parent_goal_id=None,
                title="Reduce API latency by 20%",
                success_metric="p95 < 200ms",
                weight=Decimal("0.400"),
                status=GoalStatus.draft,
                progress=0,
                health=GoalHealth.on_track,
            )
            session.add(goal1)
            goal1_created = True
            print("Seeded goal: Reduce API latency by 20%")
        else:
            print("Skipped (exists): Reduce API latency by 20%")

        goal2_created = False
        goal2 = await session.get(Goal, GOAL2_ID)
        if goal2 is None:
            goal2 = Goal(
                id=GOAL2_ID,
                employee_id=ALEX_ID,
                parent_goal_id=GOAL1_ID,  # child of goal1 — demos cascading
                title="Implement Redis caching layer",
                success_metric="Cache hit rate > 80%",
                weight=Decimal("0.300"),
                status=GoalStatus.draft,
                progress=0,
                health=GoalHealth.on_track,
            )
            session.add(goal2)
            goal2_created = True
            print("Seeded goal: Implement Redis caching layer")
        else:
            print("Skipped (exists): Implement Redis caching layer")

        # Flush so goal IDs are available for timeline event FKs
        await session.flush()

        # ------------------------------------------------------------------
        # Timeline events — one per goal, only when the goal was just created
        # ------------------------------------------------------------------
        if goal1_created:
            event1 = TimelineEvent(
                employee_id=ALEX_ID,
                actor_id=ALEX_ID,
                event_type=EventType.goal_created,
                payload={
                    "goal_id": str(GOAL1_ID),
                    "title": goal1.title,
                    "status": "draft",
                },
                linked_goal_id=GOAL1_ID,
            )
            session.add(event1)
            print("Seeded timeline event for: Reduce API latency by 20%")

        if goal2_created:
            event2 = TimelineEvent(
                employee_id=ALEX_ID,
                actor_id=ALEX_ID,
                event_type=EventType.goal_created,
                payload={
                    "goal_id": str(GOAL2_ID),
                    "title": goal2.title,
                    "status": "draft",
                },
                linked_goal_id=GOAL2_ID,
            )
            session.add(event2)
            print("Seeded timeline event for: Implement Redis caching layer")

        # ------------------------------------------------------------------
        # Single commit — all-or-nothing
        # ------------------------------------------------------------------
        await session.commit()
        print("\nSeed complete.")


if __name__ == "__main__":
    asyncio.run(seed())
