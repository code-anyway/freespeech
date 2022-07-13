import base64
import json
from typing import Dict

import requests


def format(message: str) -> str:
    data: Dict = json.loads(message)

    payload = data["jsonPayload"]
    display_name = (
        payload.get("full_name", None)
        or payload.get("username", None)
        or payload.get("user_id", None)
        or "<unknown>"
    )
    text = payload.get("text", "<unknown>")

    if "error_details" in payload:
        error_message = payload.get("message", "<unknown>")
        user_request = payload.get("request", "<unknown>")
        markdown = f"Error\n*{display_name}*: `{user_request}`\n\n`{error_message}`"
    else:
        markdown = f"*{display_name}*: `{text}`"

    return markdown


def receive(event, context):
    """Triggered from a message on a Cloud Pub/Sub topic.
    Args:
         event (dict): Event payload.
         context (google.cloud.functions.Context): Metadata for the event.
    """
    pubsub_message = base64.b64decode(event["data"]).decode("utf-8")

    try:
        text = format(pubsub_message)
    except Exception as e:
        print(e)
        text = str(pubsub_message)

    payload = {
        "chat_id": "-718305997",
        "parse_mode": "markdown",
        "text": f"{text}",
        "disable_notification": True,
        "disable_web_page_preview": True,
    }
    url = "https://api.telegram.org/bot{}/sendMessage"  # noqa: E501

    response = requests.post(url, data=payload)
    response.raise_for_status()
