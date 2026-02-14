import os
import boto3

FROM_EMAIL = os.environ.get("FROM_EMAIL", "")
TO_EMAIL = os.environ.get("REMINDER_EMAIL", "")

def handler(event, context):
    if not TO_EMAIL or not FROM_EMAIL:
        return {"status": "skip", "reason": "REMINDER_EMAIL or FROM_EMAIL not set"}
    ses = boto3.client("ses")
    ses.send_email(
        Source=FROM_EMAIL,
        Destination={"ToAddresses": [TO_EMAIL]},
        Message={
            "Subject": {"Data": "Twitter: schedule tomorrow's 3 tweets", "Charset": "UTF-8"},
            "Body": {
                "Text": {
                    "Data": "8 AM – educational\n1 PM – story/hot take\n6 PM – question\n\nRun: python3 schedule_tweets.py tweets.txt",
                    "Charset": "UTF-8",
                }
            },
        },
    )
    return {"status": "ok", "sent_to": TO_EMAIL}
