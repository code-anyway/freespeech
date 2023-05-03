import sys

# to make modules visible
sys.path.append("../")

import asyncio
from dataclasses import replace
from typing import Literal

import streamlit as st

from freespeech.api import synthesize, transcribe, transcript, translate
from freespeech.lib import youtube
from freespeech.types import (
    LANGUAGES,
    MEDIA_PLATFORMS,
    TRANSCRIPT_PLATFORMS,
    Language,
    Operation,
    SpeechToTextBackend,
    assert_never,
    platform,
)

ParagraphSize = Literal["Small", "Medium", "Large", "Auto"]
from freespeech.types import (
    Language,
    Operation,
    SpeechToTextBackend,
    assert_never,
    platform,
)


async def _transcribe(
    url: str,
    lang: Language,
    backend: SpeechToTextBackend,
    size: ParagraphSize,
) -> str:
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


async def estimate_operation_duration(url: str, operation: Operation) -> int | None:
    """Return estimated duration of an operation for a video or transcript in seconds.

    Args:
        url (str): URL of a video or transcript.
        operation (Operation): Operation to estimate duration for.

    Returns:
        Estimated duration in seconds.
    """
    _platform = platform(url)

    match _platform:
        case "YouTube":
            metric = (await youtube.get_meta(url)).duration_ms
        case "Google" | "Notion":
            metric = len(
                " ".join(
                    " ".join(event.chunks)
                    for event in (await transcript.load(url)).events
                )
            )
        case "GCS":
            raise NotImplementedError("GCS is not supported yet")
        case "Twitter":
            return None
        case _platform:
            assert_never(_platform)

    match operation:
        case "Transcribe":
            return round(metric / 1000 + metric / 2581)
        case "Translate":
            return round(metric / 102.679)
        case "Synthesize":
            return round(metric / 25)
        case x:
            assert_never(x)


def seconds_to_human_readable(seconds: int | None) -> str:
    """Convert seconds to human readable format.

    Args:
        seconds (int): Seconds to convert.

    Returns:
        Human readable format.
    """
    if seconds is None:
        return ""
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    seconds = seconds % 60

    res = ""
    if hours:
        res += f" {hours} hour{'s' if hours > 1 else ''}"
    if minutes:
        res += f" {minutes} minute{'s' if minutes > 1 else ''}"
    if not res:
        res += f" {seconds} second{'s' if seconds > 1 else ''}"

    return res.strip()


def platform_info(url):
    try:
        if not url:
            return "unfilled"
        if platform(url) in MEDIA_PLATFORMS:
            return "video"
        if platform(url) in TRANSCRIPT_PLATFORMS:
            return "transcript"
    except ValueError as ve:
        st.text("Sorry! The link may be malformed or the platform is unsupported.")
        return ""
    return ""


def transcribe_dialogue():
    language = st.selectbox(
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
    return (language, method, paragraph_size)


def translate_flow():
    url = st.text_input(
        "Please paste a link to the transcript/video (make sure to hit Enter)"
    )
    _platform_info = platform_info(url)
    if not _platform_info:
        return lambda: None
    match _platform_info:
        case "video":
            language, method, paragraph_size = transcribe_dialogue()
            target_language = st.selectbox(
                "I want my result to be in:",
                options=LANGUAGES,
            )
            if not all([language, method, paragraph_size, target_language]):
                return lambda: None

            async def action():
                st.text(
                    f"The translated video will be linked here soon. Please don't close the tab!"
                )
                transcript_url = await _transcribe(
                    url, language, method, paragraph_size
                )
                print("Transcribed")
                translated_transcript_url = await translate.translate(
                    source=transcript_url,
                    lang=target_language,
                    format="SSMD-NEXT",
                    platform="Google",
                )
                print("Translated")
                dub_url = await synthesize.dub(
                    await transcript.load(source=translated_transcript_url),
                    is_smooth=True,
                )
                st.text(f"Here you are: {dub_url}")

            return action
        case "transcript":
            print("transcript!")
            return lambda: None
        case "unfilled":
            return lambda: None
    return lambda: None


def transcribe_flow():
    inp = st.text_input("Please paste a link to the video")
    return lambda: None


def dub_flow():
    return lambda: None


st.title("Welcome! We're under construction")


async def main():
    if "option" not in st.session_state:
        st.session_state["option"] = "Translate"

    st.radio(
        "I want to:",
        key="option",
        options=["Translate", "Transcribe", "Dub"],
    )
    action = lambda: None

    match st.session_state["option"]:
        case "Translate":
            action = translate_flow()
        case "Transcribe":
            action = transcribe_flow()
        case "Dub":
            action = dub_flow()

    start = st.button(f"{st.session_state['option']}!")
    if start and (res := action()):
        await res


if __name__ == "__main__":
    asyncio.run(main())


# st.write(input)
# reset = text.empty()
# attempt = st.text_input("hi")

# attempt = ""
