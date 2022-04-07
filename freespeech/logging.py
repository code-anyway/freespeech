import google.cloud.logging
from google.cloud.logging.handlers import CloudLoggingHandler


class GoogleCloudLoggingHandler(CloudLoggingHandler):
    def __init__(self):
        client = google.cloud.logging.Client()
        super().__init__(client=client)
