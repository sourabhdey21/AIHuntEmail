from datetime import datetime, timezone

import httpx

from app.db import connect, utc_now
from app.extract import extract_emails, parse_job_paste
from app.roles import classify_roles, is_target_role


USER_AGENT = "HuntMail/1.0 (personal job search)"


def _matches(text: str, keywords: str, location: str) -> bool:
    haystack = text.lower()
    terms = [part.strip().lower() for part in keywords.split(",") if part.strip()]
    if terms and not any(term in haystack for term in terms):
        return False
    if location and location.lower() not in haystack:
        # Remote-friendly boards often omit city names; keep remote/worldwide.
        if location.lower() not in ("remote", "anywhere", "worldwide"):
            return False
    return True


def fetch_remoteok() -> list[dict]:
    jobs: list[dict] = []
    try:
        with httpx.Client(timeout=20.0, headers={"User-Agent": USER_AGENT}) as client:
            response = client.get("https://remoteok.com/api")
            response.raise_for_status()
            payload = response.json()
    except Exception:
        return jobs

    for item in payload:
        if not isinstance(item, dict) or ("position" not in item and "title" not in item):
            continue
        title = item.get("position") or item.get("title") or ""
        company = item.get("company") or ""
        description = item.get("description") or ""
        location = item.get("location") or "Remote"
        url = item.get("url") or item.get("apply_url") or ""
        external_id = str(item.get("id") or url or title)
        blob = f"{title}\n{company}\n{location}\n{description}"
        emails = extract_emails(blob)
        jobs.append(
            {
                "source": "remoteok",
                "external_id": external_id,
                "title": title[:200],
                "company": company[:160],
                "location": location[:160],
                "url": url[:400],
                "description": description[:12000],
                "recruiter_email": emails[0] if emails else "",
                "recruiter_name": "",
            }
        )
    return jobs


def fetch_arbeitnow() -> list[dict]:
    jobs: list[dict] = []
    try:
        with httpx.Client(timeout=20.0, headers={"User-Agent": USER_AGENT}) as client:
            response = client.get("https://www.arbeitnow.com/api/job-board-api")
            response.raise_for_status()
            payload = response.json()
    except Exception:
        return jobs

    for item in payload.get("data") or []:
        title = item.get("title") or ""
        company = item.get("company_name") or ""
        description = item.get("description") or ""
        location = item.get("location") or ""
        url = item.get("url") or ""
        slug = item.get("slug") or url or title
        blob = f"{title}\n{company}\n{location}\n{description}"
        emails = extract_emails(blob)
        jobs.append(
            {
                "source": "arbeitnow",
                "external_id": str(slug)[:200],
                "title": title[:200],
                "company": company[:160],
                "location": location[:160],
                "url": url[:400],
                "description": description[:12000],
                "recruiter_email": emails[0] if emails else "",
                "recruiter_name": "",
            }
        )
    return jobs


def fetch_remotive() -> list[dict]:
    jobs: list[dict] = []
    try:
        with httpx.Client(timeout=25.0, headers={"User-Agent": USER_AGENT}) as client:
            response = client.get("https://remotive.com/api/remote-jobs")
            response.raise_for_status()
            payload = response.json()
    except Exception:
        return jobs

    for item in payload.get("jobs") or []:
        title = item.get("title") or ""
        company = item.get("company_name") or ""
        description = item.get("description") or ""
        location = item.get("candidate_required_location") or "Remote"
        url = item.get("url") or ""
        external_id = str(item.get("id") or url or title)
        blob = f"{title}\n{company}\n{location}\n{description}"
        emails = extract_emails(blob)
        jobs.append(
            {
                "source": "remotive",
                "external_id": external_id,
                "title": title[:200],
                "company": company[:160],
                "location": location[:160],
                "url": url[:400],
                "description": description[:12000],
                "recruiter_email": emails[0] if emails else "",
                "recruiter_name": "",
            }
        )
    return jobs


def run_watchers() -> dict:
    with connect() as conn:
        watchers = conn.execute(
            "SELECT * FROM watchers WHERE active = 1"
        ).fetchall()

    imported = 0
    scanned = 0
    boards = fetch_remoteok() + fetch_arbeitnow() + fetch_remotive()
    scanned = len(boards)
    target_boards = [
        job for job in boards if is_target_role(job["title"], job["description"])
    ]

    if not watchers:
        return {
            "imported": 0,
            "scanned": scanned,
            "matched": len(target_boards),
            "watchers": 0,
        }

    with connect() as conn:
        for job in target_boards:
            cursor = conn.execute(
                """
                INSERT OR IGNORE INTO jobs (
                    source, external_id, title, company, location, url,
                    description, recruiter_name, recruiter_email, status, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'new', ?)
                """,
                (
                    job["source"],
                    job["external_id"],
                    job["title"],
                    job["company"],
                    job["location"],
                    job["url"],
                    job["description"],
                    job["recruiter_name"],
                    job["recruiter_email"],
                    utc_now(),
                ),
            )
            imported += cursor.rowcount
        for watcher in watchers:
            conn.execute(
                "UPDATE watchers SET last_run_at = ? WHERE id = ?",
                (utc_now(), watcher["id"]),
            )

    return {
        "imported": imported,
        "scanned": scanned,
        "matched": len(target_boards),
        "watchers": len(watchers),
    }


def import_pasted_job(raw: str, url: str = "") -> int:
    parsed = parse_job_paste(raw)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S%f")
    with connect() as conn:
        cursor = conn.execute(
            """
            INSERT INTO jobs (
                source, external_id, title, company, location, url,
                description, recruiter_name, recruiter_email, status, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'new', ?)
            """,
            (
                "linkedin-paste",
                stamp,
                parsed["title"],
                parsed["company"],
                parsed["location"],
                url.strip(),
                parsed["description"],
                parsed["recruiter_name"],
                parsed["recruiter_email"],
                utc_now(),
            ),
        )
        return int(cursor.lastrowid)
