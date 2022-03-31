import json
import os


def get_service_account_file() -> str:
    return os.environ["GOOGLE_APPLICATION_CREDENTIALS"]


def get_project_id() -> str:
    with open(get_service_account_file()) as fd:
        return json.load(fd)["project_id"]


def get_storage_url() -> str:
    return os.environ["FREESPEECH_STORAGE_URL"]


def get_notion_token() -> str:
    return os.environ["NOTION_TOKEN"]
