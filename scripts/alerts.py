# scripts/alerts.py

"""
Optional email alerting module.
Sends a summary email on workflow completion or on failure.
Configure via environment variables (see config.py).
"""

import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime

import pandas as pd

from scripts.logger import logger
from scripts.config import (
    ALERT_EMAIL_ENABLED, ALERT_EMAIL_TO, ALERT_EMAIL_FROM,
    ALERT_SMTP_HOST, ALERT_SMTP_PORT, ALERT_SMTP_PASSWORD,
)


def _build_body(subject_type: str, stats: dict) -> str:
    rows = "".join(
        f"<tr><td style='padding:6px 12px;border-bottom:1px solid #eee'>{k}</td>"
        f"<td style='padding:6px 12px;border-bottom:1px solid #eee'><b>{v}</b></td></tr>"
        for k, v in stats.items()
    )
    color = "#27ae60" if subject_type == "SUCCESS" else "#e74c3c"
    return f"""
    <html><body style='font-family:Arial,sans-serif;color:#333'>
    <h2 style='color:{color}'>GeoTab ETL — {subject_type}</h2>
    <p>Run completed at <b>{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</b></p>
    <table style='border-collapse:collapse;min-width:400px'>{rows}</table>
    </body></html>
    """


def send_summary_email(stats: dict, success: bool = True) -> None:
    """
    Send a workflow summary email if alerting is enabled.

    Args:
        stats:   Dict of key-value pairs to display in the email body.
        success: True for a success email, False for a failure/warning email.
    """
    if not ALERT_EMAIL_ENABLED:
        return
    if not all([ALERT_EMAIL_TO, ALERT_EMAIL_FROM, ALERT_SMTP_PASSWORD]):
        logger.warning("Email alerting enabled but ALERT_EMAIL_TO/FROM/PASSWORD not set. Skipping.")
        return

    status = "SUCCESS" if success else "FAILURE"
    subject = f"[GeoTab ETL] {status} — {datetime.now().strftime('%Y-%m-%d %H:%M')}"

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = ALERT_EMAIL_FROM
    msg["To"]      = ALERT_EMAIL_TO
    msg.attach(MIMEText(_build_body(status, stats), "html"))

    try:
        with smtplib.SMTP(ALERT_SMTP_HOST, ALERT_SMTP_PORT) as server:
            server.ehlo()
            server.starttls()
            server.login(ALERT_EMAIL_FROM, ALERT_SMTP_PASSWORD)
            server.sendmail(ALERT_EMAIL_FROM, ALERT_EMAIL_TO, msg.as_string())
        logger.info(f"Summary email sent to {ALERT_EMAIL_TO}.")
    except Exception as e:
        logger.warning(f"Failed to send email alert: {e}")
