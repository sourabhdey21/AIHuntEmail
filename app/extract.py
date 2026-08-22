import re

EMAIL_RE = re.compile(
    r"\b[A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,}\b",
    re.IGNORECASE,
)
SKIP_EMAIL_PARTS = (
    "example.com",
    "domain.com",
    "email.com",
    "sentry.io",
    "wixpress.com",
    "noreply",
    "no-reply",
    "donotreply",
    "mailer-daemon",
)
EMOJI_RE = re.compile(
    "["
    "\U0001F300-\U0001FAFF"
    "\U00002700-\U000027BF"
    "\U00002600-\U000026FF"
    "\U0001F1E0-\U0001F1FF"
    "]+",
    flags=re.UNICODE,
)
LOCATION_HINT = re.compile(
    r"\b(remote|hybrid|onsite|on-site|mumbai|pune|mangalore|bengaluru|bangalore|"
    r"hyderabad|chennai|delhi|noida|gurgaon|gurugram|india|uk|usa|us)\b",
    re.IGNORECASE,
)
SKILL_WORDS = (
    "linux", "windows", "aws", "azure", "gcp", "openstack", "vmware",
    "openshift", "kubernetes", "terraform", "ansible", "devops", "sre",
)
TITLE_PREFIX = re.compile(
    r"^[#\s]*(?:hiring|we(?:'|’)re hiring|job(?: opening)?|opening|role|vacancy|position)\s*[:\-–—]?\s*",
    re.IGNORECASE,
)
EXPERIENCE_SUFFIX = re.compile(
    r"\s*[|\-–—]\s*\d+\s*[–\-to]+\s*\d+\s*years?\s*$",
    re.IGNORECASE,
)


def strip_emoji(text: str) -> str:
    return EMOJI_RE.sub("", text or "")


def clean_line(text: str) -> str:
    text = strip_emoji(text or "")
    text = re.sub(r"\s+", " ", text).strip(" \t:-–—|·")
    return text


def clean_title(raw: str) -> str:
    text = TITLE_PREFIX.sub("", clean_line(raw))
    text = EXPERIENCE_SUFFIX.sub("", text)
    text = re.sub(r"^#+\s*", "", text)
    text = re.sub(r"\s+", " ", text).strip(" \t:-–—|·#")
    return text[:160] or "Open role"


def name_from_email(email: str) -> str:
    if not email or "@" not in email:
        return ""
    local = email.split("@", 1)[0]
    local = re.sub(r"\d+", "", local)
    local = re.sub(r"[._\-]+", " ", local).strip()
    if not local:
        return ""
    return local.title()[:80]


def extract_emails(text: str) -> list[str]:
    found: list[str] = []
    seen: set[str] = set()
    for match in EMAIL_RE.findall(text or ""):
        email = match.lower()
        if any(part in email for part in SKIP_EMAIL_PARTS):
            continue
        if email not in seen:
            seen.add(email)
            found.append(email)
    return found


def parse_job_paste(raw: str) -> dict:
    """Best-effort parse of a LinkedIn (or other) job posting paste."""
    text = (raw or "").strip()
    lines = [clean_line(line) for line in text.splitlines()]
    lines = [line for line in lines if line]

    title = clean_title(lines[0]) if lines else "Open role"
    company = ""
    location = ""

    for line in lines[1:6]:
        lowered = line.lower()
        if lowered.startswith("company") or lowered.startswith("organisation") or lowered.startswith("organization"):
            company = clean_line(re.sub(r"^(company|organisation|organization)\s*[:\-–—]\s*", "", line, flags=re.I))
            continue
        if lowered.startswith("location") or lowered.startswith("venue"):
            location = clean_line(re.sub(r"^(location|venue)\s*[:\-–—]\s*", "", line, flags=re.I))
            continue
        if LOCATION_HINT.search(line) and not company and not location:
            location = line[:160]
            continue
        if "@" in line or re.match(r"^(contact|email|apply|experience|years)\b", lowered):
            continue
        if not company and not LOCATION_HINT.search(line) and len(line) <= 80:
            if "·" in line or " | " in line:
                parts = [part.strip() for part in re.split(r"\s*[·|]\s*", line) if part.strip()]
                if parts:
                    company = parts[0][:160]
                if len(parts) > 1:
                    location = location or parts[1][:160]
            elif not re.search(r"(experience|years|looking for|responsib|qualif)", line, re.I):
                skill_hits = sum(1 for word in SKILL_WORDS if word in lowered)
                if skill_hits < 3:
                    company = line[:160]

    emails = extract_emails(text)
    recruiter_name = _guess_recruiter_name(text, emails[0] if emails else "")
    if not recruiter_name and emails:
        recruiter_name = name_from_email(emails[0])

    return {
        "title": title,
        "company": company,
        "location": location,
        "description": text,
        "recruiter_email": emails[0] if emails else "",
        "recruiter_name": recruiter_name,
        "all_emails": emails,
    }


def _guess_recruiter_name(text: str, email: str) -> str:
    patterns = [
        r"(?:recruiter|hiring manager|talent partner|contact)[:\s]+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)",
        r"([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\s+[\-–]\s+(?:recruiter|talent)",
    ]
    for pattern in patterns:
        match = re.search(pattern, strip_emoji(text))
        if match:
            return match.group(1).strip()[:80]
    return name_from_email(email)


def extract_focus(description: str) -> list[str]:
    """Short, clean themes from a posting — never raw marketing lines."""
    blob = clean_line(description).lower()
    themes = []
    catalog = (
        ("cloud reliability and operations", ("reliability", "sre", "cloud operations", "uptime")),
        ("FinOps and cost management", ("finops", "cost", "capacity")),
        ("Linux and Windows administration", ("linux", "windows", "sysadmin", "administrator")),
        ("AWS, Azure, and GCP", ("aws", "azure", "gcp", "google cloud")),
        ("OpenShift and Kubernetes", ("openshift", "kubernetes", "k8s")),
        ("VMware and OpenStack", ("vmware", "openstack", "vsphere")),
        ("automation and CI/CD", ("terraform", "ansible", "ci/cd", "devops")),
    )
    for label, terms in catalog:
        if any(term in blob for term in terms):
            themes.append(label)
        if len(themes) == 3:
            break
    return themes
