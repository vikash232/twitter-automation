"""
Post a tweet via Twitter API v2 using tweepy (OAuth 1.0a).
Credentials from Secrets Manager (consumer_key, consumer_secret, access_token, access_token_secret).
Tweet text from event["text"] or from SSM Parameter Store key in event["ssm_key"] or event["slot"].
"""
import json
import boto3
import tweepy

SSM_PREFIX = "/twitter/tweets"


def _get_creds(secret_arn):
    sm = boto3.client("secretsmanager")
    secret = sm.get_secret_value(SecretId=secret_arn)
    raw = json.loads(secret["SecretString"])
    return {k: (v.strip() if isinstance(v, str) else v) for k, v in raw.items()}


def _get_text_from_ssm(ssm_key):
    ssm = boto3.client("ssm")
    p = ssm.get_parameter(Name=ssm_key, WithDecryption=True)
    return p["Parameter"]["Value"].strip()


def _post_tweet(text, creds):
    client = tweepy.Client(
        consumer_key=creds["consumer_key"],
        consumer_secret=creds["consumer_secret"],
        access_token=creds["access_token"],
        access_token_secret=creds["access_token_secret"],
    )
    resp = client.create_tweet(text=text)
    return {"data": {"id": resp.data["id"]}}


def handler(event, context):
    import os
    secret_arn = os.environ.get("TWITTER_SECRET_ARN")
    if not secret_arn:
        return {"status": "error", "reason": "TWITTER_SECRET_ARN not set"}

    text = (event or {}).get("text")
    ssm_key = (event or {}).get("ssm_key")
    slot = (event or {}).get("slot")

    if not text and ssm_key:
        text = _get_text_from_ssm(ssm_key)
    if not text and slot:
        text = _get_text_from_ssm(f"{SSM_PREFIX}/{slot}")

    if not text or len(text.strip()) == 0:
        return {"status": "skip", "reason": "no tweet text (set event.text or event.slot / ssm_key)"}

    if len(text) > 280:
        return {"status": "error", "reason": "tweet longer than 280 characters"}

    creds = _get_creds(secret_arn)
    result = _post_tweet(text.strip(), creds)
    return {"status": "ok", "tweet_id": result.get("data", {}).get("id"), "text_preview": text[:50] + "..."}
