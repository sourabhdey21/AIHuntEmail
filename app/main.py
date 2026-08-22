import smtplib
from pathlib import Path

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.compose import compose_email
from app.config import UPLOAD_DIR, watch_interval_minutes
from app.db import connect, init_db, row_to_dict, utc_now
from app.emailer import MailConfigError, can_send, send_application
from app.extract import extract_emails, parse_job_paste
from app.jobs_fetcher import import_pasted_job, run_watchers
from app.roles import classify_roles, role_catalog

STATIC_DIR = Path(__file__).resolve().parent / "static"

app = FastAPI(title="HuntMail")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

scheduler = BackgroundScheduler()


@app.on_event("startup")
def on_startup() -> None:
    init_db()
    scheduler.add_job(run_watchers, "date", id="watchers-boot", replace_existing=True)
    if not scheduler.running:
        scheduler.add_job(
            run_watchers,
            "interval",
            minutes=watch_interval_minutes(),
            id="watchers",
            replace_existing=True,
        )
        scheduler.start()


@app.on_event("shutdown")
def on_shutdown() -> None:
    if scheduler.running:
        scheduler.shutdown(wait=False)


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


def with_roles(job: dict) -> dict:
    roles = classify_roles(job.get("title") or "", job.get("description") or "")
    source = (job.get("source") or "")
    if source.startswith("linkedin") and not roles:
        roles = ["Imported"]
    job["roles"] = roles
    job["on_target"] = bool(roles) or source.startswith("linkedin")
    return job


@app.get("/api/roles")
def list_roles() -> list[dict]:
    return role_catalog()


@app.get("/api/status")
def status() -> dict:
    with connect() as conn:
        rows = [with_roles(dict(row)) for row in conn.execute("SELECT * FROM jobs")]
        drafts = conn.execute(
            "SELECT COUNT(*) AS n FROM drafts WHERE status = 'draft'"
        ).fetchone()["n"]
        sent = conn.execute(
            "SELECT COUNT(*) AS n FROM drafts WHERE status = 'sent'"
        ).fetchone()["n"]
    target = [row for row in rows if row["on_target"]]
    return {
        "jobs": len(target),
        "all_jobs": len(rows),
        "drafts": drafts,
        "sent": sent,
        "with_email": sum(1 for row in target if row["recruiter_email"]),
        "mail_ready": can_send(),
    }


@app.get("/api/profile")
def get_profile() -> dict:
    with connect() as conn:
        profile = row_to_dict(conn.execute("SELECT * FROM profile WHERE id = 1").fetchone())
    return profile or {}


@app.post("/api/profile")
def save_profile(
    full_name: str = Form(""),
    headline: str = Form(""),
    skills: str = Form(""),
    pitch: str = Form(""),
    resume: UploadFile | None = File(None),
) -> dict:
    resume_path = ""
    resume_name = ""
    with connect() as conn:
        current = row_to_dict(conn.execute("SELECT * FROM profile WHERE id = 1").fetchone())
        resume_path = (current or {}).get("resume_path") or ""
        resume_name = (current or {}).get("resume_name") or ""

        if resume and resume.filename:
            resume_path, resume_name = _store_resume(resume)

        conn.execute(
            """
            UPDATE profile
            SET full_name = ?, headline = ?, skills = ?, pitch = ?,
                resume_path = ?, resume_name = ?, updated_at = ?
            WHERE id = 1
            """,
            (full_name, headline, skills, pitch, resume_path, resume_name, utc_now()),
        )
    return get_profile()


@app.post("/api/profile/resume")
def upload_resume(resume: UploadFile = File(...)) -> dict:
    if not resume.filename:
        raise HTTPException(status_code=400, detail="Choose a resume file first.")
    resume_path, resume_name = _store_resume(resume)
    with connect() as conn:
        conn.execute(
            """
            UPDATE profile
            SET resume_path = ?, resume_name = ?, updated_at = ?
            WHERE id = 1
            """,
            (resume_path, resume_name, utc_now()),
        )
    return get_profile()


def _store_resume(resume: UploadFile) -> tuple[str, str]:
    suffix = Path(resume.filename or "resume.pdf").suffix.lower() or ".pdf"
    dest = UPLOAD_DIR / f"resume{suffix}"
    dest.write_bytes(resume.file.read())
    return str(dest), resume.filename or dest.name


@app.get("/api/jobs")
def list_jobs(status: str = "", only_target: bool = True) -> list[dict]:
    query = "SELECT * FROM jobs"
    params: list = []
    if status:
        query += " WHERE status = ?"
        params.append(status)
    query += " ORDER BY id DESC"
    with connect() as conn:
        rows = [with_roles(dict(row)) for row in conn.execute(query, params)]
    if only_target:
        rows = [row for row in rows if row["on_target"]]
    return rows


@app.get("/api/jobs/{job_id}")
def get_job(job_id: int) -> dict:
    with connect() as conn:
        job = row_to_dict(conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone())
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        drafts = conn.execute(
            "SELECT * FROM drafts WHERE job_id = ? ORDER BY id DESC",
            (job_id,),
        ).fetchall()
    parsed = parse_job_paste(job["description"])
    job = with_roles(job)
    profile = get_profile()
    return {
        "job": job,
        "drafts": [dict(row) for row in drafts],
        "emails": parsed.get("all_emails") or extract_emails(job["description"]),
        "resume_name": profile.get("resume_name") or "",
        "has_resume": bool(profile.get("resume_path")),
    }


@app.post("/api/jobs/preview")
def preview_job(text: str = Form(...), url: str = Form("")) -> dict:
    if not text.strip():
        raise HTTPException(status_code=400, detail="Paste a job posting first.")
    parsed = parse_job_paste(text)
    if url.strip() and not parsed.get("url"):
        parsed["url"] = url.strip()
    job = with_roles(
        {
            "title": parsed["title"],
            "company": parsed["company"],
            "location": parsed["location"],
            "description": parsed["description"],
            "recruiter_email": parsed["recruiter_email"],
            "recruiter_name": parsed["recruiter_name"],
        }
    )
    composed = compose_email(get_profile(), job)
    profile = get_profile()
    return {
        "job": job,
        "emails": parsed["all_emails"],
        "draft": {"subject": composed["subject"], "body": composed["body"]},
        "matched_skills": composed["matched_skills"],
        "requirements": composed["requirements"],
        "resume_name": profile.get("resume_name") or "",
        "has_resume": bool(profile.get("resume_path")),
    }


@app.post("/api/jobs/import")
def import_job(text: str = Form(...), url: str = Form("")) -> dict:
    if not text.strip():
        raise HTTPException(status_code=400, detail="Paste a job posting first.")
    job_id = import_pasted_job(text, url)
    return create_draft(job_id)


@app.patch("/api/jobs/{job_id}")
def update_job(
    job_id: int,
    recruiter_email: str = Form(""),
    recruiter_name: str = Form(""),
    title: str = Form(""),
    company: str = Form(""),
) -> dict:
    with connect() as conn:
        job = row_to_dict(conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone())
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        conn.execute(
            """
            UPDATE jobs
            SET recruiter_email = ?, recruiter_name = ?, title = ?, company = ?
            WHERE id = ?
            """,
            (
                recruiter_email or job["recruiter_email"],
                recruiter_name or job["recruiter_name"],
                title or job["title"],
                company or job["company"],
                job_id,
            ),
        )
    return get_job(job_id)


@app.delete("/api/jobs/{job_id}")
def delete_job(job_id: int) -> dict:
    with connect() as conn:
        conn.execute("DELETE FROM jobs WHERE id = ?", (job_id,))
    return {"ok": True}


@app.post("/api/jobs/{job_id}/draft")
def create_draft(job_id: int) -> dict:
    profile = get_profile()
    with connect() as conn:
        job = row_to_dict(conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone())
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        parsed = parse_job_paste(job.get("description") or job.get("title") or "")
        job["title"] = parsed["title"] or job["title"]
        job["company"] = job["company"] or parsed["company"]
        job["location"] = job["location"] or parsed["location"]
        job["recruiter_email"] = job["recruiter_email"] or parsed["recruiter_email"]
        job["recruiter_name"] = job["recruiter_name"] or parsed["recruiter_name"]
        conn.execute(
            """
            UPDATE jobs
            SET title = ?, company = ?, location = ?, recruiter_email = ?, recruiter_name = ?
            WHERE id = ?
            """,
            (
                job["title"],
                job["company"],
                job["location"],
                job["recruiter_email"],
                job["recruiter_name"],
                job_id,
            ),
        )
        composed = compose_email(profile, job)
        conn.execute(
            """
            INSERT INTO drafts (job_id, subject, body, status, created_at, updated_at)
            VALUES (?, ?, ?, 'draft', ?, ?)
            """,
            (job_id, composed["subject"], composed["body"], utc_now(), utc_now()),
        )
        conn.execute("UPDATE jobs SET status = 'drafted' WHERE id = ?", (job_id,))
    payload = get_job(job_id)
    payload["matched_skills"] = composed["matched_skills"]
    payload["requirements"] = composed["requirements"]
    return payload


@app.patch("/api/drafts/{draft_id}")
def update_draft(draft_id: int, subject: str = Form(""), body: str = Form("")) -> dict:
    with connect() as conn:
        draft = row_to_dict(
            conn.execute("SELECT * FROM drafts WHERE id = ?", (draft_id,)).fetchone()
        )
        if not draft:
            raise HTTPException(status_code=404, detail="Draft not found")
        conn.execute(
            "UPDATE drafts SET subject = ?, body = ?, updated_at = ? WHERE id = ?",
            (subject or draft["subject"], body or draft["body"], utc_now(), draft_id),
        )
        job_id = draft["job_id"]
    return get_job(job_id)


@app.post("/api/drafts/{draft_id}/send")
def send_draft(draft_id: int, resume: UploadFile | None = File(None)) -> dict:
    profile = get_profile()
    if resume and resume.filename:
        resume_path, resume_name = _store_resume(resume)
        with connect() as conn:
            conn.execute(
                """
                UPDATE profile
                SET resume_path = ?, resume_name = ?, updated_at = ?
                WHERE id = 1
                """,
                (resume_path, resume_name, utc_now()),
            )
        profile = get_profile()

    with connect() as conn:
        draft = row_to_dict(
            conn.execute("SELECT * FROM drafts WHERE id = ?", (draft_id,)).fetchone()
        )
        if not draft:
            raise HTTPException(status_code=404, detail="Draft not found")
        job = row_to_dict(
            conn.execute("SELECT * FROM jobs WHERE id = ?", (draft["job_id"],)).fetchone()
        )
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")

    try:
        send_application(
            to_email=job["recruiter_email"],
            subject=draft["subject"],
            body=draft["body"],
            resume_path=profile.get("resume_path") or "",
            resume_name=profile.get("resume_name") or "",
        )
        error = ""
        status_value = "sent"
        sent_at = utc_now()
    except (MailConfigError, OSError, smtplib.SMTPException) as exc:
        error = str(exc)
        status_value = "failed"
        sent_at = None

    with connect() as conn:
        conn.execute(
            """
            UPDATE drafts
            SET status = ?, error = ?, sent_at = ?, updated_at = ?
            WHERE id = ?
            """,
            (status_value, error, sent_at, utc_now(), draft_id),
        )
        if status_value == "sent":
            conn.execute("UPDATE jobs SET status = 'sent' WHERE id = ?", (draft["job_id"],))
        else:
            conn.execute("UPDATE jobs SET status = 'failed' WHERE id = ?", (draft["job_id"],))

    if status_value == "failed":
        raise HTTPException(status_code=400, detail=error)
    payload = get_job(draft["job_id"])
    payload["notification"] = {
        "title": "Message has been sent",
        "to": job["recruiter_email"],
        "subject": draft["subject"],
        "resume": profile.get("resume_name") or "",
    }
    return payload


@app.get("/api/watchers")
def list_watchers() -> list[dict]:
    with connect() as conn:
        return [dict(row) for row in conn.execute("SELECT * FROM watchers ORDER BY id DESC")]


@app.post("/api/watchers")
def create_watcher(keywords: str = Form(...), location: str = Form("")) -> dict:
    with connect() as conn:
        cursor = conn.execute(
            """
            INSERT INTO watchers (keywords, location, active, created_at)
            VALUES (?, ?, 1, ?)
            """,
            (keywords.strip(), location.strip(), utc_now()),
        )
        watcher_id = cursor.lastrowid
        row = row_to_dict(
            conn.execute("SELECT * FROM watchers WHERE id = ?", (watcher_id,)).fetchone()
        )
    return row or {}


@app.post("/api/watchers/{watcher_id}/toggle")
def toggle_watcher(watcher_id: int) -> dict:
    with connect() as conn:
        row = row_to_dict(
            conn.execute("SELECT * FROM watchers WHERE id = ?", (watcher_id,)).fetchone()
        )
        if not row:
            raise HTTPException(status_code=404, detail="Watcher not found")
        conn.execute(
            "UPDATE watchers SET active = ? WHERE id = ?",
            (0 if row["active"] else 1, watcher_id),
        )
    return {"ok": True}


@app.delete("/api/watchers/{watcher_id}")
def delete_watcher(watcher_id: int) -> dict:
    with connect() as conn:
        conn.execute("DELETE FROM watchers WHERE id = ?", (watcher_id,))
    return {"ok": True}


@app.post("/api/watchers/run")
def run_now() -> dict:
    return run_watchers()
