import json
import os

SERVICE_ACCOUNT_FILE = os.environ["GOOGLE_APPLICATION_CREDENTIALS"]


with open(SERVICE_ACCOUNT_FILE) as fd:
    PROJECT_ID = json.load(fd)["project_id"]
