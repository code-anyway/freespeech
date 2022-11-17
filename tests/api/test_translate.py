import pytest

from freespeech.api import transcript, translate


@pytest.mark.asyncio
async def test_translate():
    transcript_url = "https://docs.google.com/document/d/1FbV0eW4Q-yKWYjPkMRCrGd2yD78n7MtswVmN9LSo4mA/"  # noqa: E501
    SOURCE_LANG = "uk-UA"
    TARGET_LANG = "en-US"

    transcript_source = await transcript.load(transcript_url)
    assert transcript_source.lang == SOURCE_LANG, "Source URL: {transcript_url}"

    translated_url = await translate.translate(
        source=transcript_url, lang=TARGET_LANG, format="SSMD-NEXT", platform="Google"
    )
    assert translated_url.startswith("https://docs.google.com/document/d/")

    translated = await transcript.load(translated_url)
    assert translated.lang == TARGET_LANG, f"Translated URL: {translated_url}"
