import functools
import json
import logging
import os

import requests

logger = logging.getLogger(__name__)

PROJECT_ID_URL = "http://metadata.google.internal/computeMetadata/v1/project/project-id"


@functools.cache
def get_service_account_file() -> str | None:
    path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", None)

    if not path:
        logger.warning("GOOGLE_APPLICATION_CREDENTIALS is not set")

    return path


@functools.cache
def is_in_cloud_run() -> bool:
    try:
        response = requests.get(
            url=PROJECT_ID_URL, headers={"Metadata-Flavor": "Google"}
        )
        if response.ok:
            logger.info("Detected running in Google environment")
            return True
        else:
            return False
    except requests.exceptions.ConnectionError:
        logger.info("Detected running in local environment")
        return False


@functools.cache
def get_project_id() -> str:
    if is_in_cloud_run():
        response = requests.get(
            url=PROJECT_ID_URL, headers={"Metadata-Flavor": "Google"}
        )
        return response.text
    else:
        file = get_service_account_file()
        if not file:
            raise RuntimeError("No Google credentials file on local environment")
        with open(file) as fd:
            return str(json.load(fd)["project_id"])


@functools.cache
def get_storage_url() -> str:
    bucket = os.environ.get("FREESPEECH_STORAGE_BUCKET", None)

    if not bucket:
        raise RuntimeError("Environment variable 'FREESPEECH_STORAGE_BUCKET' not set")

    return f"gs://{bucket}"


@functools.cache
def get_notion_token() -> str:
    token = os.environ.get("NOTION_TOKEN", None)

    if not token:
        raise RuntimeError("Environment variable 'NOTION_TOKEN' is not set.")

    return token


@functools.cache
def get_deepgram_token() -> str:
    token = os.environ.get("DEEPGRAM_TOKEN", None)

    if not token:
        raise RuntimeError("Environment variable 'DEEPGRAM_TOKEN' is not set.")

    return token


@functools.cache
def get_crud_service_url() -> str:
    url = os.environ.get("FREESPEECH_CRUD_SERVICE_URL", None)

    if not url:
        raise RuntimeError(
            "Environment variable 'FREESPEECH_CRUD_SERVICE_URL' is not set."
        )

    return url


def get_chat_service_url() -> str:
    url = os.environ.get("FREESPEECH_CHAT_SERVICE_URL", None)

    if not url:
        raise RuntimeError(
            "Environment variable 'FREESPEECH_CHAT_SERVICE_URL' is not set."
        )

    return url


@functools.cache
def get_dub_service_url() -> str:
    url = os.environ.get("FREESPEECH_DUB_SERVICE_URL", None)

    if not url:
        raise RuntimeError(
            "Environment variable 'FREESPEECH_DUB_SERVICE_URL' is not set."
        )

    return url


@functools.cache
def get_azure_config() -> tuple[str, str]:
    azure_key = os.environ.get("AZURE_SUBSCRIPTION_KEY", None)
    azure_region = os.environ.get("AZURE_REGION", None)

    if not azure_key or not azure_region:
        raise RuntimeError(
            "Both AZURE_SUBSCRIPTION_KEY and AZURE_REGION "
            "env vars are required to work with Azure TTS"
        )
    return azure_key, azure_region


@functools.cache
def get_azure_conversations_token() -> str:
    token = os.environ.get("AZURE_CONVERSATIONS_TOKEN", None)

    if not token:
        raise RuntimeError(
            "Environment variable `AZURE_CONVERSATIONS_TOKEN` is not set"
        )

    return token


@functools.cache
def get_azure_storage_connection_string() -> str:
    token = os.environ.get("AZURE_STORAGE_CONNECTION_STRING", None)

    if not token:
        raise RuntimeError(
            "Environment variable `AZURE_STORAGE_CONNECTION_STRING` is not set"
        )

    return token


@functools.cache
def get_telegram_bot_token() -> str:
    token = os.environ.get("TELEGRAM_BOT_TOKEN", None)

    if not token:
        raise RuntimeError("Environment variable TELEGRAM_BOT_TOKEN is not set. ")

    return token


@functools.cache
def get_telegram_webhook_url() -> str:
    url = os.environ.get("TELEGRAM_WEBHOOK_URL", None)

    if not url:
        raise RuntimeError("For Telegram, TELEGRAM_WEBHOOK_URL should be set.")

    return url


def get_transcript_service_url() -> str:
    url = os.environ.get("FREESPEECH_TRANSCRIPT_SERVICE_URL", None)

    if not url:
        raise RuntimeError("FREESPEECH_TRANSCRIPT_SERVICE_URL is not set.")

    return url


def get_media_service_url() -> str:
    url = os.environ.get("FREESPEECH_MEDIA_SERVICE_URL", None)

    if not url:
        raise RuntimeError("FREESPEECH_MEDIA_SERVICE_URL is not set.")

    return url
