import boto3
import os
import logging

logger = logging.getLogger(__name__)

FROM_EMAIL = os.getenv("SES_FROM_EMAIL")
BASE_URL = os.getenv("MAGIC_LINK_BASE_URL")


def get_ses_client():
    """Crează SES client când e nevoie"""
    return boto3.client(
        "ses",
        region_name=os.getenv("AWS_REGION", "us-east-1"),
        aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
    )


def send_magic_link(email: str, token: str):
    ses = get_ses_client()  # ✅ Crează doar când trimite email

    link = f"{BASE_URL}/auth/magic?token={token}"
    subject = "Your secure login link"
    body = f"Click here: {link}\n\nThis expires in 15 minutes."

    try:
        ses.send_email(
            Source=FROM_EMAIL,
            Destination={"ToAddresses": [email]},
            Message={
                "Subject": {"Data": subject},
                "Body": {"Text": {"Data": body}},
            },
        )
        logger.info(f"📧 Magic link sent to {email}")
        return True
    except Exception as e:
        logger.error(f"❌ SES send error: {e}")
        return False
