import smtplib
from email.message import EmailMessage
from pathlib import Path

from app.config import sender_name, smtp_app_password, smtp_email


class MailConfigError(RuntimeError):
    pass


def can_send() -> bool:
    return bool(smtp_email() and smtp_app_password())


def send_application(
    to_email: str,
    subject: str,
    body: str,
    resume_path: str = "",
    resume_name: str = "",
) -> None:
    from_email = smtp_email()
    password = smtp_app_password()
    if not from_email or not password:
        raise MailConfigError(
            "Add SMTP_APP_PASSWORD to your .env file. "
            "Create a Gmail app password at https://myaccount.google.com/apppasswords"
        )
    if not to_email or "@" not in to_email:
        raise MailConfigError("This job has no recruiter email to send to.")

    message = EmailMessage()
    message["From"] = f"{sender_name()} <{from_email}>"
    message["To"] = to_email
    message["Subject"] = subject
    message.set_content(body)

    if resume_path:
        path = Path(resume_path)
        if path.is_file():
            data = path.read_bytes()
            filename = resume_name or path.name
            message.add_attachment(
                data,
                maintype="application",
                subtype="pdf" if filename.lower().endswith(".pdf") else "octet-stream",
                filename=filename,
            )

    with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=30) as smtp:
        smtp.login(from_email, password)
        smtp.send_message(message)
