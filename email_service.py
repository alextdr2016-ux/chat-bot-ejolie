import boto3
import os
import logging

logger = logging.getLogger(__name__)

SES_REGION = os.getenv("SES_REGION", "us-east-1")
SES_SENDER_EMAIL = os.getenv("SES_SENDER_EMAIL")
APP_BASE_URL = os.getenv("APP_BASE_URL", "https://app.fabrex.org")

ses_client = boto3.client("ses", region_name=SES_REGION)


def send_magic_link_email(to_email: str, token: str):
    """
    Trimite email cu link magic de autentificare
    """
    login_link = f"{APP_BASE_URL}/auth/login?token={token}"

    subject = "Autentificare securizată – Fabrex"
    body_text = f"""
Salut 👋,

Ai cerut autentificare pe Fabrex.

Apasă pe linkul de mai jos pentru a te loga:
{login_link}

⏱ Linkul este valabil 15 minute.

Dacă nu ai cerut acest email, îl poți ignora.

– Echipa Fabrex
"""

    try:
        response = ses_client.send_email(
            Source=SES_SENDER_EMAIL,
            Destination={"ToAddresses": [to_email]},
            Message={
                "Subject": {"Data": subject, "Charset": "UTF-8"},
                "Body": {
                    "Text": {"Data": body_text, "Charset": "UTF-8"}
                }
            }
        )

        logger.info(f"📧 Magic link email sent to {to_email}")
        return True

    except Exception as e:
        logger.error(f"❌ SES email error: {e}")
        return False
