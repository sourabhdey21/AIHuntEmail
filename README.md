# HuntMail

A local web app that helps you apply to jobs by email: paste a posting, extract the recruiter address if it is in the text, write a tailored note from your resume and pitch, then send it from Gmail.

## What is free, and what LinkedIn will not allow

Fully automatic LinkedIn integration is **not available for free**, and it is not something this app tries to do.

- LinkedIn’s public APIs do not let a personal app read your feed, watch every new job, or pull recruiter emails.
- Scraping LinkedIn (or using unofficial “LinkedIn automation” tools) breaks their terms, can lock your account, and is not implemented here.
- Most LinkedIn posts hide the recruiter email anyway. Easy Apply does not expose a mailbox you can write to.

What you *can* do for free:

1. Copy a job from LinkedIn and paste it into HuntMail.
2. If the post contains an email, HuntMail picks it up. If not, type the address yourself.
3. HuntMail drafts a message from your profile, skills, and the job text.
4. You review it, then send it through Gmail with your resume attached.
5. Optional watchers poll **public** boards (RemoteOK, Arbeitnow). Those listings rarely include emails.

That review step is intentional. Auto-emailing every recruiter looks like spam and can freeze your Gmail account.

## Setup

You need Python 3.10+ and a Gmail **app password** (not your normal login password).

1. Turn on [2-Step Verification](https://myaccount.google.com/signinoptions/two-step-verification).
2. Create an app password at [https://myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords).
3. Put it only in `.env` on this machine. Do not paste it into chat, git, or the web UI.

```bash
cd huntmail
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # already created; edit SMTP_APP_PASSWORD
```

Edit `.env`:

```
SMTP_EMAIL=sourabhdey21@gmail.com
SMTP_APP_PASSWORD=your-16-character-app-password
SENDER_NAME=Sourabh Dey
```

Start the app:

```bash
source .venv/bin/activate
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Open [http://127.0.0.1:8000](http://127.0.0.1:8000).

## Daily use

1. **Profile** — name, skills, pitch, and resume PDF.
2. **Import job** — paste LinkedIn (or any) job text. HuntMail writes a draft.
3. **Inbox** — fix the recruiter email if needed, edit the draft, send.
4. **Watchers** — optional keyword alerts from public remote job boards.

Mail never leaves this computer except the one message you choose to send through Gmail.

## Docker and OpenShift

Image: `docker.io/sourabhdey21/huntmail:latest`

```bash
docker build -t sourabhdey21/huntmail:latest .
docker push sourabhdey21/huntmail:latest
```

Kubernetes:

```bash
oc apply -f k8s/
kubectl create secret generic huntmail-smtp -n huntmail --from-env-file=.env --dry-run=client -o yaml | kubectl apply -f -
kubectl -n huntmail rollout status deployment/huntmail
```

Edit `k8s/ingress.yaml` and set `host` to your DNS name. The app listens on port 8080.

Deploy on OpenShift (uses `.env` for the SMTP secret, never bakes it into the image):

```bash
oc login
chmod +x openshift/deploy.sh
./openshift/deploy.sh
```
