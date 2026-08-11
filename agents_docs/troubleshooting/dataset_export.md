# Dataset export troubleshooting

## Export routes return HTML 404

The PC backend and task worker bind-mount `pc/services/backend` into their containers, but their Python processes do not reload when those files change. If a newly added export route such as `POST /api/exports/preflight` returns Flask's HTML `404 Not Found`, or the worker does not recognize `export_dataset`, first confirm that no tasks are active and restart both processes from `pc/`:

```powershell
docker compose restart backend task-worker
```

Restarting only the backend can restore the HTTP route while leaving the task worker unable to execute the submitted export. After both services restart, verify that an empty preflight request returns structured JSON validation rather than HTML 404, and confirm the worker startup log lists `export_dataset` among its registered handlers. A rebuild is unnecessary when only bind-mounted Python source changed.
