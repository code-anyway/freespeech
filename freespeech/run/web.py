import asyncio
import logging
import logging.config
from dataclasses import replace
from typing import Awaitable

import streamlit as st

from freespeech import env
from freespeech.api import synthesize, transcribe, transcript, translate
from freespeech.typing import (
    LANGUAGES,
    assert_never,
    is_media_platform,
    is_transcript_platform,
    platform,
)

logging_handler = ["google" if env.is_in_cloud_run() else "console"]

LOGGING_CONFIG = {
    "version": 1,
    "formatters": {
        "brief": {"format": "%(message)s"},
        "default": {
            "format": "%(asctime)s %(levelname)-8s %(name)-15s %(message)s",
            "datefmt": "%Y-%m-%d %H:%M:%S",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "default",
            "stream": "ext://sys.stdout",
        },
        "google": {"class": "google.cloud.logging.handlers.StructuredLogHandler"},
    },
    "loggers": {
        "discord": {"level": logging.INFO, "handlers": logging_handler},
        "freespeech": {"level": logging.INFO, "handlers": logging_handler},
        "aiohttp": {"level": logging.INFO, "handlers": logging_handler},
        "__main__": {"level": logging.INFO, "handlers": logging_handler},
    },
}

logging.config.dictConfig(LOGGING_CONFIG)
logger = logging.getLogger(__name__)


def log_user_action(action: str, **kwargs):
    logger.info(f"{action} {kwargs}")


async def _transcribe(url, lang, backend, size) -> str:
    t = await transcribe.transcribe(url, lang=lang, backend=backend)
    # NOTE: Bill seems to be the most popular. Doing this here because changing the
    # default in the library would break existing code.
    events = [
        replace(event, voice=replace(event.voice, character="Bill"))
        for event in t.events
    ]

    match (size):
        case "Small":
            window_size_ms = 0
        case "Medium":
            window_size_ms = 30_000
        case "Large":
            window_size_ms = 60_000
        case "Auto":
            window_size_ms = 0
        case x:
            assert_never(x)

    t = replace(
        t,
        events=transcript.compress(events, window_size_ms=window_size_ms),
    )
    transcript_url = await transcript.save(
        transcript=t,
        platform="Google",
        format="SSMD-NEXT",
        location=None,
    )
    return transcript_url


def transcribe_dialogue():
    source_language = st.selectbox(
        "My source is in:",
        options=LANGUAGES,
    )
    method = st.radio(
        "I want to transcribe using:",
        options=["Speech Recognition", "Subtitles"],
    )
    if method == "Speech Recognition":
        method = "Machine D"
    paragraph_size = st.radio(
        "I want the transcribed paragraphs to be:",
        options=["Auto", "Large", "Medium", "Small"],
    )
    return (source_language, method, paragraph_size)


async def translate_transcript_action(url, target_language):
    log_user_action("Translate transcript", url=url, target_language=target_language)
    st.write(
        "The translated transcript will be linked here soon. Please don't close the tab!"  # noqa E501
    )
    translated_transcript_url = await translate.translate(
        source=url,
        lang=target_language,
        format="SSMD-NEXT",
        platform="Google",
    )
    st.write(f"Here you are: [link]({translated_transcript_url})")


async def translate_video_action(
    url, source_language, method, paragraph_size, target_language
):
    log_user_action(
        "Translate video",
        url=url,
        source_language=source_language,
        method=method,
        paragraph_size=paragraph_size,
        target_language=target_language,
    )
    st.write(
        "The translated video will be linked here soon. Please don't close the tab!"  # noqa E501
    )
    transcript_url = await _transcribe(url, source_language, method, paragraph_size)

    translated_transcript_url = await translate.translate(
        source=transcript_url,
        lang=target_language,
        format="SSMD-NEXT",
        platform="Google",
    )
    dub_url = await synthesize.dub(
        await transcript.load(source=translated_transcript_url),
        is_smooth=True,
    )
    st.write(
        f"""Here you are:
    - [Translated Dub]({dub_url})
    - [Translated Transcript]({translated_transcript_url})
    - [Original Transcript]({transcript_url})
"""
    )


def start():
    return st.button(f"{st.session_state['option']}!")


def translate_flow(url: str) -> Awaitable | None:
    if is_media_platform(platform(url)):
        source_language, method, paragraph_size = transcribe_dialogue()
        target_language = st.selectbox(
            "I want my result to be in:",
            options=LANGUAGES,
        )

        if all((source_language, method, paragraph_size, target_language)):
            if start():
                return translate_video_action(
                    url, source_language, method, paragraph_size, target_language
                )

    if is_transcript_platform(platform(url)):
        target_language = st.selectbox(
            "I want my result to be in:",
            options=LANGUAGES,
        )
        if target_language:
            if start():
                return translate_transcript_action(url, target_language)

    return None


def transcribe_flow(url: str) -> Awaitable | None:
    if not is_media_platform(platform(url)):
        return None

    source_language, method, paragraph_size = transcribe_dialogue()

    async def action():
        log_user_action(
            "Transcribe",
            url=url,
            source_language=source_language,
            method=method,
            paragraph_size=paragraph_size,
        )
        st.write("The transcript will be linked here soon. Please don't close the tab!")
        transcript_url = await _transcribe(url, source_language, method, paragraph_size)
        st.write(f"Here you are: [link]({transcript_url})")

    if all((url, source_language, method, paragraph_size)):
        if start():
            return action()

    return None


def dub_flow(url: str) -> Awaitable | None:
    if not is_transcript_platform(platform(url)):
        return None

    async def action():
        log_user_action(
            "Dub",
            url=url,
        )
        st.write(
            "The dub of the transcript will be here soon. Please don't close the tab!"
        )
        dub_url = await synthesize.dub(
            await transcript.load(source=url),
            is_smooth=True,
        )
        st.write(f"Here you are: [link]({dub_url})")

    if start():
        return action()
    else:
        return None


st.title("Welcome to Freespeech!")
st.write("Please insert a quarter to continue.")


async def main():
    st.radio(
        "I want to:",
        key="option",
        index=0,
        options=["Translate", "Transcribe", "Dub"],
    )

    action = None
    match st.session_state["option"]:
        case "Translate":
            url = st.text_input(
                "Please paste a link to the video or transcript and hit Enter"
            )
            if url:
                action = translate_flow(url)
        case "Transcribe":
            url = st.text_input("Please paste a link to the video and hit Enter")
            if url:
                action = transcribe_flow(url)
        case "Dub":
            url = st.text_input("Please paste a link to the transcript and hit Enter")
            if url:
                action = dub_flow(url)

    if action:
        await action


if __name__ == "__main__":
    asyncio.run(main())
