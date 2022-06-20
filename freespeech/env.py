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
def get_project_id() -> str:
    file = get_service_account_file()

    if not file:
        logger.warning(f"Service account file is not set. Will use {PROJECT_ID_URL}")
        response = requests.get(
            url=PROJECT_ID_URL, headers={"Metadata-Flavor": "Google"}
        )
        return response.text
    else:
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
