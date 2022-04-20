import pytest
from freespeech import client
from freespeech.lib import speech

CRUD_SERVICE_URL = "https://freespeech-qux7zlmkmq-uc.a.run.app"
DUB_SERVICE_URL = "https://freespeech-qux7zlmkmq-uc.a.run.app"
PRESIDENT_OF_UA_DAY_56 = "https://www.youtube.com/watch?v=k_Nmzh7KRMU"


@pytest.mark.asyncio
async def test_upload_dub():
    clip = await client.upload(CRUD_SERVICE_URL, PRESIDENT_OF_UA_DAY_56, "en-US")
    assert clip.transcript

    normalized_transcript = speech.normalize_speech(clip.transcript)

    from pprint import pprint
    pprint(clip.transcript)
    pprint(normalized_transcript)

    assert False
    # dubbed_clip = await client.dub(DUB_SERVICE_URL,
    #                                clip_id=clip._id,
    #                                transcript=normalized_transcript,
    #                                default_character="Alan Turing",
    #                                lang="en-US",
    #                                pitch=0.0,
    #                                weights=(2, 10))
    # public_url = await client.video(CRUD_SERVICE_URL, dubbed_clip._id)
    # assert public_url == ""