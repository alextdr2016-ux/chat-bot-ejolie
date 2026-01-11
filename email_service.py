import boto3
import os
import logging

logger = logging.getLogger(__name__)


def get_ses_client():
    """Crează SES client când e nevoie"""
    return boto3.client(
        "ses",
        region_name=os.getenv("AWS_REGION", "us-east-1").strip(),
        aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID").strip(),
        aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY").strip(),
    )


def send_magic_link(email: str, token: str):
    # ✅ Citește variabilele ACUM (la runtime, nu la import!)
    from_email = os.getenv("SES_FROM_EMAIL")
    base_url = os.getenv("MAGIC_LINK_BASE_URL")

    # ✅ CHECK dacă sunt setate
    if not from_email:
        logger.error("❌ SES_FROM_EMAIL not set!")
        return False
    if not base_url:
        logger.error("❌ MAGIC_LINK_BASE_URL not set!")
        return False

    ses = get_ses_client()
    link = f"{base_url}/auth/magic?token={token}"
    subject = "Your secure login link"
    body = f"Click here: {link}\n\nThis expires in 15 minutes."

    try:
        ses.send_email(
            Source=from_email,  # ✅ Folosește variabila locală
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
