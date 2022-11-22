import asyncio
import difflib
import logging
import re
import xml.etree.ElementTree as ET
from dataclasses import replace
from functools import cache
from itertools import groupby
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Dict, Sequence, Tuple
from uuid import uuid4

import aiohttp
from deepgram import Deepgram
from google.api_core import exceptions as google_api_exceptions
from google.cloud import speech as speech_api
from google.cloud import texttospeech as google_tts
from google.cloud.speech_v1.types.cloud_speech import LongRunningRecognizeResponse
from pydantic.dataclasses import dataclass

from freespeech import env
from freespeech.lib import concurrency, media
from freespeech.lib.storage import obj
from freespeech.lib.text import (
    capitalize_sentence,
    chunk,
    is_sentence,
    lemmas,
    make_sentence,
    remove_symbols,
    sentences,
    split_sentences,
)
from freespeech.types import (
    CHARACTERS,
    Audio,
    Character,
    Event,
    Language,
    Literal,
    ServiceProvider,
    TranscriptionModel,
    Voice,
    assert_never,
    is_character,
)

logger = logging.getLogger(__name__)


@dataclass
class AzureEvent:
    offset: str
    duration: str
    offsetInTicks: int
    durationInTicks: int


@dataclass
class Phrase:
    lexical: str
    itn: str
    maskedITN: str
    display: str


@dataclass
class CandidateWord(AzureEvent):
    confidence: float
    word: str


@dataclass
class CandidatePhrase(Phrase):
    confidence: float
    words: list[CandidateWord]


@dataclass
class RecognizedPhrase(AzureEvent):
    recognitionStatus: Literal["Success"]
    channel: int
    nBest: list[CandidatePhrase]
    speaker: int = 0


Normalization = Literal["break_ends_sentence", "extract_breaks_from_sentence"]

MAX_CHUNK_LENGTH = 1000  # Google Speech API Limit

# Let's give voices real names and map them to API-specific names
# https://docs.microsoft.com/en-us/azure/cognitive-services/speech-service/language-support
# https://cloud.google.com/text-to-speech/docs/voices
VOICES: Dict[Character, Dict[Language, Tuple[ServiceProvider, str]]] = {
    "Ada": {
        "en-US": ("Google", "en-US-Wavenet-F"),
        "ru-RU": ("Google", "ru-RU-Wavenet-E"),
        "pt-PT": ("Google", "pt-PT-Wavenet-D"),
        "pt-BR": ("Google", "pt-BR-Wavenet-A"),
        "de-DE": ("Azure", "de-DE-KatjaNeural"),
        "es-US": ("Google", "es-US-Wavenet-A"),
        "uk-UA": ("Google", "uk-UA-Wavenet-A"),
        "es-MX": ("Azure", "es-MX-LarissaNeural"),
        "es-ES": ("Google", "es-ES-Wavenet-D"),
        "fr-FR": ("Azure", "fr-FR-YvetteNeural"),
    },
    "Grace": {
        "en-US": ("Google", "en-US-Wavenet-C"),
        "ru-RU": ("Google", "ru-RU-Wavenet-C"),
        "pt-PT": ("Google", "pt-PT-Wavenet-A"),
        "pt-BR": ("Google", "pt-BR-Wavenet-C"),
        "de-DE": ("Azure", "de-DE-TanjaNeural"),
        "es-US": ("Google", "es-US-Wavenet-A"),
        "uk-UA": ("Google", "uk-UA-Wavenet-A"),
        "es-MX": ("Azure", "es-MX-RenataNeural"),
        "es-ES": ("Google", "es-ES-Wavenet-C"),
        "fr-FR": ("Azure", "fr-FR-JacquelineNeural"),
    },
    "Alan": {
        "en-US": ("Google", "en-US-Wavenet-I"),
        "ru-RU": ("Google", "ru-RU-Wavenet-D"),
        "pt-PT": ("Google", "pt-PT-Wavenet-C"),
        "pt-BR": ("Google", "pt-BR-Wavenet-B"),
        "de-DE": ("Azure", "de-DE-ConradNeural"),
        "es-US": ("Google", "es-US-Wavenet-B"),
        "uk-UA": ("Azure", "uk-UA-OstapNeural"),
        "es-MX": ("Azure", "es-MX-GerardoNeural"),
        "es-ES": ("Google", "es-ES-Wavenet-B"),
        "fr-FR": ("Azure", "fr-FR-HenriNeural"),
    },
    "Alonzo": {
        "en-US": ("Google", "en-US-Wavenet-D"),
        "ru-RU": ("Google", "ru-RU-Wavenet-B"),
        "pt-PT": ("Google", "pt-PT-Wavenet-B"),
        "pt-BR": ("Google", "pt-BR-Wavenet-B"),
        "de-DE": ("Azure", "de-DE-KasperNeural"),
        "es-US": ("Google", "es-US-Wavenet-C"),
        "uk-UA": ("Azure", "uk-UA-OstapNeural"),
        "es-MX": ("Azure", "es-MX-CecilioNeural"),
        "es-ES": ("Google", "es-ES-Standard-B"),
        "fr-FR": ("Azure", "fr-FR-YvesNeural"),
    },
    "Bill": {
        "en-US": ("Azure", "en-US-ChristopherNeural"),
        "ru-RU": ("Azure", "ru-RU-DmitryNeural"),
        "pt-PT": ("Azure", "pt-PT-DuarteNeural"),
        "pt-BR": ("Azure", "pt-BR-JulioNeural"),
        "de-DE": ("Azure", "de-DE-ChristophNeural"),
        "es-US": ("Azure", "es-US-AlonsoNeural"),
        "uk-UA": ("Azure", "uk-UA-OstapNeural"),
        "es-MX": ("Azure", "es-MX-JorgeNeural"),
        "es-ES": ("Azure", "es-ES-AlvaroNeural"),
        "fr-FR": ("Azure", "fr-FR-ClaudeNeural"),
    },
    "Melinda": {
        "ru-RU": ("Azure", "ru-RU-DariyaNeural"),
        "en-US": ("Azure", "en-US-JennyNeural"),
        "pt-PT": ("Azure", "pt-PT-RaquelNeural"),
        "pt-BR": ("Azure", "pt-BR-FranciscaNeural"),
        "de-DE": ("Azure", "de-DE-ElkeNeural"),
        "es-US": ("Azure", "es-US-PalomaNeural"),
        "uk-UA": ("Azure", "uk-UA-PolinaNeural"),
        "es-MX": ("Azure", "es-MX-CarlotaNeural"),
        "es-ES": ("Azure", "es-ES-ElviraNeural"),
        "fr-FR": ("Azure", "fr-FR-DeniseNeural"),
    },
    "Greta": {
        "ru-RU": ("Azure", "ru-RU-SvetlanaNeural"),
        "en-US": ("Azure", "en-US-AnaNeural"),
        "pt-PT": ("Azure", "pt-PT-FernandaNeural"),
        "pt-BR": ("Azure", "pt-BR-GiovannaNeural"),
        "de-DE": ("Azure", "de-DE-GiselaNeural"),
        "es-US": ("Azure", "es-US-PalomaNeural"),
        "uk-UA": ("Azure", "uk-UA-PolinaNeural"),
        "es-MX": ("Azure", "es-MX-NuriaNeural"),
        "es-ES": ("Azure", "es-ES-ElviraNeural"),
        "fr-FR": ("Azure", "fr-FR-EloiseNeural"),
    },
}

GOOGLE_CLOUD_ENCODINGS = {
    "LINEAR16": speech_api.RecognitionConfig.AudioEncoding.LINEAR16,
    "WEBM_OPUS": speech_api.RecognitionConfig.AudioEncoding.WEBM_OPUS,
}

# Any speech break less than this value will be ignored.
MINIMUM_SPEECH_BREAK_MS = 50

# When synthesizing speech to match duration, this is the maximum delta.
SYNTHESIS_ERROR_MS = 200

SPEECH_RATE_MINIMUM = 0.7
SPEECH_RATE_MAXIMUM = 1.5

# Number of retries when iteratively adjusting speaking rate.
SYNTHESIS_RETRIES = 10

# Speech-to-text API call timeout.
# Upper limit is 480 minutes
# Details: https://cloud.google.com/speech-to-text/docs/async-recognize#speech_transcribe_async_gcs-python  # noqa: E501
GOOGLE_TRANSCRIBE_TIMEOUT_SEC = 480 * 60
AZURE_TRANSCRIBE_TIMEOUT_SEC = 60 * 60

SSML_EMOTIONS = {
    "😌": "calm",
    "🙂": "calm",
    "😢": "sad",
    "😞": "sad",
    "🤩": "excited",
    "😊": "excited",
    "😡": "angry",
    "😠": "angry",
}


@cache
def supported_google_voices() -> Dict[str, Sequence[str]]:
    client = google_tts.TextToSpeechClient()

    # Performs the list voices request
    response = client.list_voices()

    return {voice.name: voice.language_codes for voice in response.voices}


async def supported_azure_voices() -> Dict[str, Sequence[str]]:
    azure_key, azure_region = env.get_azure_config()
    headers = {
        "Ocp-Apim-Subscription-Key": azure_key,
    }
    url = f"https://{azure_region}.tts.speech.microsoft.com"
    async with aiohttp.ClientSession(url, headers=headers) as session:
        async with session.get("/cognitiveservices/voices/list") as response:
            if not response.ok:
                raise RuntimeError(await response.text())
            voices = await response.json()
    return {voice["ShortName"]: voice["Locale"] for voice in voices}


async def transcribe(
    file: Path,
    lang: Language,
    model: TranscriptionModel,
    provider: ServiceProvider,
) -> Sequence[Event]:
    """Transcribe audio.

    Args:
        uri: URI to the file. Supported: `gs://bucket/path`
        lang: speaker's language-region (i.e. en-US, pt-BR)
            as per https://www.rfc-editor.org/rfc/rfc5646
        model: transcription model (default: `"latest_long"`).
            https://cloud.google.com/speech-to-text/docs/transcription-model

    Notes:
        To save on probing and transcoding in a streaming environment,
        we are making hard assumptions on what input audio format is gonna be.

    Returns:
        Transcript containing timed phrases as `List[Event]`.
    """

    match provider:
        case "Google":
            return await _transcribe_google(file, lang, model)
        case "Deepgram":
            return await _transcribe_deepgram(file, lang, model)
        case "Azure":
            return await _transcribe_azure(file, lang, model)
        case never:
            assert_never(never)


async def _transcribe_deepgram(file: Path, lang: Language, model: TranscriptionModel):
    # For more info see language section of
    # https://developers.deepgram.com/api-reference/#transcription-prerecorded
    LANGUAGE_OVERRIDE = {
        "uk-UA": "uk",
        "ru-RU": "ru",
        "de-DE": "de",
    }
    deepgram_lang = LANGUAGE_OVERRIDE.get(lang, None) or lang

    if model in ("default", "latest_long"):
        model = "general"

    mime_type = "audio/wav"

    deepgram = Deepgram(env.get_deepgram_token())

    with open(file, "rb") as buffer:
        source = {"buffer": buffer, "mimetype": mime_type}
        response = await deepgram.transcription.prerecorded(
            source,
            {
                "punctuate": True,
                "language": deepgram_lang,
                "model": model,
                "profanity_filter": False,
                "diarize": True,
                "utterances": True,
                "utt_split": 1.4,
            },
        )

    events = []
    for utterance in response["results"]["utterances"]:
        character = CHARACTERS[int(utterance["speaker"]) % len(CHARACTERS)]
        assert is_character(character)

        event = Event(
            time_ms=round(float(utterance["start"]) * 1000),
            duration_ms=round(
                float(utterance["end"] - float(utterance["start"])) * 1000
            ),
            chunks=[utterance["transcript"]],
            voice=Voice(character=character),
        )
        events += [event]

    return events


async def _transcribe_google(
    file: Path, lang: Language, model: TranscriptionModel
) -> Sequence[Event]:
    client = speech_api.SpeechClient()
    uri = await obj.put(file, f"{env.get_storage_url()}/transcribe_google/{file.name}")
    try:

        def _api_call() -> LongRunningRecognizeResponse:
            operation = client.long_running_recognize(
                config=speech_api.RecognitionConfig(
                    # NOTE (astaff, 20220728): apparently Google Cloud doesn't
                    # need those and calculates everything on the fly.
                    # audio_channel_count=num_channels,
                    # encoding=GOOGLE_CLOUD_ENCODINGS[encoding],
                    # sample_rate_hertz=sample_rate_hz,
                    language_code=lang,
                    model=model,
                    enable_automatic_punctuation=True,
                    # TODO (astaff): are there any measurable gains
                    # from adjusting the hyper parameters?
                    # metadata=speech_api.RecognitionMetadata(
                    #     recording_device_type=speech_api.RecognitionMetadata.RecordingDeviceType.SMARTPHONE,  # noqa: E501
                    #     original_media_type=speech_api.RecognitionMetadata.OriginalMediaType.VIDEO,  # noqa: E501
                    # )
                ),
                audio=speech_api.RecognitionAudio(uri=uri),
            )
            result = operation.result(timeout=GOOGLE_TRANSCRIBE_TIMEOUT_SEC)  # type: ignore  # noqa: E501
            assert isinstance(
                result, LongRunningRecognizeResponse
            ), f"type(result)={type(result)}"

            return result

        response = await concurrency.run_in_thread_pool(_api_call)
    except google_api_exceptions.NotFound:
        raise ValueError(f"Requested entity not found {uri}")

    current_time_ms = 0
    events = []

    for result in response.results:
        end_time_ms = int(result.result_end_time.total_seconds() * 1000)
        event = Event(
            time_ms=current_time_ms,
            duration_ms=end_time_ms - current_time_ms,
            chunks=[result.alternatives[0].transcript],
        )
        current_time_ms = end_time_ms
        events += [event]
    return events


def transform_azure_result(
    phrase: RecognizedPhrase, lang: Language, model: TranscriptionModel
) -> list[Event]:
    """Transforms Azure's REST API record into list of Events
    Documentation: https://learn.microsoft.com/en-us/azure/cognitive-services/speech-service/batch-transcription-get?pivots=rest-api#transcription-result-file  # noqa: E501
    """
    time_ms = phrase.offsetInTicks // 10000
    duration_ms = phrase.durationInTicks // 10000
    text = phrase.nBest[0].display

    match model:
        case "default_granular":
            return [
                Event(
                    time_ms=time_ms,
                    chunks=[sentence],
                    duration_ms=duration_ms,
                    voice=Voice(character=CHARACTERS[phrase.speaker]),
                )
                for sentence, time_ms, duration_ms in break_phrase(
                    text=text,
                    words=[
                        (
                            word.word,
                            word.offsetInTicks // 10000,
                            word.durationInTicks // 10000,
                        )
                        for word in phrase.nBest[0].words
                    ],
                    lang=lang,
                )
            ]
        case "default":
            return [
                Event(
                    time_ms=time_ms,
                    chunks=[text],
                    duration_ms=duration_ms,
                    voice=Voice(character=CHARACTERS[phrase.speaker]),
                )
            ]
        case "latest_long" | "general":
            raise ValueError(f"Azure doesn't support model: '{model}'")
        case never:
            assert_never(never)


async def _transcribe_azure(file: Path, lang: Language, model: TranscriptionModel):
    uri = await obj.put(file, f"az://freespeech-files/{str(uuid4())}.{file.suffix}")

    key, region = env.get_azure_config()
    # more info: https://westus.dev.cognitive.microsoft.com/docs/services/speech-to-text-api-v3-0/operations/CreateTranscription  # noqa: E501
    headers = {
        "Content-Type": "application/json",
        "Ocp-Apim-Subscription-Key": key,
    }
    body = {
        "contentUrls": [uri],
        "properties": {
            "punctuationMode": "DictatedAndAutomatic",
            "profanityFilterMode": "None",  # "Masked"
            "wordLevelTimestampsEnabled": True,
            "diarizationEnabled": False,
        },
        "locale": lang,
        "displayName": f"Transcription using default model for {lang}",
    }

    async with aiohttp.ClientSession(
        f"https://{region}.api.cognitive.microsoft.com", headers=headers
    ) as session:
        # Submit transcription job
        async with session.post(
            "/speechtotext/v3.0/transcriptions", json=body
        ) as response:
            result = await response.json()
            if not response.ok:
                raise RuntimeError(result["message"])
            transcription_id = response.headers["location"].split("/")[-1]

        # Monitor job status and wait for Succeeded
        time_elapsed_sec = 0.0
        while time_elapsed_sec < AZURE_TRANSCRIBE_TIMEOUT_SEC:
            async with session.get(
                f"/speechtotext/v3.0/transcriptions/{transcription_id}"
            ) as response:
                result = await response.json()
                if not response.ok:
                    raise RuntimeError(result["message"])

                if result["status"] == "Succeeded":
                    break
                elif result["status"] == "Failed":
                    raise RuntimeError(f"Transcription job {transcription_id} failed!")

            time_elapsed_sec += 5.0
            await asyncio.sleep(5.0)

        # For successful job, retrieve the actual content URL
        async with session.get(
            f"/speechtotext/v3.0/transcriptions/{transcription_id}/files"
        ) as response:
            result = await response.json()
            if not response.ok:
                raise RuntimeError(result["message"])
            content_url = result["values"][0]["links"]["contentUrl"]

    async with aiohttp.ClientSession(headers=headers) as session:
        async with session.get(content_url) as response:
            result = await response.json()

    # Flatten the result
    return sum(
        [
            transform_azure_result(RecognizedPhrase(**phrase), lang, model)
            for phrase in result["recognizedPhrases"]
        ],
        [],
    )


def is_valid_ssml(text: str) -> bool:
    try:
        root = ET.fromstring(text)
    except ET.ParseError:
        return False

    return root.tag == "{http://www.w3.org/2001/10/synthesis}speak"


def _collect_and_remove_emojis(text: str, collection: list[str] | None) -> str:
    """Remove emojis from the given string while collecting
    fragments with encountered emojis to the given list.
    If the collection argument is None, the collection step will be skipped.
    """

    def _repl(m, acc):
        if acc:
            acc.append(m.group(0))

        if m.group(0).endswith("."):
            return "."
        else:
            return " "

    text = re.sub(
        rf"\s*[{''.join(SSML_EMOTIONS.keys())}]\s*\.*",
        lambda m: _repl(m, collection),
        text,
    )

    return text


def _emojis_to_ssml_emotion_tags(text: str, lang: Language) -> str:
    def _wrap_into_emotion_tag(text: str, emotion: str):
        return f'<mstts:express-as style="{emotion}">' + text + "</mstts:express-as>"

    pattern = rf"([{''.join(SSML_EMOTIONS.keys())}]\s*[.!?,;:]*)"
    split_by_emojis = re.split(pattern, text)

    text_with_emotion_tags = ""
    # Iterate over pairs: substring and it's subsequent emoji fragment
    for i in range(0, len(split_by_emojis) - 1, 2):
        # Emoji fragment is dirty - it contains
        # subsequent spaces and punctuation marks
        emoji_fagment_dirty = split_by_emojis[i + 1]
        substr = split_by_emojis[i].strip()

        if substr == "":
            continue

        # Retrieve a clean emoji and punctuation marks
        emoji = emoji_fagment_dirty[0]
        punctuation_tail = emoji_fagment_dirty[1:].strip()

        # Azure seems to be sensitive when it comes to emotion tags
        # and punctuation. It refuses to tone a sentence into any emotions,
        # if parts of the sentence are wrapped into their own emotion tags.
        # Azure only tones a sentence when it is wrapped into a single
        # emotion tag as a whole. The following part should handle cases
        # of inconvenient emoji positioning in a sentence relative
        # to surrounding punctuation.
        # TODO: improve this part - for now it's a crude fix.
        if not re.fullmatch(r"[.?!]+", punctuation_tail) and not substr.endswith(
            (".", "!", "?")
        ):
            punctuation_tail = "."

        _sentences = sentences(substr, lang)

        # An encountered emoji affects only the last
        # sentence of the preceding substring
        affected_substr = _sentences[-1]
        affected_substr = _wrap_into_emotion_tag(
            affected_substr + punctuation_tail, SSML_EMOTIONS[emoji]
        )

        # If the preceding substring contained other sentences,
        # wrap them into a default emotion
        if len(_sentences) > 1:
            unaffected_substr = " ".join(s.strip() for s in _sentences[:-1])
            unaffected_substr = _wrap_into_emotion_tag(
                unaffected_substr, "calm"  # emotion used as default
            )
            text_with_emotion_tags += unaffected_substr

        text_with_emotion_tags += affected_substr

    # Don't forget the last element of the
    # split array which is always non-emoji
    if split_by_emojis[-1].strip() != "":
        text_with_emotion_tags += _wrap_into_emotion_tag(
            split_by_emojis[-1].strip(), "calm"
        )

    return text_with_emotion_tags


def _wrap_in_ssml(
    text: str, voice: str, speech_rate: float, lang: Language = "en-US"
) -> str:
    def _google():
        decorated_text = "".join(
            [
                f"<s>{_collect_and_remove_emojis(sentence, collection=None)}</s>"
                for sentence in split_sentences(text)
            ]
        )

        result = (
            '<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" '
            'xml:lang="{LANG}">'
            '<voice name="{VOICE}"><prosody rate="{RATE:f}">{TEXT}</prosody></voice>'
            "</speak>".format(
                TEXT=decorated_text, VOICE=voice, RATE=speech_rate, LANG=lang
            )
        )
        assert is_valid_ssml(result), f"text={decorated_text} result={result}"
        return result

    def _azure():
        rate_percent = (speech_rate - 1.0) * 100.0
        if rate_percent >= 0:
            rate_str = f"+{rate_percent}%"
        else:
            rate_str = f"{rate_percent}%"

        result = (
            '<speak xmlns="http://www.w3.org/2001/10/synthesis" xmlns:mstts="http://www.w3.org/2001/mstts" xmlns:emo="http://www.w3.org/2009/10/emotionml" xml:lang="{LANG}" version="1.0">'  # noqa: E501
            '<voice name="{VOICE}"><prosody rate="{RATE}"><mstts:silence type="Sentenceboundary" value="100ms"/>{TEXT}</prosody></voice>'  # noqa: E501
            "</speak>".format(
                TEXT=_emojis_to_ssml_emotion_tags(text, lang),
                VOICE=voice,
                RATE=rate_str,
                LANG=lang,
            )
        )
        assert is_valid_ssml(result), f"text={text} result={result}"
        return result

    # TODO (astaff, 20220906): Refactor this and remove guessing
    # the provider from the name of their voice.
    if voice.endswith("Neural"):  # Assuming all azure voices end with Neural
        return _azure()
    else:
        return _google()


def text_to_chunks(
    text: str, chunk_length: int, voice: str, speech_rate: float
) -> Sequence[str]:
    inner = re.sub(r"#(\d+(\.\d+)?)#", r'<break time="\1s" />', text)
    overhead = len(_wrap_in_ssml("", voice=voice, speech_rate=speech_rate))
    sentence_overhead = len("<s></s>")
    return chunk(
        text=inner,
        max_chars=chunk_length - overhead,
        sentence_overhead=sentence_overhead,
    )


async def synthesize_text(
    text: str,
    duration_ms: int | None,
    voice: Voice,
    lang: Language,
    output_dir: Path | str,
) -> Tuple[Path, Voice]:

    character = voice.character
    if character not in VOICES:
        raise ValueError(
            f"Unsupported voice: {character}\n" f"Supported voices: {VOICES}"
        )

    if lang not in VOICES[character]:
        raise ValueError(f"Unsupported lang {lang} for {voice}\n")

    provider, provider_voice = VOICES[character][lang]
    match provider:
        case "Google":
            all_voices = supported_google_voices()
        case "Azure":
            all_voices = await supported_azure_voices()
        case "Deepgram":
            raise ValueError("Deepgram can not be used as TTS provider")
        case never:
            assert_never(never)

    chunks_with_breaks_expanded = text_to_chunks(
        text,
        chunk_length=MAX_CHUNK_LENGTH,
        voice=provider_voice,
        speech_rate=voice.speech_rate,
    )

    # eyeballing duration?

    if provider_voice not in all_voices or lang not in all_voices[provider_voice]:
        raise ValueError(
            (
                f"{provider} Speech Synthesis API "
                "doesn't support {lang} for voice {voice}\n"
                f"Supported values: {all_voices}"
            )
        )

    async def _synthesize_step(rate: float, retries: int | None) -> Tuple[Path, float]:
        if retries is not None and retries < 0:
            raise RuntimeError(
                (
                    "Unable to converge while adjusting speaking rate "
                    f"after {SYNTHESIS_RETRIES} attempts."
                    f"text={text} duration={duration_ms}"
                )
            )

        if duration_ms is not None:
            if rate < SPEECH_RATE_MINIMUM:
                logger.warning(f"Below SPEECH_RATE_MINIMUM: text={text} rate={rate}")
                return await _synthesize_step(SPEECH_RATE_MINIMUM, retries=None)

            if rate > SPEECH_RATE_MAXIMUM:
                logger.warning(f"Above SPEECH_RATE_MAXIMUM: text={text} rate={rate}")
                return await _synthesize_step(SPEECH_RATE_MAXIMUM, retries=None)

        def _google_api_call(ssml_phrase: str) -> bytes:
            client = google_tts.TextToSpeechClient()
            result = client.synthesize_speech(
                input=google_tts.SynthesisInput(ssml=ssml_phrase),
                voice=google_tts.VoiceSelectionParams(
                    language_code=lang,
                ),
                audio_config=google_tts.AudioConfig(
                    audio_encoding=google_tts.AudioEncoding.LINEAR16,
                    pitch=voice.pitch,
                ),
            )
            return result.audio_content

        async def _azure_api_call(ssml_phrase: str) -> bytes:
            azure_key, azure_region = env.get_azure_config()
            headers = {
                "X-Microsoft-OutputFormat": "riff-44100hz-16bit-mono-pcm",
                "Content-Type": "application/ssml+xml",
                "Ocp-Apim-Subscription-Key": azure_key,
            }
            url = f"https://{azure_region}.tts.speech.microsoft.com"
            async with aiohttp.ClientSession(url, headers=headers) as session:
                async with session.post(
                    "/cognitiveservices/v1", data=ssml_phrase
                ) as response:
                    if not response.ok:
                        raise RuntimeError(str(response))
                    return await response.read()

        match provider:
            case "Azure":
                responses = await asyncio.gather(
                    *[
                        _azure_api_call(
                            _wrap_in_ssml(chunk, voice=provider_voice, speech_rate=rate)
                        )
                        for chunk in chunks_with_breaks_expanded
                    ]
                )
            case "Google":
                responses = await asyncio.gather(
                    *[
                        concurrency.run_in_thread_pool(
                            _google_api_call,
                            _wrap_in_ssml(
                                phrase, voice=provider_voice, speech_rate=rate
                            ),
                        )
                        for phrase in chunks_with_breaks_expanded
                    ]
                )
            case "Deepgram":
                raise ValueError("Can not use Deepgram as a TTS provider")
            case never:
                assert_never(never)

        with TemporaryDirectory() as tmp_dir:
            files = [f"{media.new_file(tmp_dir)}.wav" for _ in responses]
            for file, response in zip(files, responses):
                with open(file, "wb") as fd:
                    fd.write(response)
            audio_file = await media.concat(files, output_dir)

        (audio, *_), _ = media.probe(audio_file)
        assert isinstance(audio, Audio)

        if (
            duration_ms is None
            or retries is None
            or abs(audio.duration_ms - duration_ms) < SYNTHESIS_ERROR_MS
        ):
            return Path(audio_file), rate
        else:
            logger.warning(
                f"retrying delta={audio.duration_ms - duration_ms} rate={rate}"
            )
            rate *= audio.duration_ms / duration_ms
            return await _synthesize_step(rate, retries - 1)

    output_file, speech_rate = await _synthesize_step(
        rate=voice.speech_rate, retries=SYNTHESIS_RETRIES
    )

    return output_file, Voice(
        speech_rate=speech_rate, character=voice.character, pitch=voice.pitch
    )


async def synthesize_events(
    events: Sequence[Event],
    lang: Language,
    output_dir: Path | str,
) -> Tuple[Path, Sequence[Voice], list[media.Span]]:
    output_dir = Path(output_dir)
    current_time_ms = 0
    clips = []
    voices = []
    spans = []

    for event in events:
        padding_ms = event.time_ms - current_time_ms
        spans += [("blank", current_time_ms, event.time_ms)]
        text = " ".join(event.chunks)
        clip, voice = await synthesize_text(
            text=text,
            duration_ms=event.duration_ms,
            voice=event.voice,
            lang=lang,
            output_dir=output_dir,
        )
        (audio, *_), _ = media.probe(clip)
        assert isinstance(audio, Audio)

        if padding_ms < 0:
            logger.warning(f"Negative padding ({padding_ms}) in front of: {text}")

        clips += [(padding_ms, clip)]
        current_time_ms = event.time_ms + audio.duration_ms
        spans += [("event", event.time_ms, current_time_ms)]

        voices += [voice]

    output_file = await media.concat_and_pad(clips, output_dir)

    return output_file, voices, spans


def concat_events(e1: Event, e2: Event, break_sentence: bool) -> Event:
    shift_ms = e2.time_ms - e1.time_ms

    if e1.duration_ms is None or e2.duration_ms is None:
        raise TypeError(
            f"""Tried to concatenate events, one of which is missing duration_ms.
            e1: {e1}
            e2: {e2}"""
        )

    gap_ms = shift_ms - e1.duration_ms

    first = " ".join(e1.chunks)
    second = " ".join(e2.chunks)

    if gap_ms >= MINIMUM_SPEECH_BREAK_MS:
        if break_sentence:
            first = capitalize_sentence(make_sentence(first))
            second = capitalize_sentence(second)
        chunk = f"{first} #{gap_ms / 1000.0:.2f}# {second}"
    else:
        chunk = f"{first} {second}"

    return Event(
        time_ms=e1.time_ms,
        duration_ms=shift_ms + e2.duration_ms,
        chunks=[chunk],
        voice=e2.voice,
    )


def normalize_speech(
    events: Sequence[Event], gap_ms: int, length: int, method: Normalization
) -> Sequence[Event]:
    """Transforms speech events into a fewer and longer ones
    representing continuous speech."""

    REMOVE_SYMBOLS = "\n"

    scrubbed_events = [
        replace(e, chunks=[remove_symbols(" ".join(e.chunks), REMOVE_SYMBOLS)])
        for e in events
    ]

    first_event, *events = scrubbed_events
    acc = [first_event]

    for event in events:
        last_event = acc.pop()
        last_text = (" ".join(last_event.chunks)).strip()

        if last_event.duration_ms is None or event.duration_ms is None:
            acc += [last_event, event]
            continue

        gap = event.time_ms - last_event.time_ms - last_event.duration_ms

        if gap > gap_ms:
            acc += [last_event, event]
        elif len(last_text) > length and is_sentence(last_text):
            acc += [last_event, event]
        elif last_event.voice != event.voice:
            acc += [last_event, event]
        else:
            match method:
                case "break_ends_sentence":
                    acc += [concat_events(last_event, event, break_sentence=True)]
                case "extract_breaks_from_sentence":
                    raise NotImplementedError()
                case never:
                    assert_never(never)

    return acc


def break_phrase(
    text: str,
    words: Sequence[Tuple[str, int, int]],
    lang: Language,
) -> Sequence[Tuple[str, int, int]]:
    """Breaks down a single phrase into separate sentences with start time and duration.
    Args:
        text: Paragraph of text with one or more sentences.
        words: Sequence of tuples representing a single word from the phrase,
            its start time and duration.
        lang: Language code for language-aware sentence parsing.
    Returns:
        Sequence of tuples representing a sentence, its start time and duration.
    """
    # reduce each word in text and words down to lemmas to avoid
    # mismatches due to effects of ASR's language model.
    _sentences = sentences(text, lang)
    display_tokens = [
        (lemma.lower(), num)
        for num, sentence in enumerate(_sentences)
        for lemma in lemmas(sentence, lang)
    ]
    lexical_tokens = [
        (lemma.lower(), start, duration)
        for word, start, duration in words
        for lemma in lemmas(word, lang)
    ]

    # Find the longest common sequences between lemmas in text
    # and lemmatized words.
    matcher = difflib.SequenceMatcher(
        a=[token for token, *_ in display_tokens],
        b=[token for token, *_ in lexical_tokens],
        autojunk=False,
    )
    matches = [
        (num, (int(start), int(duration)))
        for i, j, n in matcher.get_matching_blocks()
        for (_, num), (_, start, duration) in zip(
            display_tokens[i : i + n], lexical_tokens[j : j + n]
        )
    ]

    # Group matches by sentence number. The first and the last item
    # in the group will represent the first and last overlaps with the timed words.
    sentence_timings = {
        num: (start := timings[0][0], timings[-1][0] + timings[-1][1] - start)
        for num, timings in [
            (num, [(start, duration) for _, (start, duration) in timings])
            for num, timings in groupby(matches, key=lambda a: a[0])
        ]
    }

    # Return sentences and their timings.
    return [
        (sentence, *sentence_timings[num]) for num, sentence in enumerate(_sentences)
    ]
