# Service: speech
# POST /media/{id}/{lang}/transcribe
# Async. Launches a transcription job that will update media's transcript for a given language
# TODO: return a job id, maintain a jon queue, don't allow duplicates.


def transcribe(url: str, lang: str) -> Transcript:
    media = get_media(url)

    if not media.audio:
        raise RuntimeError(f"No audio: {url} (id={media._id})")

    audio, *tail = media.audio

    if tail:
        logger.warning(f"Extra audio tracks found for {url}: {tail}")

    mono_audio = media_ops.downmix_stereo_to_mono(
        audio, storage_url=env.get_storage_url()
    )
    transcript = speech.transcribe(mono_audio, lang=lang)

    datastore.put(transcript)

    return transcript



