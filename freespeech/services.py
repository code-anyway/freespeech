from freespeech.types import Language, Transcript, Media
from freespeech import youtube, datastore, env, speech, language, media

import dataclasses


VOICES = {
    "ru-RU": "ru-RU-Wavenet-C",
    "en-US": "en-US-Wavenet-E"
}


def transcribe(audio_id: str, lang: str) -> str:
    audio = datastore.get(audio_id, "audio")
    mono_audio = media.downmix_stereo_to_mono(
        audio, storage_url=env.get_storage_url())
    transcript = speech.transcribe(mono_audio)
    datastore.put(transcript)
    return transcript._id


def download_and_transcribe(url: str, lang: str) -> str:
    res = datastore.get_by_key_value("origin", url, "media")
    if res:
        media = res[0]
    else:
        media = youtube.download(url, env.get_storage_url())
        media = dataclasses.replace(
            media,
            audio=[
                dataclasses.replace(
                    a,
                    lang=lang,
                    storage_url=env.get_storage_url()) for a in media.audio])
    datastore.put(media)
    audio, = media.audio
    return transcribe(audio._id, lang=lang)


def translate(_id: str, lang: Language) -> str:
    transcript = datastore.get(_id, "transcript")
    translation = language.translate(transcript, source=None, target=lang)

    assert isinstance(translation, Transcript)

    datastore.put(translation)
    return translation._id


def synthesize(_id: str) -> str:
    transcript = datastore.get(_id, "transcript")
    audio = speech.synthesize(
        transcript,
        VOICES[transcript.lang],
        storage_url=env.get_storage_url()
    )

    datastore.put(audio)
    return audio._id


def voiceover(url, audio_id) -> str:
    original_media, = datastore.get_by_key_value("origin", url, "media")
    new_audio = datastore.get(audio_id, "audio")
    original_audio, = original_media.audio
    mixed_audio = media.mix(
        [original_audio, new_audio],
        weights=[2, 10],
        storage_url=env.get_storage_url())

    final_video, final_audio = media.add_audio(
        original_media.video[0],
        mixed_audio,
        storage_url=env.get_storage_url())

    def _translate(text: str) -> str:
        return str(language.translate(
            text,
            original_audio.lang,
            new_audio.lang))

    translated_media = Media(
        audio=[final_audio],
        video=[final_video],
        title=_translate(original_media.title),
        description=_translate(original_media.description),
        tags=original_media.tags,
        origin=original_media.origin
    )

    datastore.put(translated_media)
    return translated_media._id


def upload(media_id, url):
    pass
