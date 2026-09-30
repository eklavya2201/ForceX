# Deploying ForceX

This guide puts the ForceX server online for free, builds the Windows desktop app, and publishes it so anyone who opens a share link can download it.

1. [Choose a host](#choose-a-host)
2. [Free: deploy on PythonAnywhere](#free-deploy-on-pythonanywhere)
3. [Build and publish ForceX.exe](#build-and-publish-forcexexe)
4. [Paid: deploy on Render](#paid-deploy-on-render)

## Choose a host

ForceX keeps its database and uploaded files on disk, so the host must keep files between restarts.

| Host | Cost | Keeps files | Limits |
|---|---|---|---|
| **PythonAnywhere Beginner** | Free | Yes | 512 MB storage in total, uploads up to about 90 MB, log in once a month to keep the site running |
| Render Starter + disk | about $7.25 / month | Yes | 1 GB disk (more costs extra), uploads up to 500 MB |
| Render Free | Free | **No** | Deletes every file and account each time it sleeps (after 15 idle minutes) |
| Vercel | Free | **No** | Serverless: no disk, 4.5 MB request limit, no cleanup job |

Use **PythonAnywhere** for free hosting. Do not use Render Free or Vercel: the site would appear to work, then lose every share.

## Free: deploy on PythonAnywhere

Your site will be at `https://YOUR-USERNAME.pythonanywhere.com`. Replace `YOUR-USERNAME` everywhere below.

### 1. Create an account

Sign up for the free **Beginner** plan at https://www.pythonanywhere.com/pricing/.

### 2. Download the code and install packages

Open **Consoles** → **Bash** and run:

```bash
git clone https://github.com/YOUR-GITHUB-USERNAME/ForceX.git
cd ForceX
mkvirtualenv --python=/usr/bin/python3.12 forcex
pip install -r requirements.txt
```

Use your own copy of the repository (your fork or mirror). If `python3.12` is not found, run `ls /usr/bin/python3.*` and use the newest version listed, 3.12 or higher.

### 3. Create the settings file

Still in the console, generate two keys:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
python -c "import secrets; print(secrets.token_hex(32))"
```

Open the editor with `nano .env`, paste the following, and put one key on each of the first two lines:

```env
FORCEX_SECRET_KEY=<first key>
FORCEX_CLIENT_KEY=<second key>
FORCEX_SCHEDULER=0
FORCEX_MAX_UPLOAD_MB=90
FORCEX_COOKIE_SECURE=1
FORCEX_BEHIND_PROXY=1
FORCEX_ALLOW_REGISTRATION=1
FORCEX_DESKTOP_DOWNLOAD_URL=https://github.com/YOUR-GITHUB-USERNAME/ForceX/releases/latest/download/ForceX.exe
```

Save with `Ctrl+O`, `Enter`, then exit with `Ctrl+X`.

Keep a copy of `FORCEX_CLIENT_KEY`. You need it to build the desktop app.

Why these values:

- `FORCEX_SCHEDULER=0`: PythonAnywhere does not allow background threads, so ForceX cleans up expired shares while handling normal requests instead.
- `FORCEX_MAX_UPLOAD_MB=90`: PythonAnywhere rejects uploads over 100 MB.

### 4. Create the web app

1. Open the **Web** tab and click **Add a new web app** → **Next**.
2. Choose **Manual configuration** (not "Flask"), then **Python 3.12** (or the version you used in step 2).
3. On the web app page, set:
   - **Source code:** `/home/YOUR-USERNAME/ForceX`
   - **Virtualenv:** `/home/YOUR-USERNAME/.virtualenvs/forcex`
4. Click the **WSGI configuration file** link, delete everything in it, paste this, and click **Save**:

   ```python
   import sys
   sys.path.insert(0, "/home/YOUR-USERNAME/ForceX")
   from wsgi import application
   ```

5. Under **Static files**, add URL `/static/` with directory `/home/YOUR-USERNAME/ForceX/static`.
6. Under **Security**, turn on **Force HTTPS**.
7. Click the green **Reload** button at the top.

Open `https://YOUR-USERNAME.pythonanywhere.com`. You should see the ForceX sign-in page.

### 5. Create your account, then close registration

1. Click **Get started** and register.
2. In a Bash console, run `cd ~/ForceX && nano .env`, change `FORCEX_ALLOW_REGISTRATION=1` to `0`, and save.
3. On the **Web** tab, click **Reload**.

### 6. Keep it running

Free web apps stop after one month. PythonAnywhere emails you before that. Log in, open the **Web** tab, and click **Run until 1 month from today**. Your data is kept.

### Updating

```bash
cd ~/ForceX && git pull && workon forcex && pip install -r requirements.txt
```

Then click **Reload** on the **Web** tab.

## Build and publish ForceX.exe

Only needed for shares created with **ForceX app only** protection. Shares with the default **Any browser** protection open in any browser, watermarked, with nothing to install.

When a receiver opens an app-only share in Chrome or Edge, they see a **Download ForceX for Windows** button and the link to paste into the app. That button points to the `.exe` you publish here.

### 1. Build it on your Windows PC

From a copy of the repository:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt -r requirements-desktop.txt pyinstaller
.\.venv\Scripts\python.exe build_desktop.py --url https://YOUR-USERNAME.pythonanywhere.com --key <FORCEX_CLIENT_KEY from the server's .env>
```

The build takes about 5 minutes and produces `dist\ForceX.exe` (about 220 MB). The site address and key are built in, so receivers need nothing else.

### 2. Publish it as a GitHub Release

This gives it a permanent public download link. It requires the repository to be public and the [GitHub CLI](https://cli.github.com) to be signed in.

```powershell
gh release create v1.0.0 dist\ForceX.exe --title "ForceX for Windows" --notes "Download ForceX.exe, open it, and paste the share link you were sent."
```

The download link is then:

```text
https://github.com/YOUR-GITHUB-USERNAME/ForceX/releases/latest/download/ForceX.exe
```

This is the address in `FORCEX_DESKTOP_DOWNLOAD_URL`. It always points to the newest release, so publishing `v1.0.1` later needs no server change.

Without the CLI, open the repository on GitHub, click **Releases** → **Draft a new release**, create a tag such as `v1.0.0`, attach `dist\ForceX.exe`, and publish. The file must be named exactly `ForceX.exe`.

### What receivers see

1. They open the share link in their browser and get the "Open this link in the ForceX app" page.
2. They click **Download ForceX for Windows** and run it. Windows SmartScreen warns about an unknown publisher, because the `.exe` is not code-signed; they click **More info** → **Run anyway**.
3. They paste the link into the bar at the top of the app and press Enter.

The app needs Windows 10 version 2004 or newer, because it relies on Windows to hide its window from screenshots. On other systems it refuses to start.

### Pointing an existing .exe elsewhere

Place a file named `forcex.env` next to the `.exe` to override the built-in values without rebuilding:

```env
FORCEX_URL=https://YOUR-USERNAME.pythonanywhere.com
FORCEX_CLIENT_KEY=<key>
```

## Paid: deploy on Render

Use this when you outgrow PythonAnywhere's 512 MB or 90 MB upload limit.

1. Sign in at https://dashboard.render.com with GitHub.
2. Click **New** → **Blueprint** and choose your ForceX repository. Render reads `render.yaml` and shows a web service, `forcex`, on the Starter plan with a 1 GB disk.
3. When asked for `FORCEX_CLIENT_KEY`, paste a key generated with `py -c "import secrets; print(secrets.token_hex(32))"`.
4. Click **Apply**. The first build takes 2–4 minutes. Your site is at `https://forcex-XXXX.onrender.com`.
5. Register, then set `FORCEX_ALLOW_REGISTRATION` to `0` under **Environment**.
6. If your repository is not `eklavya2201/ForceX`, set `FORCEX_DESKTOP_DOWNLOAD_URL` to your own release link.
7. Build the `.exe` with `--url https://forcex-XXXX.onrender.com` and publish it as above.

Every push to the connected branch redeploys automatically, and data on the disk is kept.

## Things to know

- **A public `.exe` makes the client key public.** Anyone can download the app and extract the key. The key only makes sure ordinary browsers are sent to the app; share links, passcodes and expiry are what protect the content. If you need tighter control, share the `.exe` privately instead of through a public release.
- **Each site needs its own `.exe`.** The `.exe` only opens links from the site it was built for. If two people deploy separately, each builds and publishes their own `.exe` and sets their own `FORCEX_DESKTOP_DOWNLOAD_URL`.
- **Nothing stops a phone camera.** The watermark with the share ID and time is there to trace leaked photos.

## Troubleshooting

| Symptom | Fix |
|---|---|
| PythonAnywhere shows "Something went wrong" | Open the **error log** link on the **Web** tab. `FORCEX_SECRET_KEY must be set` or `FORCEX_CLIENT_KEY must be set` means `.env` is missing or not in `~/ForceX`. |
| `ModuleNotFoundError` in the error log | The **Virtualenv** path on the **Web** tab is wrong, or `pip install` ran outside `workon forcex`. |
| Upload fails on PythonAnywhere | The file is over 90 MB, or the 512 MB storage is full. Delete old shares or move to Render. |
| Download button gives a 404 | No release has been published yet, or the asset is not named exactly `ForceX.exe`. |
| Desktop app shows "Open this link in the ForceX app" | The `.exe` was built with a different key from the one on the server. Rebuild it. |
| Desktop app says "Only links from … can be opened" | The `.exe` was built for a different address. Rebuild with the right `--url`. |
| Shares vanish after a restart | You are on Render Free, or the Render disk is not mounted at `/var/data`. |
