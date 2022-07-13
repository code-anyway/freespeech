import base64

from freespeech.functions import pubsub_to_telegram

MESSAGE = '{"httpRequest":{},"insertId":"62ceacfd000883ddea6a6745","jsonPayload":{"client":"telegram_1","full_name":"alex che","message":"user_says: dub https://docs.google.com/document/d/15XayUk8kOLlPQB8MS4yZojBRlYomETnQ5yr-BpZy8s0/edit","text":"dub https://docs.google.com/document/d/15XayUk8kOLlPQB8MS4yZojBRlYomETnQ5yr-BpZy8s0/edit","user_id":470696723,"username":"alexandercherednichenko"},"labels":{"commit-sha":"ed0094ba757e34ed49384857f9f3f9e6af534940","gcb-build-id":"e775f996-eae3-460e-837e-8dec0434bb3d","gcb-trigger-id":"516f800f-f70d-47a0-9008-cafc8e9a0dbd","instanceId":"00c527f6d43358395d7f36eaae5044ddc068b8dea4ff85da3fbe9983983639ceadbabbd296c8b0f3b6360ba6978085718e368f61e50db21f0f4d1ab20e990bbd07","interface":"conversation_telegram","managed-by":"gcp-cloud-build-deploy-cloud-run","python_logger":"freespeech.api.telegram"},"logName":"projects/freespeech-343914/logs/run.googleapis.com%2Fstderr","receiveTimestamp":"2022-07-13T11:31:09.566598821Z","resource":{"labels":{"configuration_name":"freespeech-telegram","location":"us-central1","project_id":"freespeech-343914","revision_name":"freespeech-telegram-00045-miw","service_name":"freespeech-telegram"},"type":"cloud_run_revision"},"severity":"INFO","sourceLocation":{"file":"/opt/venv/lib/python3.10/site-packages/freespeech/api/telegram.py","function":"_message","line":"85"},"timestamp":"2022-07-13T11:31:09.558045Z"}'
ERROR_MESSAGE = \
'{"httpRequest":{},"insertId":"62cf084d000421dc5f64bbb3","jsonPayload":{"client":"telegram_1","error_details":"400, message=\'Missing document url. Try something that starts with https://docs.google.com/\\nTry `dub https://docs.google.com/document/d/1FbV0eW4Q-yKWYjPkMRCrGd2yD78n7MtswVmN9LSo4mA/edit` or just /help\', url=URL(\'https://freespeech-chat-qux7zlmkmq-uc.a.run.app/say\')","full_name":"Artyom Astafurov","message":"conversation_error: Missing document url. Try something that starts with https://docs.google.com/\\nTry `dub https://docs.google.com/document/d/1FbV0eW4Q-yKWYjPkMRCrGd2yD78n7MtswVmN9LSo4mA/edit` or just /help","request":"hello world","user_id":5178257111,"username":"astaff239"},"labels":{"commit-sha":"2dc12ef8aa93295d97e224c6f699db0516791895","gcb-build-id":"490c8b5c-7347-4eda-9461-dba4f3256766","gcb-trigger-id":"516f800f-f70d-47a0-9008-cafc8e9a0dbd","instanceId":"00c527f6d4d302d3bab4f1125985132385ba6be77ca5558f7363334fef2eaced26dd3483f34108f0fde0c9b6d8ab71cd6d4d2240f97c2691750ee3df48872c2c5c","interface":"conversation_telegram","managed-by":"gcp-cloud-build-deploy-cloud-run","python_logger":"freespeech.api.telegram"},"logName":"projects/freespeech-343914/logs/run.googleapis.com%2Fstderr","receiveTimestamp":"2022-07-13T18:00:45.428615642Z","resource":{"labels":{"configuration_name":"freespeech-telegram","location":"us-central1","project_id":"freespeech-343914","revision_name":"freespeech-telegram-00047-guh","service_name":"freespeech-telegram"},"type":"cloud_run_revision"},"severity":"ERROR","sourceLocation":{"file":"/opt/venv/lib/python3.10/site-packages/freespeech/api/telegram.py","function":"_message","line":"126"},"timestamp":"2022-07-13T18:00:45.270812Z"}'


def test_format():
    res = pubsub_to_telegram.format(MESSAGE)
    assert (
        res
        == "*alex che*: `dub https://docs.google.com/document/d/15XayUk8kOLlPQB8MS4yZojBRlYomETnQ5yr-BpZy8s0/edit`"
    )

    res = pubsub_to_telegram.format(ERROR_MESSAGE)
    assert (
        res
        == "Error\n*Artyom Astafurov*: `hello world`\n\n`conversation_error: Missing document url. Try something that starts with https://docs.google.com/\nTry `dub https://docs.google.com/document/d/1FbV0eW4Q-yKWYjPkMRCrGd2yD78n7MtswVmN9LSo4mA/edit` or just /help`"
    )


def _test_receive():
    message = base64.encodebytes(MESSAGE.encode("utf-8"))
    pubsub_to_telegram.receive({"data": message}, None)

    message = base64.encodebytes(ERROR_MESSAGE.encode("utf-8"))
    pubsub_to_telegram.receive({"data": message}, None)
