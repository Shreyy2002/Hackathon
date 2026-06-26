# Requirements Document

## Introduction

The Event-Sourced Performance Ledger is a hackathon-grade performance management system that replaces conventional CRUD-based approaches with an append-only event log as the authoritative system of record. Every meaningful action — goal creation, progress update, peer feedback, check-in, review — is stored as an immutable `TimelineEvent`. Current entity state is derived by replaying events, producing a full audit trail, a rich employee timeline UI, and a natural data source for AI-generated review drafts.

The system is structured as a modular monolith with four bounded contexts: `Identity`, `Goals`, `Timeline`, and `Reviews`. A React frontend communicates with a single FastAPI async backend. Real-time updates are delivered via WebSockets. AI review drafting is offloaded to Celery workers backed by the OpenAI gpt-4o-mini model.

---

## Glossary

- **System**: The Event-Sourced Performance Ledger as a whole.
- **Identity_Context**: The bounded context responsible for user resolution and role switching.
- **Goals_Context**: The bounded context responsible for goal lifecycle management, weight validation, and the goal cascade tree.
- **Timeline_Context**: The bounded context responsible for the append-only event log, evidence tagging, and real-time broadcast.
- **Reviews_Context**: The bounded context responsible for performance review lifecycle, AI draft generation, and calibration.
- **Goal_Weight_Engine**: The component inside the Goals_Context that computes weighted performance scores.
- **TimelineEvent**: An immutable, append-only record of a meaningful action, stored in the `timeline_events` table.
- **Evidence**: A `TimelineEvent` that has been tagged as supporting evidence for a specific goal.
- **WebSocket_Manager**: The in-process component that tracks active WebSocket connections and fans out broadcast messages.
- **Celery_Worker**: An asynchronous background process that executes long-running tasks such as AI draft generation.
- **Review_Draft**: An AI-generated text summary stored in the `ai_draft_text` field of a review record.
- **Calibration**: The process by which a manager adds override commentary and a final numeric rating to a submitted review.
- **Goal_Cascade_Tree**: A hierarchical visualisation of parent–child goal relationships rendered with React Flow.
- **Sentiment_Score**: A float in `[-1.0, 1.0]` computed asynchronously from feedback text via the OpenAI API.
- **Performance_Score**: The result of `compute_performance_score` — a `Decimal` in `[0.00, 100.00]` representing weighted goal completion.
- **Employee**: A user with role `employee`.
- **Manager**: A user with role `manager`.
- **HR_Admin**: A user with role `hr`.
- **Cycle_Name**: A string identifier for a performance review period (e.g. "H1 2025").

---

## Requirements

### Requirement 1: Identity and Role Switching

**User Story:** As a demo user, I want to switch between the three hardcoded personas (Riya, Alex, HR Admin), so that I can experience the system from each role's perspective without needing real authentication.

#### Acceptance Criteria

1. THE Identity_Context SHALL seed exactly three users on startup: Riya (Manager), Alex (Employee), and an HR Admin user.
2. WHEN a valid `user_id` is posted to `POST /api/auth/switch-role`, THE Identity_Context SHALL set the `X-Current-User` session cookie to that user's identifier.
3. IF an invalid or unknown `user_id` is posted to `POST /api/auth/switch-role`, THEN THE Identity_Context SHALL return HTTP 404.
4. WHEN `GET /api/employees/{id}/profile` is called, THE Identity_Context SHALL return a single response containing the user record, all goals, and the twenty most recent timeline events for that employee.
5. THE Identity_Context SHALL inject the current user context into every bounded context via dependency injection, so that downstream services can determine the acting user without additional database queries.

---

### Requirement 2: Goal Creation and Weight Validation

**User Story:** As an employee, I want to create goals with weights that represent their relative importance, so that my performance score accurately reflects how I prioritise my work.

#### Acceptance Criteria

1. WHEN a `GoalCreate` request is received, THE Goals_Context SHALL reject the request with HTTP 400 if adding the new goal's weight would cause the employee's total goal weight to exceed `1.0`.
2. WHEN a goal is successfully created, THE Goals_Context SHALL insert a `goal_created` timeline event linked to that goal.
3. WHEN a goal is successfully created, THE Goals_Context SHALL set the initial status to `draft`, progress to `0`, and health to `on_track`.
4. THE Goals_Context SHALL accept a `parent_goal_id` on goal creation and store the parent–child relationship for cascade tree rendering.
5. IF a `parent_goal_id` is provided that does not reference an existing goal owned by the same employee, THEN THE Goals_Context SHALL return HTTP 404.
6. THE Goals_Context SHALL constrain the `progress` field to the integer range `[0, 100]` and reject values outside this range with HTTP 422.
7. THE Goals_Context SHALL constrain the `weight` field to a positive `Decimal` value and reject zero or negative weights with HTTP 422.

---

### Requirement 3: Goal Lifecycle and State Machine

**User Story:** As an employee and manager, I want goals to follow a defined approval workflow, so that only manager-reviewed goals contribute to performance scores.

#### Acceptance Criteria

1. THE Goals_Context SHALL enforce the following valid state transitions and reject all others with HTTP 400:
   - `draft` → `pending_approval` (employee submits)
   - `pending_approval` → `approved` (manager approves)
   - `pending_approval` → `rejected` (manager rejects)
   - `rejected` → `draft` (employee revises and resubmits)
2. WHEN a goal transitions to `pending_approval`, THE Goals_Context SHALL insert a `goal_submitted` timeline event.
3. WHEN a goal transitions to `approved`, THE Goals_Context SHALL insert a `goal_approved` timeline event containing the goal ID, title, and optional approval note.
4. WHEN a goal transitions to `rejected`, THE Goals_Context SHALL insert a `goal_rejected` timeline event containing the goal ID, title, and rejection note.
5. IF a user with role other than `manager` attempts to approve or reject a goal, THEN THE Goals_Context SHALL return HTTP 403.
6. WHEN a goal reaches the `approved` or `rejected` terminal states, THE Goals_Context SHALL not allow the status to revert to `draft` or `pending_approval` (except `rejected` → `draft` per rule 3.1).

---

### Requirement 4: Goal Progress Updates and Health Flags

**User Story:** As an employee, I want to update my goal's progress percentage and health status, so that stakeholders can see whether I am on track.

#### Acceptance Criteria

1. WHEN a progress update is submitted for an approved goal, THE Goals_Context SHALL update the goal's `progress` and `health` fields and insert a `progress_updated` timeline event.
2. THE `progress_updated` event payload SHALL include `previous_progress`, `new_progress`, `previous_health`, `new_health`, and an optional `note`.
3. THE Goals_Context SHALL reject progress updates with values outside `[0, 100]` with HTTP 422.
4. THE Goals_Context SHALL accept one of the three health values — `on_track`, `at_risk`, `off_track` — and reject any other value with HTTP 422.

---

### Requirement 5: Goal Weighting and Performance Score Computation

**User Story:** As a manager, I want the system to compute a weighted performance score for each employee, so that I can objectively compare contributions across different goal priorities.

#### Acceptance Criteria

1. THE Goal_Weight_Engine SHALL compute the performance score as the weighted sum of `(progress × weight)` across all `approved` goals, normalised by the total allocated weight of those goals.
2. THE Goal_Weight_Engine SHALL return `0.0` when an employee has no approved goals.
3. FOR ALL valid inputs to `compute_performance_score`, THE Goal_Weight_Engine SHALL return a `Decimal` in the closed range `[0.00, 100.00]`.
4. THE Goal_Weight_Engine SHALL NOT mutate any goal object during score computation.
5. THE Goals_Context SHALL guarantee that the sum of weights across all of an employee's goals at any point in time is less than or equal to `1.0`.

---

### Requirement 6: Goal Cascade Tree

**User Story:** As a manager, I want to view goals in a parent–child hierarchy using a React Flow tree, so that I can understand how strategic objectives cascade down to individual tasks.

#### Acceptance Criteria

1. WHEN `build_goal_tree` is called with a flat list of goals for one employee, THE Goals_Context SHALL return only root goals (those with `parent_goal_id` equal to `NULL`), with child goals recursively nested under their parents.
2. THE Goals_Context SHALL silently drop orphaned goals (goals whose `parent_goal_id` references a non-existent goal) from the tree output.
3. THE Goals_Context SHALL NOT include circular parent–child references; the database SHALL enforce this via a constraint.
4. WHEN the Goal_Cascade_Tree is rendered, THE System SHALL display each node with the goal title, progress percentage, and health status.

---

### Requirement 7: Timeline — Append-Only Event Log

**User Story:** As an auditor or manager, I want every meaningful action to be recorded as an immutable event, so that I can reconstruct the full history of any employee's performance.

#### Acceptance Criteria

1. THE Timeline_Context SHALL enforce append-only semantics: no `UPDATE` or `DELETE` statement targeting the `timeline_events` table SHALL succeed; the database SHALL raise an exception via a trigger.
2. WHEN `append_event` is called, THE Timeline_Context SHALL insert a new row into `timeline_events` with a server-generated `created_at` timestamp without modifying any existing rows.
3. WHEN `append_event` is called, THE Timeline_Context SHALL NOT commit the transaction immediately, so that the caller can atomically write multiple events in one transaction.
4. THE Timeline_Context SHALL return paginated, filterable timeline events ordered by `created_at DESC`, supporting `offset` and `limit` query parameters and an optional `event_type` filter.
5. WHEN a new timeline event is committed, THE Timeline_Context SHALL broadcast the serialised event to all active WebSocket connections subscribed to the relevant `employee_id`.
6. IF a WebSocket client disconnects during a broadcast, THEN THE WebSocket_Manager SHALL silently catch the disconnect, remove the dead socket from the connection set, and continue broadcasting to remaining subscribers.
7. THE `timeline_events` table SHALL index `(employee_id, created_at DESC)` to support efficient paginated timeline queries.
8. THE `timeline_events` table SHALL index `event_type` to support efficient filtered timeline queries.

---

### Requirement 8: Evidence Tagging

**User Story:** As an employee or manager, I want to tag existing timeline events as evidence for specific goals, so that the review process can reference concrete accomplishments.

#### Acceptance Criteria

1. WHEN an evidence tag request is received, THE Timeline_Context SHALL set `is_evidence = true` on the specified timeline event and insert an `evidence_tagged` event recording the `source_event_id`, `goal_id`, and `tagged_by` fields.
2. IF the timeline event referenced in an evidence tag request belongs to a different employee than the goal, THEN THE Timeline_Context SHALL return HTTP 403.
3. IF the goal referenced in an evidence tag request does not exist, THEN THE Timeline_Context SHALL return HTTP 404.
4. THE Evidence Board in the Review split-screen SHALL display all timeline events where `is_evidence = true` and `linked_goal_id` matches the selected goal.
5. FOR ALL timeline events where `is_evidence = true`, THE Timeline_Context SHALL ensure `linked_goal_id` is non-null and references an existing goal.

---

### Requirement 9: Peer Feedback and Anonymous Feedback

**User Story:** As an employee, I want to submit peer feedback — optionally anonymously — so that colleagues receive candid and useful performance input.

#### Acceptance Criteria

1. WHEN a `feedback` or `peer_review` timeline event is created with `is_anonymous = false`, THE Timeline_Context SHALL include the `from_user_id` in the stored JSONB payload.
2. WHEN a `feedback` or `peer_review` timeline event is created with `is_anonymous = true`, THE Timeline_Context SHALL store `from_user_id` as `null` in the payload so that the submitter's identity cannot be derived from the event record.
3. WHEN a `feedback` or `peer_review` event is committed, THE System SHALL enqueue an asynchronous sentiment analysis task to compute and store the `sentiment_score` in the event's JSONB payload.
4. THE Timeline_Context SHALL accept `feedback` and `peer_review` events containing a non-empty `text` field and reject empty text with HTTP 422.

---

### Requirement 10: Sentiment Analysis

**User Story:** As an HR admin, I want feedback events to be automatically enriched with a sentiment score, so that review summaries can surface emotional tone patterns.

#### Acceptance Criteria

1. WHEN the sentiment analysis task completes, THE System SHALL update the `sentiment_score` field in the relevant `timeline_events` JSONB payload to a `float` value.
2. THE sentiment analysis task SHALL produce a `sentiment_score` in the closed range `[-1.0, 1.0]`; any value outside this range SHALL be clamped or rejected before storage.
3. WHEN the sentiment analysis task is the sole exception to the append-only rule (JSONB payload enrichment), THE System SHALL only modify the `sentiment_score` key and SHALL NOT alter any other fields in the payload.
4. IF the OpenAI API call for sentiment analysis fails, THEN THE System SHALL not store a partial or invalid sentiment score and the event SHALL remain without a `sentiment_score` key.

---

### Requirement 11: Check-In Events

**User Story:** As a manager, I want to record structured check-in meeting notes as timeline events, so that there is a traceable history of one-on-one discussions and agreed action items.

#### Acceptance Criteria

1. WHEN a `check_in` timeline event is created, THE Timeline_Context SHALL validate that the payload includes a non-empty `meeting_date` (ISO 8601 date string), a non-empty `notes` string, and an `action_items` list.
2. THE Timeline_Context SHALL reject a `check_in` event with a missing or malformed `meeting_date` with HTTP 422.
3. THE Timeline_Context SHALL accept an empty `action_items` list as valid for check-in events.

---

### Requirement 12: AI-Powered Review Draft Generation

**User Story:** As a manager, I want the system to generate a draft performance review using AI, so that I can start from a data-grounded summary rather than a blank page.

#### Acceptance Criteria

1. WHEN `POST /api/reviews/{review_id}/generate-draft` is called, THE Reviews_Context SHALL enqueue a `generate_review_draft` Celery task, store the Celery `task_id` in the review record, and return HTTP 202 with the `task_id`.
2. WHEN the `generate_review_draft` task executes, THE Reviews_Context SHALL fetch the employee's goals and all timeline events ordered by `created_at ASC` and pass them to the prompt builder.
3. WHEN the Celery task completes successfully, THE Reviews_Context SHALL set `ai_draft_text` to the non-empty string returned by OpenAI, transition `review.status` to `in_progress`, and broadcast a `draft_ready` WebSocket event to the `review_id` channel.
4. IF the Celery task fails after three retry attempts, THEN THE Reviews_Context SHALL leave `review.ai_draft_text` and `review.status` unchanged and broadcast a `{"type": "draft_failed", "review_id": "..."}` WebSocket event.
5. THE `ai_draft_text` field SHALL be null unless a `generate_review_draft` task has completed successfully for that review.
6. THE Celery task SHALL be idempotent: re-running `generate_review_draft` with the same `review_id` SHALL overwrite `ai_draft_text` without creating duplicate records.

---

### Requirement 13: Review Lifecycle and Calibration

**User Story:** As a manager, I want to calibrate an employee's performance review with override notes and a final numeric rating, so that the review reflects both AI-generated insights and my professional judgement.

#### Acceptance Criteria

1. THE Reviews_Context SHALL enforce the following review status transitions: `draft` → `in_progress` → `submitted` → `calibrated`.
2. WHEN a calibration update is submitted, THE Reviews_Context SHALL persist `manager_override`, `calibration_notes`, and `final_rating` and transition the review status to `calibrated`.
3. THE Reviews_Context SHALL constrain `final_rating` to the integer range `[1, 5]` and reject values outside this range with HTTP 422.
4. WHEN calibration is applied, THE Reviews_Context SHALL insert a timeline event to create an audit trail of the calibration action, including the manager ID and the final rating.
5. THE Reviews_Context SHALL allow a manager to edit `manager_comments` independently of the `ai_draft_text`, so that the AI output is preserved as a reference while the manager's final narrative is stored separately.

---

### Requirement 14: Real-Time WebSocket Updates

**User Story:** As a frontend user, I want the timeline and review screens to update in real time without polling, so that I see other users' actions immediately.

#### Acceptance Criteria

1. WHEN a WebSocket client connects to `ws://…/ws/{employee_id}`, THE WebSocket_Manager SHALL register the socket in the in-memory connection map keyed by `employee_id`.
2. WHEN a client disconnects, THE WebSocket_Manager SHALL remove the socket from the connection map and clean up the entry if the set becomes empty.
3. WHEN `broadcast(employee_id, message)` is called and no subscribers exist for that `employee_id`, THE WebSocket_Manager SHALL silently return without error.
4. WHEN a new timeline event is committed for an employee, THE WebSocket_Manager SHALL deliver the serialised event JSON to every connected WebSocket subscriber for that `employee_id` before the HTTP response is returned.
5. WHEN the frontend receives a WebSocket message, THE Timeline_UI SHALL optimistically prepend the new event to the cached timeline without requiring a full page refresh.

---

### Requirement 15: Timeline UI — Infinite Scroll and Filtering

**User Story:** As an employee or manager, I want to browse the complete event history with infinite scroll and filter by event type, so that I can quickly locate specific events.

#### Acceptance Criteria

1. THE Timeline_UI SHALL render events in descending chronological order, showing the most recent event at the top.
2. WHEN the user scrolls to the bottom of the visible timeline, THE Timeline_UI SHALL fetch the next page of events using `offset`-based pagination with a page size of 20.
3. THE Timeline_UI SHALL provide filter pills for each `EventType` so users can restrict the visible events to a specific type.
4. WHEN a filter pill is activated, THE Timeline_UI SHALL reset the page offset to zero and re-fetch the timeline with the `event_type` filter applied.
5. THE Timeline_UI SHALL display each event with its `event_type` label, `created_at` timestamp (formatted by `date-fns`), and a human-readable summary of the `payload`.

---

### Requirement 16: JSONB Payload Schemas

**User Story:** As a developer, I want every event type to have a validated JSONB payload schema, so that downstream consumers (AI prompts, UI renderers) can reliably deserialise event data.

#### Acceptance Criteria

1. THE Timeline_Context SHALL validate `goal_created`, `goal_submitted`, `goal_approved`, and `goal_rejected` event payloads to contain `goal_id` (UUID string), `title` (non-empty string), `status` (valid `GoalStatus` string), and optional `note`.
2. THE Timeline_Context SHALL validate `progress_updated` event payloads to contain `goal_id`, `previous_progress` (`int` in `[0, 100]`), `new_progress` (`int` in `[0, 100]`), `previous_health`, `new_health`, and optional `note`.
3. THE Timeline_Context SHALL validate `feedback` and `peer_review` event payloads to contain `text` (non-empty string), `is_anonymous` (`bool`), and, when `is_anonymous = false`, a non-null `from_user_id`.
4. THE Timeline_Context SHALL validate `achievement` event payloads to contain `title` (non-empty string), `description` (non-empty string), and optional `linked_goal_id`.
5. THE Timeline_Context SHALL validate `check_in` event payloads to contain `meeting_date` (ISO 8601 date), `notes` (non-empty string), and `action_items` (list of strings, may be empty).
6. THE Timeline_Context SHALL validate `evidence_tagged` event payloads to contain `source_event_id` (UUID string), `goal_id` (UUID string), and `tagged_by` (UUID string).
7. IF any required payload field is absent or of the wrong type, THEN THE Timeline_Context SHALL return HTTP 422 and SHALL NOT insert the event.

---

### Requirement 17: Audit Trail Completeness

**User Story:** As an auditor, I want every significant state change to be traceable in the timeline, so that I can reconstruct the full decision history for any employee.

#### Acceptance Criteria

1. FOR EVERY goal that reaches `approved` status, THE Timeline_Context SHALL contain at least one `goal_approved` event with a matching `linked_goal_id`.
2. FOR EVERY goal that reaches `rejected` status, THE Timeline_Context SHALL contain at least one `goal_rejected` event with a matching `linked_goal_id`.
3. FOR EVERY goal that reaches `pending_approval` status, THE Timeline_Context SHALL contain at least one `goal_submitted` event with a matching `linked_goal_id`.
4. WHEN calibration is applied to a review, THE Timeline_Context SHALL contain a timeline event recording the calibration action, the manager ID, and the final rating.
5. THE Timeline_Context SHALL record the `actor_id` on every timeline event so that the acting user can be identified for each state change.

---

### Requirement 18: Error Handling and Data Integrity

**User Story:** As a developer, I want all error scenarios to return well-defined HTTP responses and leave the system in a consistent state, so that the frontend can guide users to recovery actions.

#### Acceptance Criteria

1. IF a goal creation request would cause the total weight to exceed `1.0`, THEN THE Goals_Context SHALL return HTTP 400 with a message of the form `"Total goal weight would exceed 1.0. Current allocated: {current}"`.
2. IF a goal state transition is invalid (e.g. approving a `draft` goal), THEN THE Goals_Context SHALL return HTTP 400 with a descriptive message indicating the current and required state.
3. IF a timeline event is submitted with a `linked_goal_id` that belongs to a different employee, THEN THE Timeline_Context SHALL return HTTP 403.
4. IF a review is not found during draft generation, THEN THE Celery_Worker SHALL raise a `ValueError` and the task SHALL retry up to three times with a 30-second countdown before moving to the dead-letter queue.
5. WHEN any database error occurs during a Celery task, THE Celery_Worker SHALL call `db.rollback()` in the `finally` block before raising the exception to the retry mechanism.
6. IF an OpenAI API timeout occurs during review draft generation, THEN THE Reviews_Context SHALL not update the review record, and the next retry attempt SHALL start with a fresh database session.
