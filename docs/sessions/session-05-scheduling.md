# Session 05 — Scheduling & Email Delivery

## Goal
Allow users to schedule recurring analysis runs (e.g. "every Monday at 08:00, analyse the last
7 days") and receive the result as an email.

## Prerequisite
Session 04 completed and merged.

## Scope
- `Schedule` model + Alembic migration
- Celery Beat for cron scheduling (schedule stored in DB via `django-celery-beat` alternative:
  `celery-sqlalchemy-scheduler` or simple custom approach polling DB every minute)
- `Schedule` CRUD endpoints:
  - `POST   /api/schedules` — create schedule (analysis_id, cron, time_window, recipient_email)
  - `GET    /api/schedules` — list schedules
  - `PATCH  /api/schedules/{id}` — update / toggle active
  - `DELETE /api/schedules/{id}` — delete schedule
- Celery task `run_scheduled_analysis`: fetch history for time window → AI → send email
- Email service using `aiosmtplib` (SMTP config from env vars)
- Email template (plain text + minimal HTML) with analysis result
- Frontend: schedule management page

## Acceptance Criteria
- User can create a schedule with a cron expression and time window
- Celery worker picks up due schedules and executes the analysis
- On completion an email is sent to the configured recipient
- `analysis_runs` row is created with status `completed` or `failed`
- Failed runs record the error message; no silent failures
- Email service tested with a mock SMTP server
- Schedule ownership enforced (users can only see/edit their own schedules)

## Out of Scope
- Push notifications
- Slack/webhook delivery (can be added later as a `NotificationChannel` abstraction)

## Key Files to Create / Modify

```
backend/
  app/models/schedule.py
  app/schemas/schedule.py
  app/routers/schedules.py
  app/services/email_service.py
  app/services/schedule_service.py
  app/tasks/analysis_tasks.py      # Celery task
  app/tasks/scheduler.py           # beat schedule loader
  tests/test_schedules.py
  tests/test_email.py

alembic/versions/<timestamp>_add_schedules.py

frontend/
  src/pages/SchedulesPage.tsx
  src/components/ScheduleCard.tsx
  src/components/CronEditor.tsx    # human-friendly cron builder
  src/services/scheduleApi.ts
```
