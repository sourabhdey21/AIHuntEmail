from app.extract import clean_title, extract_focus, name_from_email


def _skill_list(skills: str) -> list[str]:
    return [part.strip() for part in (skills or "").split(",") if part.strip()]


def matched_skills(skills: str, description: str) -> list[str]:
    haystack = (description or "").lower()
    hits = []
    for skill in _skill_list(skills):
        if skill.lower() in haystack:
            hits.append(skill)
    return hits[:6]


def _first_name(job: dict) -> str:
    recruiter = (job.get("recruiter_name") or "").strip()
    if recruiter:
        return recruiter.split()[0]
    return name_from_email(job.get("recruiter_email") or "").split()[0] if name_from_email(job.get("recruiter_email") or "") else ""


def compose_email(profile: dict, job: dict) -> dict:
    name = (profile.get("full_name") or "Sourabh Dey").strip()
    pitch = (profile.get("pitch") or "").strip()
    title = clean_title(job.get("title") or "the open role")
    company = (job.get("company") or "").strip()
    description = job.get("description") or ""

    matches = matched_skills(profile.get("skills") or "", f"{title} {description}")
    themes = extract_focus(f"{title} {description}")
    first = _first_name(job)
    greeting = f"Dear {first}," if first else "Dear Hiring Team,"

    role_line = f"the {title} position"
    if company:
        role_line = f"the {title} position at {company}"

    if matches:
        fit = (
            f"My background in {', '.join(matches[:-1]) + ', and ' + matches[-1] if len(matches) > 1 else matches[0]} "
            f"is a strong fit for this role."
        )
    else:
        fit = "I have hands-on experience in cloud operations and systems administration that maps well to this role."

    theme_line = ""
    if themes:
        theme_line = (
            "I would be glad to support "
            + (", ".join(themes[:-1]) + ", and " + themes[-1] if len(themes) > 1 else themes[0])
            + "."
        )

    paragraphs = [
        greeting,
        "",
        f"I am writing to apply for {role_line}. {fit}",
        "",
        pitch,
    ]
    if theme_line:
        paragraphs.extend(["", theme_line])
    paragraphs.extend(
        [
            "",
            "I have attached my resume for your review. I would welcome the opportunity to discuss how I can contribute to the team.",
            "",
            "Kind regards,",
            name,
        ]
    )

    subject = f"Application for {title}"
    if company:
        subject = f"Application for {title} — {company}"

    return {
        "subject": subject[:160],
        "body": "\n".join(paragraphs).strip(),
        "matched_skills": matches,
        "requirements": themes,
        "title": title,
        "company": company,
        "greeting_name": first,
    }
