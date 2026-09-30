# Deploying ForceX

This guide puts the ForceX server online on **Render** and connects the desktop app to it.

## Why Render and not Vercel

Vercel runs Python as short-lived serverless functions. ForceX does not fit that model:

| ForceX needs | Vercel | Render |
|---|---|---|
| A disk that keeps the SQLite database and uploaded files | No, the filesystem is wiped after each request | Yes, with a persistent disk |
| Uploads up to 500 MB | No, requests are capped at about 4.5 MB | Yes |
| A background cleanup job that deletes expired shares | No, nothing runs between requests | Yes |

Deploying to Vercel would appear to work, then lose every share. Use Render.

## Cost

| Plan | Price | What happens |
|---|---|---|
| Starter + 1 GB disk | about $7.25 / month | Recommended. Data survives restarts and redeploys. |
| Free | $0 | Works for a demo only. It sleeps after 15 idle minutes, and **all users, shares and files are deleted** on every restart or deploy. |

## 1. Get your own copy of the repository

Render deploys from a repository on **your** GitHub account. Use either:

- the copy the repo owner mirrors to your account (`<your-username>/ForceX`), or
- a fork: open https://github.com/eklavya2201/ForceX and click **Fork**.

## 2. Generate the client key

The server only shows shared content to the desktop app, and the two recognise each other through a shared secret, the **client key**. Generate one on your computer:

```powershell
py -c "import secrets; print(secrets.token_hex(32))"
```

Keep this value. You need it in step 3 and in every copy of the desktop app you hand out.

## 3. Create the service on Render

1. Sign in at https://dashboard.render.com with your GitHub account.
2. Click **New** → **Blueprint**.
3. Choose your ForceX repository. Render reads `render.yaml` and shows one web service, `forcex`, with a 1 GB disk.
4. When asked for `FORCEX_CLIENT_KEY`, paste the key from step 2.
5. Click **Apply**. The first build takes 2–4 minutes.

Render generates `FORCEX_SECRET_KEY` for you. The other settings (database and file paths on the disk, HTTPS cookies, proxy handling) are already in `render.yaml`.

When the build finishes, your site is at `https://forcex-XXXX.onrender.com`. The address is shown at the top of the service page.

### Without the Blueprint (manual setup)

If you prefer **New** → **Web Service**:

| Field | Value |
|---|---|
| Runtime | Python 3 |
| Build command | `pip install -r requirements.txt` |
| Start command | `python run.py` |
| Instance type | Starter |

Then under **Disks**, add a disk with mount path `/var/data` and size 1 GB. Under **Environment**, add:

| Key | Value |
|---|---|
| `PYTHON_VERSION` | `3.12.7` |
| `HOST` | `0.0.0.0` |
| `FORCEX_SECRET_KEY` | a new random value (same command as step 2) |
| `FORCEX_CLIENT_KEY` | the key from step 2 |
| `FORCEX_DB` | `sqlite:////var/data/forcex.db` |
| `FORCEX_STORAGE` | `/var/data/storage` |
| `FORCEX_COOKIE_SECURE` | `1` |
| `FORCEX_BEHIND_PROXY` | `1` |

## 4. Create your sender account, then close registration

1. Open your site and click **Get started** to register.
2. In Render, go to **Environment**, set `FORCEX_ALLOW_REGISTRATION` to `0`, and save. Render redeploys, and nobody else can sign up.

## 5. Build the desktop app for receivers

Receivers can only open share links in the ForceX desktop app. Opening one in Chrome or Edge shows "Open this link in the ForceX app".

Build `ForceX.exe` once, on your own Windows PC, from a copy of the repository:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt -r requirements-desktop.txt pyinstaller
.\.venv\Scripts\python.exe build_desktop.py --url https://forcex-XXXX.onrender.com --key <the key from step 2>
```

The build takes about 5 minutes and produces `dist\ForceX.exe` (about 220 MB). The site address and key are built into it, so receivers need nothing else: they double-click it, paste the share link into the bar at the top, and press Enter.

Send the `.exe` through Google Drive, OneDrive or similar, since it is too large for most email and chat apps. Windows SmartScreen will warn that it is from an unknown publisher, because the file is not code-signed. Receivers click **More info** → **Run anyway**.

To point an existing `.exe` at a different server or key without rebuilding, place a file named `forcex.env` next to it:

```env
FORCEX_URL=https://forcex-XXXX.onrender.com
FORCEX_CLIENT_KEY=<key>
```

The app only works on Windows 10 version 2004 or newer, because it relies on Windows to hide its window from screenshots. On other systems it refuses to start.

## Updating

Every push to the connected branch redeploys automatically. Data on the disk is kept.

## Things to know

- **The client key is a shared secret, not strong protection.** It is inside every copy of `ForceX.exe`, and anyone determined can extract it and use it from a script. It stops casual use of ordinary browsers, not a determined attacker. If it leaks, generate a new one, update it in Render, rebuild the `.exe` and send it out again.
- **Two deployments are two separate sites.** If both of you deploy, each site has its own accounts, shares and files.
- **Nothing stops a phone camera.** The watermark with the share ID and time is there to trace leaked photos.

## Troubleshooting

| Symptom | Fix |
|---|---|
| Build fails on `pip install` | Check that `PYTHON_VERSION` is `3.12.7`. |
| Service crashes with `FORCEX_CLIENT_KEY must be set` | Add the key under **Environment**. |
| Desktop app shows "Open this link in the ForceX app" | The `.exe` was built with a different key from the one in Render. Rebuild it. |
| Desktop app says "Only links from … can be opened" | The `.exe` was built for a different address. Rebuild with the right `--url`. |
| Shares vanish after a deploy | You are on the free plan, or the disk is not mounted at `/var/data`. |
