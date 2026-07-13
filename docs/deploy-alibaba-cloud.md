# Deploying to Alibaba Cloud

This guide deploys the Job Application Autopilot backend to **Alibaba Cloud ECS** and explains
how to satisfy the hackathon's **"Proof of Alibaba Cloud Deployment"** requirement.

> **Why ECS (not Function Compute)?** The app keeps state on the local filesystem (SQLite
> `applications.db`, uploaded CVs, generated `.docx` files, and the Gmail `token.json`), runs the
> pipeline as a background `subprocess`, and serves a long-lived FastAPI process. That maps cleanly
> to a small always-on VM. Function Compute is stateless and short-lived, so it would fight all of
> the above. Use ECS.

---

## 0. Prerequisites

- An **Alibaba Cloud (International)** account — the same account you used at qwencloud.com to get
  your Qwen credits. Use the international console: <https://account.alibabacloud.com>.
- Your `QWEN_API_KEY`, Google `credentials.json`, and a working local checkout of the repo.
- Because the code calls the **international** DashScope endpoint
  (`https://dashscope-intl.aliyuncs.com`), pick an **international region** for the ECS instance
  (e.g., **Singapore**) so it can reach both Qwen Cloud and the Gmail API.

---

## 1. Create the ECS instance

In the console: **Elastic Compute Service → Instances → Create Instance**.

- **Billing:** Pay-as-you-go (covered by your credits; you can stop/release it after judging).
- **Region:** Singapore (or another international region).
- **Instance type:** 2 vCPU / 2–4 GB is plenty (e.g., a burstable `t`-series or `e`-series).
- **Image:** Ubuntu 22.04 LTS (64-bit).
- **Public IP:** **Assign a public IPv4** (needed so judges can reach the demo).
- **Key pair:** create/download an SSH key pair (easier than a root password).
- **System disk:** default 40 GB is fine.

Note the instance's **public IP** once it's running.

## 2. Open the firewall (Security Group)

Edit the instance's **Security Group → Inbound rules** and allow:

| Port | Purpose | Source |
|---|---|---|
| 22 | SSH | your IP (recommended) or `0.0.0.0/0` |
| 8000 | App (uvicorn) | `0.0.0.0/0` |
| 80 | App (only if you add nginx, step 8) | `0.0.0.0/0` |

## 3. Connect and install system packages

```bash
ssh -i /path/to/key.pem root@<PUBLIC_IP>

apt update && apt -y upgrade
apt -y install python3 python3-venv python3-pip git
```

## 4. Get the code and install dependencies

```bash
cd /opt
git clone https://github.com/cavy111/job-autopilot.git
cd job-autopilot

python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

## 5. Configure secrets

Create `.env` in the repo root (never commit it):

```bash
cat > /opt/job-autopilot/.env <<'ENV'
QWEN_API_KEY=your_real_qwen_key
SENDER_NAME=Your Name
SENDER_EMAIL=you@example.com
SENDER_PHONE=+263...
ENV
```

Upload your Google OAuth client file from your **laptop**:

```bash
scp -i /path/to/key.pem credentials.json root@<PUBLIC_IP>:/opt/job-autopilot/
```

### 5a. Gmail token — the one real gotcha ⚠️

The Gmail auth flow (`agents/submission.py → _get_gmail_service`) calls
`flow.run_local_server(...)`, which **opens a browser**. A headless ECS box has no browser, so you
must generate `token.json` **on your laptop first**, then upload it. The server only ever needs to
silently refresh it afterward.

On your **laptop** (with `credentials.json` present and deps installed):

```bash
python -c "from agents.submission import _get_gmail_service; _get_gmail_service()"
# a browser opens → approve → token.json is written next to credentials.json
```

Then upload it:

```bash
scp -i /path/to/key.pem token.json root@<PUBLIC_IP>:/opt/job-autopilot/
```

> If you keep the app in **dry-run / approval-only** mode for the demo, sending is only triggered
> when you click **Approve & Send**. You can demo the full pipeline (scrape → score → tailor →
> stage for approval) without ever sending, and show one real send at the end once `token.json` is
> in place.

## 6. Initialise the database

```bash
cd /opt/job-autopilot && source venv/bin/activate
python -c "from agents.tracker import init_db; init_db()"
```

(The dashboard also calls `init_db()` on startup, so this is just an explicit first run.)

## 7. Run it as a service (systemd)

Create `/etc/systemd/system/autopilot.service`:

```ini
[Unit]
Description=Job Application Autopilot (FastAPI)
After=network.target

[Service]
WorkingDirectory=/opt/job-autopilot
ExecStart=/opt/job-autopilot/venv/bin/uvicorn api.main:app --host 0.0.0.0 --port 8000
Restart=always
User=root

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
systemctl daemon-reload
systemctl enable --now autopilot
systemctl status autopilot          # should show "active (running)"
```

Open **http://<PUBLIC_IP>:8000** — you should see the dashboard. Upload a CV and click **Run
Pipeline**.

> The pipeline runs via `subprocess.Popen([sys.executable, "main.py"])`. Because systemd starts
> uvicorn from the venv, `sys.executable` is the venv Python, so the subprocess uses the same
> environment automatically.

## 8. (Optional) Nicer URL with nginx on port 80

```bash
apt -y install nginx
cat > /etc/nginx/sites-available/autopilot <<'NGINX'
server {
    listen 80;
    server_name _;
    location / { proxy_pass http://127.0.0.1:8000; proxy_set_header Host $host; }
}
NGINX
ln -sf /etc/nginx/sites-available/autopilot /etc/nginx/sites-enabled/default
nginx -t && systemctl restart nginx
```

Then the demo is at **http://<PUBLIC_IP>** (port 80).

---

## 9. Satisfying the submission requirement

The official rules define the proof as **"a link to a code file in your repo that demonstrates use
of Alibaba Cloud services and APIs."** Your Qwen calls hit the Alibaba Cloud DashScope endpoint, so:

- **Link this in your Devpost submission:**
  [`agents/relevance_filter.py` (the `base_url="https://dashscope-intl.aliyuncs.com/..."` DashScope client)](../agents/relevance_filter.py) — the same pattern is in `cv_parser.py`, `cv_tailor.py`, and `cover_letter.py`.
- The project **overview** page also asks for a **short recording** showing the backend running on
  Alibaba Cloud. Capture ~30–60s of:
  1. `systemctl status autopilot` on the ECS box (proves it's running on Alibaba Cloud),
  2. the dashboard loading at your `http://<PUBLIC_IP>`, and
  3. a pipeline run producing a Qwen-scored job (proves the DashScope/Alibaba Cloud API call).

Provide the **public URL** in your submission's testing instructions so judges can reach the demo
during the judging period.

## 10. Housekeeping

- Confirm `.env`, `credentials.json`, and `token.json` are **gitignored** (they are) — never commit secrets.
- Lock the SSH (port 22) rule to your own IP where possible.
- **Stop** (don't release) the instance between work sessions to conserve credits; **release** it after the judging period ends (~Jul 31).
- If you have time, add HTTPS via a domain + free certificate; not required for judging.
