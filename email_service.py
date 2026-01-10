import os
import boto3

SES_REGION = os.getenv("SES_REGION", "us-east-1")
FROM_EMAIL = os.getenv("FROM_EMAIL", "no-reply@fabrex.org")

ses = boto3.client("ses", region_name=SES_REGION)


def send_magic_link(to_email: str, login_url: str):
    """
    Trimite un email simplu (text) cu magic link.
    """
    ses.send_email(
        Source=FROM_EMAIL,
        Destination={"ToAddresses": [to_email]},
        Message={
            "Subject": {"Data": "Your login link"},
            "Body": {
                "Text": {
                    "Data": f"Click the link to sign in:\n\n{login_url}\n\nThis link expires in 15 minutes."
                }
            }
        }
    )
