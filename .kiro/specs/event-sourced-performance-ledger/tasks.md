# Implementation Plan: Event-Sourced Performance Ledger

## Overview

Implement the full-stack performance management system in five sequential phases targeting a 52-hour hackathon window. The backend is a FastAPI async modular monolith (Python) with PostgreSQL, Redis, and Celery. The frontend is React (Vite + TailwindCSS). All eight correctness properties are covered by hypothesis property-based tests.

## Tasks

- [ ] 1. Phase 1 — Foundation: Project Scaffolding, Docker, DB, Seeding, Role Switching
  - [x] 1.1 Create project directory structure and Docker Compose
    - Scaffold `backend/` and `frontend/` directories per the design's project structure
    - Write `docker-compose.yml` with services: `postgres`, `redis`, `backend`, `celery`, `frontend`
    - Write `backend/requirements.txt` with pinned versions from design dependencies table
    - Write `frontend/package.json` with pinned versions from design dependencies table
    - _Requirements: 1.1_

  - [x] 1.2 Set up async SQLAlchemy engine, session factory, and base model
    - Write `backend/app/database.py` with `AsyncEngine`, `AsyncSession`, and `Base`
    - Configure `asyncpg` connection string from environment variables
    - _Requirements: 7.1, 7.2_

  - [x] 1.3 Write SQLAlchemy ORM models for all four tables
    - Write `backend/app/models/user.py` — `User` model with `UserRole` enum
    - Write `backend/app/models/goal.py` — `Goal` model with `GoalStatus`, `GoalHealth` enums and self-referential FK
    - Write `backend/app/models/timeline_event.py` — `TimelineEvent` model with `EventType` enum and JSONB `payload`; no `updated_at`
    - Write `backend/app/models/review.py` — `Review` model with `ReviewStatus` enum
    - _Requirements: 2.1–2.7, 7.1, 13.1_

  - [x] 1.4 Write Alembic migrations and append-only DB trigger
    - Initialise Alembic; generate initial migration for all four tables
    - Add `(employee_id, created_at DESC)` and `event_type` indexes on `timeline_events`
    - Embed the `prevent_timeline_mutation` PostgreSQL trigger SQL in the migration
    - _Requirements: 7.1, 7.7, 7.8_

  - [x] 1.5 Write seed script for the three hardcoded personas
    - Write `backend/seed.py` seeding Riya (manager), Alex (employee, manager_id=Riya), HR Admin (hr)
    - Seed at least two draft goals for Alex and one sample timeline event per goal
    - Make the script idempotent (upsert by name)
    - _Requirements: 1.1_

  - [x] 1.6 Implement Identity context — role-switching endpoints and current-user DI
    - Write `backend/app/schemas/` Pydantic models: `UserRead`, `RoleSwitchRequest`, `EmployeeProfileRead`
    - Write `backend/app/routers/auth.py`: `POST /api/auth/switch-role` (set cookie, 404 on unknown ID)
    - Write `backend/app/routers/employees.py`: `GET /api/employees/{id}/profile` (user + goals + 20 recent events)
    - Write `get_current_user` dependency that reads `X-Current-User` cookie and returns `User`
    - _Requirements: 1.1–1.5_

  - [x] 1.7 Bootstrap FastAPI app with CORS and WebSocket skeleton
    - Write `backend/app/main.py`: app factory, CORS (`http://localhost:5173`), include all routers
    - Add placeholder `/ws/{employee_id}` WebSocket endpoint (accept + close) to unblock frontend
    - _Requirements: 14.1_

  - [x] 1.8 Scaffold React frontend with Vite, TailwindCSS, Zustand user store, and API client
    - Configure Vite, TailwindCSS, `@tanstack/react-query` provider
    - Write `frontend/src/store/userStore.ts` Zustand store: `currentUser`, `setUser`
    - Write `frontend/src/api/client.ts` axios wrapper that attaches cookie header
    - Write `RoleSwitcher` component (dropdown: Riya / Alex / HR Admin) that calls `POST /api/auth/switch-role`
    - _Requirements: 1.1, 1.2_

  - [x] 1.9 Checkpoint — Foundation complete
    - Ensure `docker compose up` starts all services without error
    - Confirm seed script populates three users and sample data
    - Confirm role-switcher sets cookie and `GET /api/employees/{id}/profile` returns data
    - Ask the user if any adjustments are needed before proceeding.

- [x] 2. Phase 2 — Core Flow: Timeline Append, Goals CRUD + Approval, Timeline UI
  - [x] 2.1 Implement `append_event` service and Timeline context schemas
    - Write `backend/app/services/timeline_service.py`: `append_event` function (flush, no commit)
    - Write `backend/app/schemas/timeline.py`: `TimelineEventCreate`, `TimelineEventRead`, `EventType`
    - Write all seven JSONB payload Pydantic validators (GoalEventPayload, ProgressEventPayload, FeedbackEventPayload, AchievementEventPayload, CheckInEventPayload, EvidenceEventPayload) and a dispatcher that validates `payload` by `event_type`
    - _Requirements: 7.2, 7.3, 16.1–16.7_

  - [x] 2.2 Implement Timeline router — POST and paginated GET
    - Write `backend/app/routers/timeline.py`
    - `POST /api/timeline/events`: validate payload schema, call `append_event`, commit, broadcast via WebSocket manager, return 201
    - `GET /api/timeline/events`: paginated (`offset`, `limit=20`) and filterable by `event_type`, ordered by `created_at DESC`
    - Enforce `linked_goal_id` cross-employee 403 check
    - _Requirements: 7.2–7.5, 8.1–8.5, 18.3_

  - [x] 2.3 Implement Goals service — creation, weight validation, and cascade tree
    - Write `backend/app/services/goal_service.py`
    - `get_total_goal_weight(db, employee_id)` query
    - `compute_performance_score(goals)` — weighted sum, normalise, return `Decimal` in [0, 100]
    - `build_goal_tree(all_goals)` — index by id, attach children, drop orphans, return roots
    - _Requirements: 2.1–2.7, 5.1–5.5, 6.1–6.4_

  - [ ]* 2.4 Write property test — Property 3: performance score always in [0, 100]
    - Write `backend/tests/test_properties.py` using `hypothesis`
    - Generate arbitrary lists of approved goal objects with random progress [0,100] and weight [0.01, 1.0]
    - Assert `Decimal("0.0") <= compute_performance_score(goals) <= Decimal("100.0")`
    - **Property 3: Performance score bounds**
    - **Validates: Requirements 5.3**

  - [ ]* 2.5 Write property test — Property 2: goal weight invariant never exceeds 1.0
    - Generate arbitrary weight sequences; simulate the guard logic
    - Assert total allocated weight is always `<= Decimal("1.0")` after each accepted creation
    - **Property 2: Goal weight invariant**
    - **Validates: Requirements 2.1, 5.5**

  - [x] 2.6 Implement Goals router — CRUD and approval state machine
    - Write `backend/app/routers/goals.py`
    - `POST /api/goals`: weight overflow check (400), parent_goal_id validation (404), create goal, emit `goal_created` event, return 201
    - `GET /api/goals/{id}`: return single goal
    - `GET /api/goals?employee_id=`: return flat list + performance score
    - `PATCH /api/goals/{id}/submit`: draft→pending_approval, emit `goal_submitted`, 400 on wrong state
    - `PATCH /api/goals/{id}/approve`: pending_approval→approved (manager only), emit `goal_approved`, 403/400 guards
    - `PATCH /api/goals/{id}/reject`: pending_approval→rejected (manager only), emit `goal_rejected`, note required
    - `PATCH /api/goals/{id}/progress`: update progress + health, emit `progress_updated`, validate [0,100] and health enum
    - _Requirements: 2.1–2.7, 3.1–3.6, 4.1–4.4, 17.1–17.5, 18.1–18.2_

  - [ ]* 2.7 Write property test — Property 4: goal state machine valid transitions only
    - Generate random sequences of transition attempts from each state
    - Assert only transitions in `VALID_TRANSITIONS` dict are accepted; all others raise HTTP 400
    - **Property 4: Goal state machine — valid transitions only**
    - **Validates: Requirements 3.1**

  - [x] 2.8 Implement WebSocket Manager and real-time broadcast
    - Write `backend/app/services/websocket_manager.py`: `connect`, `disconnect`, `broadcast` procedures
    - Wire `/ws/{employee_id}` endpoint to manager in `main.py`
    - Handle `WebSocketDisconnect` silently; clean up empty sets
    - _Requirements: 7.5, 7.6, 14.1–14.4_

  - [x] 2.9 Build Timeline UI — infinite scroll, filter pills, WebSocket live updates
    - Write `frontend/src/hooks/useEmployeeTimeline.ts`: `useInfiniteQuery` + WebSocket subscription with optimistic prepend
    - Write `frontend/src/components/Timeline/TimelineEventCard.tsx`: displays `event_type` badge, `created_at` via `date-fns`, payload summary
    - Write `frontend/src/components/Timeline/TimelineFilterPills.tsx`: one pill per EventType; on click reset offset and re-fetch
    - Wire into `EmployeeTimelinePage` with infinite scroll trigger on scroll-to-bottom
    - _Requirements: 14.5, 15.1–15.5_

  - [x] 2.10 Checkpoint — Core flow complete
    - Create a goal as Alex, submit for approval, approve as Riya
    - Verify `timeline_events` contains `goal_created`, `goal_submitted`, `goal_approved` rows
    - Verify Timeline UI shows events in real time via WebSocket
    - Ask the user if any adjustments are needed before proceeding.

- [ ] 3. Phase 3 — Review Magic: Review Page, Goal-Weighted Score, AI Draft via Celery
  - [x] 3.1 Set up Celery app and Redis connection
    - Write `backend/app/tasks/celery_app.py`: configure broker/backend from env, `CELERY_TASK_ALWAYS_EAGER` toggle for tests
    - _Requirements: 12.1_

  - [~] 3.2 Implement `generate_review_draft` Celery task
    - Write `backend/app/tasks/review_tasks.py`: fetch review, goals, events (ordered ASC); call `build_review_prompt`; call OpenAI `gpt-4o-mini`; set `ai_draft_text` + `status=in_progress`; broadcast `draft_ready`; `db.rollback()` in `finally`; retry 3× with 30s countdown
    - Write `build_review_prompt(goals, events)` helper in same module
    - _Requirements: 12.1–12.6, 18.4–18.6_

  - [~] 3.3 Implement Reviews router — lifecycle and draft generation endpoint
    - Write `backend/app/routers/reviews.py`
    - `POST /api/reviews`: create review (status=draft)
    - `GET /api/reviews/{id}`: return ReviewRead
    - `POST /api/reviews/{review_id}/generate-draft`: enqueue task, store `ai_task_id`, return 202 with task_id
    - `PATCH /api/reviews/{review_id}/calibrate`: persist `manager_override`, `calibration_notes`, `final_rating` [1–5], transition to `calibrated`, emit calibration timeline event
    - `PATCH /api/reviews/{review_id}/comments`: update `manager_comments` only (preserve `ai_draft_text`)
    - _Requirements: 12.1, 13.1–13.5_

  - [ ]* 3.4 Write property test — Property 6: ai_draft_text only set after successful task
    - Generate reviews in various states; assert `ai_draft_text IS NOT NULL` implies `ai_task_id IS NOT NULL` and status in allowed set
    - **Property 6: AI draft only set after Celery task completion**
    - **Validates: Requirements 12.5**

  - [~] 3.5 Build Review split-screen UI — draft editor, Evidence Board, calibration panel
    - Write `frontend/src/hooks/useReview.ts`: fetch review, poll/WebSocket for `draft_ready` and `draft_failed` events
    - Write `frontend/src/components/ReviewSplitView/AIDraftPanel.tsx`: show `ai_draft_text` (read-only), `manager_comments` editable textarea, "Generate Draft" button triggering `POST .../generate-draft`
    - Write `frontend/src/components/ReviewSplitView/EvidenceBoard.tsx`: list timeline events where `is_evidence=true` and `linked_goal_id` matches selected goal
    - Write `frontend/src/components/ReviewSplitView/CalibrationPanel.tsx`: Radix slider 1–5 for `final_rating`, override and notes inputs, submit → `PATCH .../calibrate`
    - _Requirements: 8.4, 12.3, 12.4, 13.2, 13.3, 13.5_

  - [~] 3.6 Implement evidence tagging endpoint and UI control
    - Add `POST /api/timeline/events/{event_id}/tag-evidence` to timeline router: set `is_evidence=true`, insert `evidence_tagged` event, enforce cross-employee 403 and goal 404
    - Add "Pin as Evidence" button to `TimelineEventCard` that calls the endpoint
    - _Requirements: 8.1–8.5_

  - [~] 3.7 Implement peer feedback and anonymous feedback submission
    - Add `POST /api/timeline/feedback` endpoint: validate `text` non-empty, set `from_user_id=null` when `is_anonymous=true`, enqueue async sentiment analysis task
    - Write `backend/app/tasks/review_tasks.py` sentiment task: call OpenAI, clamp score to [-1,1], JSONB patch only `sentiment_score` key
    - Add Feedback form component in frontend with anonymous toggle
    - _Requirements: 9.1–9.4, 10.1–10.4_

  - [ ]* 3.8 Write property test — Property 8: sentiment score always in [-1.0, 1.0]
    - Generate arbitrary sentiment score floats; assert clamping logic keeps value in `[-1.0, 1.0]`
    - **Property 8: Sentiment score bounds**
    - **Validates: Requirements 10.2**

  - [~] 3.9 Checkpoint — Review magic complete
    - Trigger AI draft generation end-to-end; confirm `draft_ready` WebSocket fires and UI updates
    - Tag an evidence event; confirm it appears on Evidence Board
    - Submit a calibration; confirm timeline event is created with manager ID and final rating
    - Ask the user if any adjustments are needed before proceeding.

- [ ] 4. Phase 4 — Advanced UI/UX: React Flow Goal Cascade, WebSocket Polish, Tailwind
  - [~] 4.1 Implement Goal Cascade Tree with React Flow
    - Write `frontend/src/components/GoalCascadeTree/GoalCascadeTree.tsx`
    - Call `GET /api/goals?employee_id=` to get flat goal list; call `build_goal_tree` equivalent in frontend or use the backend `/api/goals/tree` endpoint
    - Implement `buildFlowNodes(goals)` per the design: traverse recursively, assign x/y positions
    - Custom `goalNode` type showing title, progress percentage, health status badge (colour-coded by `GoalHealth`)
    - _Requirements: 6.1–6.4_

  - [~] 4.2 Add `/api/goals/tree` backend endpoint
    - Add `GET /api/goals/tree?employee_id=` to goals router; call `build_goal_tree` and return nested `GoalRead` list
    - _Requirements: 6.1, 6.2_

  - [~] 4.3 Polish WebSocket reconnection and real-time review status updates
    - Update `useEmployeeTimeline.ts` to reconnect automatically on close/error using exponential backoff
    - Update `useReview.ts` to subscribe to `review_id` WebSocket channel; handle `draft_ready` (show draft) and `draft_failed` (show retry button)
    - _Requirements: 14.1–14.5_

  - [~] 4.4 Build Goals management page with approval workflow UI
    - Write `GoalsPage.tsx` listing goals in a table with status badges and action buttons contextual to role
    - Employee: "Submit for Approval" button on draft goals, progress slider + health selector on approved goals
    - Manager: "Approve" / "Reject" buttons on pending_approval goals, rejection note modal
    - Show computed `Performance Score` for the selected employee
    - _Requirements: 3.1–3.6, 4.1–4.4, 5.1–5.2_

  - [~] 4.5 Apply Tailwind polish and navigation shell
    - Implement top navigation bar with `RoleSwitcher` dropdown and active-user avatar
    - Apply consistent Tailwind colour palette: health badges (`on_track` = green, `at_risk` = amber, `off_track` = red), status badges for goal and review states
    - Ensure responsive layout for Timeline, Goals, and Review pages
    - _Requirements: 15.5_

  - [~] 4.6 Checkpoint — Advanced UI/UX complete
    - Verify React Flow goal cascade renders correctly with parent→child edges
    - Verify WebSocket reconnects after server restart
    - Verify all three role views show correct action sets
    - Ask the user if any adjustments are needed before proceeding.

- [ ] 5. Phase 5 — Testing & Correctness: All 8 Properties, Integration Tests, Seed Data
  - [~] 5.1 Write property test — Property 1: timeline immutability (append-only trigger)
    - Write test that attempts `UPDATE timeline_events SET payload = ...` via SQLAlchemy raw SQL against a test DB
    - Assert a `sqlalchemy.exc.DBAPIError` (or subclass) is raised containing the trigger message
    - **Property 1: Timeline immutability**
    - **Validates: Requirements 7.1**

  - [ ]* 5.2 Write property test — Property 5: every goal state transition has a corresponding timeline event
    - Use `hypothesis` to generate sequences of valid state transitions for a goal
    - After each transition, assert the `timeline_events` table contains the matching event type for the goal
    - **Property 5: Every goal state transition has a corresponding timeline event**
    - **Validates: Requirements 17.1–17.3**

  - [ ]* 5.3 Write property test — Property 7: evidence tags always reference valid events and goals
    - Generate collections of evidence-tagged events; assert every `is_evidence=True` event has a non-null `linked_goal_id` that exists in the goals set
    - **Property 7: Evidence tags always reference valid events**
    - **Validates: Requirements 8.5**

  - [~] 5.4 Write integration test — goal creation round-trip
    - Use `httpx.AsyncClient` with `ASGI` transport against the FastAPI app
    - `POST /api/goals` → assert 201, verify `timeline_events` row with `event_type=goal_created` exists for the new goal
    - _Requirements: 2.2_

  - [ ]* 5.5 Write integration test — WebSocket broadcast on timeline event
    - Connect a test WebSocket client to `/ws/{employee_id}`
    - `POST /api/timeline/events` for that employee
    - Assert the WS client receives the serialised event JSON before the HTTP response check completes
    - _Requirements: 7.5_

  - [ ]* 5.6 Write integration test — Celery `generate_review_draft` in eager mode
    - Set `CELERY_TASK_ALWAYS_EAGER=True`; stub OpenAI response with a fixed string
    - Call `POST /api/reviews/{review_id}/generate-draft`; poll or await task result
    - Assert `review.ai_draft_text` is the stub string and `review.status == in_progress`
    - _Requirements: 12.2, 12.3_

  - [ ]* 5.7 Write integration test — append-only trigger via API
    - Attempt to call a hypothetical internal path that would issue UPDATE on `timeline_events`
    - Assert the operation is rejected at the DB layer
    - _Requirements: 7.1_

  - [~] 5.8 Enrich seed data for demo flow
    - Extend `backend/seed.py` with: three approved goals for Alex (weights summing to 0.9), two progress updates, one check-in event, one peer feedback (anonymous), one review record in `in_progress` with a pre-populated `ai_draft_text`
    - Add a parent goal and one child goal to seed Alex's cascade tree
    - _Requirements: 1.1, 6.1_

  - [~] 5.9 Final checkpoint — all tests pass
    - Run `pytest backend/tests/ --tb=short` and confirm all tests pass
    - Run `docker compose up` with fresh volumes; confirm seed data loads and full demo flow is exercisable
    - Ask the user if any remaining issues need addressing.

## Notes

- Tasks marked with `*` are optional and can be skipped for a faster MVP — but property tests directly validate the 8 correctness properties from the design, so they are strongly recommended before demo
- Each task references specific requirements for traceability
- Checkpoints end each phase to validate incremental progress before moving forward
- `CELERY_TASK_ALWAYS_EAGER=True` makes Celery tasks run synchronously in tests — no live broker needed
- The append-only trigger (task 1.4) must land before any timeline tests or integration tests run
- All eight correctness properties from the design are covered: Properties 1–8 map to tasks 5.1, 2.5, 2.4, 2.7, 5.2, 3.4, 5.3, 3.8 respectively

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1"] },
    { "id": 1, "tasks": ["1.2", "1.8"] },
    { "id": 2, "tasks": ["1.3"] },
    { "id": 3, "tasks": ["1.4", "1.5"] },
    { "id": 4, "tasks": ["1.6", "1.7"] },
    { "id": 5, "tasks": ["2.1", "2.3", "3.1"] },
    { "id": 6, "tasks": ["2.2", "2.6", "2.8"] },
    { "id": 7, "tasks": ["2.4", "2.5", "2.7", "2.9"] },
    { "id": 8, "tasks": ["3.2", "3.3"] },
    { "id": 9, "tasks": ["3.4", "3.5", "3.6", "3.7"] },
    { "id": 10, "tasks": ["3.8", "4.2"] },
    { "id": 11, "tasks": ["4.1", "4.3", "4.4"] },
    { "id": 12, "tasks": ["4.5"] },
    { "id": 13, "tasks": ["5.1", "5.4", "5.8"] },
    { "id": 14, "tasks": ["5.2", "5.3", "5.5", "5.6", "5.7"] }
  ]
}
```
