# Deploying on Render

One Render web service runs all three apps behind nginx:

| App | Address |
|---|---|
| Patient | `https://<service>.onrender.com/` |
| Doctor | `https://<service>.onrender.com/doctor/` |
| Administration | `https://<service>.onrender.com/admin/` |
| Public account deletion (Google Play) | `https://<service>.onrender.com/?account=delete` |

Files: `render.yaml` (Blueprint), `Dockerfile`, `deploy/render-start.sh`, `deploy/nginx-render.conf`.

## Settings
- `PERDIA_ADMIN_PASSWORD` (required): the admin password. Set it in Render, never in the repository.
- `PERDIA_DATA_DIR`: where accounts, reports, databases and photos are written (`/var/data`).

## Free plan limits (testing only)
- No persistent disk: all data is deleted on every restart, redeploy or wake-up.
- The service sleeps when idle; the first visit after that is slow.
- 512 MB of memory for three apps is tight; if the logs show the service running out of memory, use a paid instance type.

## Keeping data (real use)
Change `plan` in `render.yaml` (or in the Render dashboard) to a paid instance type, 2 GB RAM recommended, and enable the `disk` block mounted at `/var/data`. A disk belongs to one service only, which is why the three apps run in one service. Adding a disk means a few seconds of downtime on each deploy.
