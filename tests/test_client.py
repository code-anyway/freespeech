import asyncio
import pytest

from freespeech import client
from freespeech.lib import language, speech
from freespeech.types import Clip

CRUD_SERVICE_URL = "https://freespeech-crud-qux7zlmkmq-uc.a.run.app"
DUB_SERVICE_URL = "https://freespeech-qux7zlmkmq-uc.a.run.app"

SAMPLES_PRESIDENT_OF_UA = [
    "https://www.youtube.com/watch?v=k_Nmzh7KRMU",  # 56
    "https://www.youtube.com/watch?v=PRLIlthRIwA",  # 55
    # "https://www.youtube.com/watch?v=TStisIimBwo",  # 54
    "https://www.youtube.com/watch?v=Q3RGBV74SJ4",  # 53
    "https://www.youtube.com/watch?v=Q4qQs5p0DMo",  # 52
    "https://www.youtube.com/watch?v=pa1OL_nT4Rw",  # 51
    "https://www.youtube.com/watch?v=POT1KFffDzI",  # 50
    "https://www.youtube.com/watch?v=RqvZvEAPFwg",  # 49
    # "https://www.youtube.com/watch?v=YTBFBeQedvA",  # 48
    "https://www.youtube.com/watch?v=FPQqfCk5w3k",  # 47
    "https://www.youtube.com/watch?v=7bFpIHZQw9o",  # 46
    "https://www.youtube.com/watch?v=Nbpqzq5YsuM",  # 45
]

CLIPS = {
    'https://www.youtube.com/watch?v=7bFpIHZQw9o': '6366e2f8-8194-4f53-96c2-706a7ab0e5fc',
    'https://www.youtube.com/watch?v=FPQqfCk5w3k': '6877ea03-587b-42d0-8df1-e06078189b0f',
    'https://www.youtube.com/watch?v=Nbpqzq5YsuM': '580cc9e2-13b7-48ce-94fa-726e79d5d809',
    'https://www.youtube.com/watch?v=POT1KFffDzI': '9369ad5d-4051-4dc4-bc53-94bb036fe012',
    'https://www.youtube.com/watch?v=PRLIlthRIwA': '580cc9e2-13b7-48ce-94fa-726e79d5d809',
    'https://www.youtube.com/watch?v=Q3RGBV74SJ4': 'c35443c4-bc1c-4933-bcf1-8a0a8fe8d0e9',
    'https://www.youtube.com/watch?v=Q4qQs5p0DMo': '6877ea03-587b-42d0-8df1-e06078189b0f',
    'https://www.youtube.com/watch?v=RqvZvEAPFwg': 'a615c6d2-dc0b-47e3-be83-8eb08e09282f',
    'https://www.youtube.com/watch?v=YTBFBeQedvA': 'ba8bc359-fcff-4880-b5dc-5c2ab92956c4',
    'https://www.youtube.com/watch?v=k_Nmzh7KRMU': 'fc0ce641-c714-4a30-9eca-15b07949c495',
    'https://www.youtube.com/watch?v=pa1OL_nT4Rw': '580cc9e2-13b7-48ce-94fa-726e79d5d809'
}

DUBS = [
    ('https://www.youtube.com/watch?v=7bFpIHZQw9o', 'https://storage.googleapis.com/freespeech-output/clips/51e83dc8-ed50-4836-b6d9-175a07530d2d.mp4'),
    # ('https://www.youtube.com/watch?v=FPQqfCk5w3k', 'https://storage.googleapis.com/freespeech-output/clips/e957cf04-c1a6-407f-9e5b-5dbd8bec58e6.mp4'),
    # ('https://www.youtube.com/watch?v=PRLIlthRIwA', 'https://storage.googleapis.com/freespeech-output/clips/ea776fc5-994b-4581-981d-39c4a20c0ecd.mp4'),
    # ('https://www.youtube.com/watch?v=POT1KFffDzI', 'https://storage.googleapis.com/freespeech-output/clips/dfd732ad-2f69-4681-96fa-7ce14974e4d7.mp4'),
    # ('https://www.youtube.com/watch?v=PRLIlthRIwA', 'https://storage.googleapis.com/freespeech-output/clips/116cdc5c-60bc-4300-ab86-a94c35f7e92d.mp4'),
    # ('https://www.youtube.com/watch?v=Q3RGBV74SJ4', 'https://storage.googleapis.com/freespeech-output/clips/b723c257-3537-4649-a0a6-277a16e4b57a.mp4'),
    # ('https://www.youtube.com/watch?v=FPQqfCk5w3k', 'https://storage.googleapis.com/freespeech-output/clips/ab79c348-5ddf-4445-a4a8-099ffd84ac68.mp4'),
    # ('https://www.youtube.com/watch?v=RqvZvEAPFwg', 'https://storage.googleapis.com/freespeech-output/clips/8bcc757e-6d9f-4656-a1d9-95e006121b8b.mp4'),
    # ('https://www.youtube.com/watch?v=k_Nmzh7KRMU', 'https://storage.googleapis.com/freespeech-output/clips/fcaab9a4-026b-448a-89dd-d20fa8271d11.mp4'),
    # ('https://www.youtube.com/watch?v=PRLIlthRIwA', 'https://storage.googleapis.com/freespeech-output/clips/741ef52c-0646-403f-9a98-5bbb12492562.mp4'),
]


@pytest.mark.asyncio
async def test_upload_dub():
    # clips = await asyncio.gather(*[
    #     client.upload(CRUD_SERVICE_URL, url, "en-US")
    #     for url in SAMPLES_PRESIDENT_OF_UA], return_exceptions=True)

    # assert {url: clip._id for url, clip in zip(SAMPLES_PRESIDENT_OF_UA, clips)} == {}
    clips = await asyncio.gather(*[client.clip(CRUD_SERVICE_URL, _id) for _id in CLIPS.values()])
    dub_ru = [_dub(clip, "ru-RU") for clip in clips]
    dub_en = [_dub(clip, "en-US") for clip in clips]
    dubs = \
        list(await asyncio.gather(*dub_ru, return_exceptions=True)) + \
        list(await asyncio.gather(*dub_en, return_exceptions=True))

    # res = [(clip.origin, url) for clip, url in zip(clips, urls)]
    # assert res == []
    res = [f"Origin: {dub.origin}\nDub {dub.lang}): {await client.video(CRUD_SERVICE_URL, dub._id)}"
           for dub in dubs if isinstance(dub, Clip)]
    print("\n\n".join(res))
    assert False


async def _dub(clip, lang):
    normalized_transcript = speech.normalize_speech(clip.transcript)
    if clip.lang != lang:
        normalized_transcript = language.translate_events(normalized_transcript,
                                                          clip.lang,
                                                          lang)
    dubbed_clip = await client.dub(DUB_SERVICE_URL,
                                   clip_id=clip._id,
                                   transcript=normalized_transcript,
                                   default_character="Alan Turing",
                                   lang=lang,
                                   pitch=0.0,
                                   weights=(2, 10))
    return dubbed_clip
