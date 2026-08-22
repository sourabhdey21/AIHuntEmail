from pathlib import Path

from dotenv import load_dotenv
import os

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
UPLOAD_DIR = DATA_DIR / "uploads"
DB_PATH = DATA_DIR / "huntmail.db"

load_dotenv(ROOT / ".env")

DATA_DIR.mkdir(parents=True, exist_ok=True)
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


def smtp_email() -> str:
    return os.getenv("SMTP_EMAIL", "sourabhdey21@gmail.com").strip()


def smtp_app_password() -> str:
    return os.getenv("SMTP_APP_PASSWORD", "").strip()


def sender_name() -> str:
    return os.getenv("SENDER_NAME", "Sourabh Dey").strip()


def watch_interval_minutes() -> int:
    raw = os.getenv("WATCH_INTERVAL_MINUTES", "30")
    try:
        return max(10, int(raw))
    except ValueError:
        return 30
