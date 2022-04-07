import json
import os
import requests
import logging


logger = logging.getLogger(__name__)

PROJECT_ID_URL = \
    "http://metadata.google.internal/computeMetadata/v1/project/project-id"


def get_service_account_file() -> str | None:
    path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", None)

    if not path:
        logger.info("GOOGLE_APPLICATION_CREDENTIALS is not set")

    return path


def get_project_id() -> str:
    file = get_service_account_file()

    if not file:
        logger.info(
            f"Service account file is not set. Will use {PROJECT_ID_URL}")
        response = requests.get(
            url=PROJECT_ID_URL,
            headers={"Metadata-Flavor": "Google"}
        )
        return response.text
    else:
        with open(file) as fd:
            return json.load(fd)["project_id"]


def get_storage_url() -> str:
    return os.environ["FREESPEECH_STORAGE_URL"]


def get_notion_token() -> str:
    return os.environ["NOTION_TOKEN"]
