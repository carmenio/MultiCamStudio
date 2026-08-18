# Task queue schema compatibility

`TaskDatabase` requires the dependency and cancellation fields introduced by
`pc/infra/supabase/migrations/20260815000000_add_task_dependencies_and_cancel_request.sql`.
Apply pending Supabase migrations before deploying backend code that queues task chains.

The characteristic drift error is PostgREST `PGRST204` reporting that
`depends_on_task_id` is absent from `task_jobs`. Do not remove task dependencies or
silently retry without the field. Apply the additive migration, notify PostgREST to
reload its schema, and restart `backend` plus `task-worker`.

Verify the live contract with:

```sql
select column_name
from information_schema.columns
where table_schema = 'public'
  and table_name = 'task_jobs'
  and column_name in ('depends_on_task_id', 'cancel_requested_at', 'cancel_reason');
```
