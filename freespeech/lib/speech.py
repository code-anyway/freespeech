import asyncio
import difflib
import json
import logging
import os
import re
import shutil
import xml.etree.ElementTree as ET
from dataclasses import replace
from functools import cache, reduce
from itertools import groupby
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Dict, Sequence, Tuple
from uuid import uuid4

import aiofiles
import aiohttp
import pydub
from deepgram import Deepgram
from google.api_core import exceptions as google_api_exceptions
from google.cloud import speech as speech_api
from google.cloud import texttospeech as google_tts
from google.cloud.speech_v1.types.cloud_speech import LongRunningRecognizeResponse
from pydantic.dataclasses import dataclass

import freespeech.lib.hash as hash
from freespeech import env
from freespeech.lib import concurrency, elevenlabs, media
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
VOICES: Dict[Character, Dict[Language, Tuple[ServiceProvider, str] | None]] = {
    "Ada": {
        "en-US": ("Azure", "en-US-AriaNeural"),
        "ru-RU": ("Google", "ru-RU-Wavenet-E"),
        "pt-PT": ("Google", "pt-PT-Wavenet-D"),
        "pt-BR": ("Azure", "pt-BR-YaraNeural"),
        "de-DE": ("Azure", "de-DE-KatjaNeural"),
        "es-US": ("Google", "es-US-Wavenet-A"),
        "uk-UA": ("Google", "uk-UA-Wavenet-A"),
        "es-MX": ("Azure", "es-MX-LarissaNeural"),
        "es-ES": ("Google", "es-ES-Wavenet-D"),
        "fr-FR": ("Azure", "fr-FR-YvetteNeural"),
        "sv-SE": ("Azure", "sv-SE-SofieNeural"),
        "tr-TR": ("Azure", "tr-TR-EmelNeural"),
        "it-IT": ("Azure", "it-IT-FabiolaNeural"),
        "ar-SA": ("Azure", "ar-SA-ZariyahNeural"),
        "et-EE": ("Azure", "et-EE-AnuNeural"),
        "fi-FI": ("Azure", "fi-FI-SelmaNeural"),
        "ja-JP": ("Azure", "ja-JP-NanamiNeural"),
        "zh-CN": ("Azure", "zh-CN-XiaohanNeural"),
        "pl-PL": ("Azure", "pl-PL-ZofiaNeural"),
    },
    "Grace": {
        "en-US": ("Azure", "en-US-JaneNeural"),
        "ru-RU": ("Google", "ru-RU-Wavenet-C"),
        "pt-PT": ("Google", "pt-PT-Wavenet-A"),
        "pt-BR": ("Azure", "pt-BR-ManuelaNeural"),
        "de-DE": ("Azure", "de-DE-TanjaNeural"),
        "es-US": ("Google", "es-US-Wavenet-A"),
        "uk-UA": ("Google", "uk-UA-Wavenet-A"),
        "es-MX": ("Azure", "es-MX-RenataNeural"),
        "es-ES": ("Google", "es-ES-Wavenet-C"),
        "fr-FR": ("Azure", "fr-FR-JacquelineNeural"),
        "sv-SE": ("Azure", "sv-SE-SofieNeural"),
        "tr-TR": ("Azure", "tr-TR-EmelNeural"),
        "it-IT": ("Azure", "it-IT-PalmiraNeural"),
        "ar-SA": ("Azure", "ar-SA-ZariyahNeural"),
        "et-EE": ("Azure", "et-EE-AnuNeural"),
        "fi-FI": ("Azure", "fi-FI-NooraNeural"),
        "ja-JP": ("Azure", "ja-JP-MayuNeural"),
        "zh-CN": ("Azure", "zh-CN-XiaomoNeural"),
        "pl-PL": ("Azure", "pl-PL-AgnieszkaNeural"),
    },
    "Alan": {
        "en-US": ("Azure", "en-US-GuyNeural"),
        "ru-RU": ("Google", "ru-RU-Wavenet-D"),
        "pt-PT": ("Google", "pt-PT-Wavenet-C"),
        "pt-BR": ("Azure", "pt-BR-NicolauNeural"),
        "de-DE": ("Azure", "de-DE-ConradNeural"),
        "es-US": ("Google", "es-US-Wavenet-B"),
        "uk-UA": ("Azure", "uk-UA-OstapNeural"),
        "es-MX": ("Azure", "es-MX-GerardoNeural"),
        "es-ES": ("Google", "es-ES-Wavenet-B"),
        "fr-FR": ("Azure", "fr-FR-HenriNeural"),
        "sv-SE": ("Azure", "sv-SE-MattiasNeural"),
        "tr-TR": ("Azure", "tr-TR-AhmetNeural"),
        "it-IT": ("Azure", "it-IT-DiegoNeural"),
        "ar-SA": ("Azure", "ar-SA-HamedNeural"),
        "et-EE": ("Azure", "et-EE-KertNeural"),
        "fi-FI": ("Azure", "fi-FI-HarriNeural"),
        "ja-JP": ("Azure", "ja-JP-DaichiNeural"),
        "zh-CN": ("Azure", "zh-CN-YunxiNeural"),
        "pl-PL": ("Azure", "pl-PL-MarekNeural"),
    },
    "Alonzo": {
        "en-US": ("Azure", "en-US-EricNeural"),
        "ru-RU": ("Google", "ru-RU-Wavenet-B"),
        "pt-PT": ("Google", "pt-PT-Wavenet-B"),
        "pt-BR": ("Azure", "pt-BR-DonatoNeural"),
        "de-DE": ("Azure", "de-DE-KasperNeural"),
        "es-US": ("Google", "es-US-Wavenet-C"),
        "uk-UA": ("Azure", "uk-UA-OstapNeural"),
        "es-MX": ("Azure", "es-MX-CecilioNeural"),
        "es-ES": ("Google", "es-ES-Standard-B"),
        "fr-FR": ("Azure", "fr-FR-YvesNeural"),
        "sv-SE": ("Azure", "sv-SE-MattiasNeural"),
        "tr-TR": ("Azure", "tr-TR-AhmetNeural"),
        "it-IT": ("Azure", "it-IT-RinaldoNeural"),
        "ar-SA": ("Azure", "ar-SA-HamedNeural"),
        "et-EE": ("Azure", "et-EE-KertNeural"),
        "fi-FI": ("Azure", "fi-FI-HarriNeural"),
        "ja-JP": ("Azure", "ja-JP-KeitaNeural"),
        "zh-CN": ("Azure", "zh-CN-YunyeNeural"),
        "pl-PL": ("Azure", "pl-PL-MarekNeural"),
    },
    "Bill": {
        "en-US": ("Azure", "en-US-DavisNeural"),
        "ru-RU": ("Azure", "ru-RU-DmitryNeural"),
        "pt-PT": ("Azure", "pt-PT-DuarteNeural"),
        "pt-BR": ("Azure", "pt-BR-JulioNeural"),
        "de-DE": ("Azure", "de-DE-ChristophNeural"),
        "es-US": ("Azure", "es-US-AlonsoNeural"),
        "uk-UA": ("Azure", "uk-UA-OstapNeural"),
        "es-MX": ("Azure", "es-MX-JorgeNeural"),
        "es-ES": ("Azure", "es-ES-AlvaroNeural"),
        "fr-FR": ("Azure", "fr-FR-ClaudeNeural"),
        "sv-SE": ("Azure", "sv-SE-MattiasNeural"),
        "tr-TR": ("Azure", "tr-TR-AhmetNeural"),
        "it-IT": ("Azure", "it-IT-LisandroNeural"),
        "ar-SA": ("Azure", "ar-SA-HamedNeural"),
        "et-EE": ("Azure", "et-EE-KertNeural"),
        "fi-FI": ("Azure", "fi-FI-HarriNeural"),
        "ja-JP": ("Azure", "ja-JP-NaokiNeural"),
        "zh-CN": ("Azure", "zh-CN-YunzeNeural"),
        "pl-PL": ("Azure", "pl-PL-MarekNeural"),
    },
    "Barbara": {
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
        "sv-SE": ("Azure", "sv-SE-HilleviNeural"),
        "tr-TR": ("Azure", "tr-TR-EmelNeural"),
        "it-IT": ("Azure", "it-IT-ElsaNeural"),
        "ar-SA": ("Azure", "ar-SA-ZariyahNeural"),
        "et-EE": ("Azure", "et-EE-AnuNeural"),
        "fi-FI": ("Azure", "fi-FI-NooraNeural"),
        "ja-JP": ("Azure", "ja-JP-ShioriNeural"),
        "zh-CN": ("Azure", "zh-CN-XiaoxiaoNeural"),
        "pl-PL": ("Azure", "pl-PL-ZofiaNeural"),
    },
    "Greta": {
        "ru-RU": ("Azure", "ru-RU-SvetlanaNeural"),
        "en-US": ("Azure", "en-US-AnaNeural"),
        "pt-PT": ("Azure", "pt-PT-FernandaNeural"),
        "pt-BR": ("Azure", "pt-BR-LeticiaNeural"),
        "de-DE": ("Azure", "de-DE-GiselaNeural"),
        "es-US": ("Azure", "es-US-PalomaNeural"),
        "uk-UA": ("Azure", "uk-UA-PolinaNeural"),
        "es-MX": ("Azure", "es-MX-NuriaNeural"),
        "es-ES": ("Azure", "es-ES-ElviraNeural"),
        "fr-FR": ("Azure", "fr-FR-EloiseNeural"),
        "sv-SE": ("Azure", "sv-SE-HilleviNeural"),
        "tr-TR": ("Azure", "tr-TR-EmelNeural"),
        "it-IT": ("Azure", "it-IT-PierinaNeural"),
        "ar-SA": ("Azure", "ar-SA-ZariyahNeural"),
        "et-EE": ("Azure", "et-EE-KertNeural"),
        "fi-FI": ("Azure", "fi-FI-SelmaNeural"),
        "ja-JP": ("Azure", "ja-JP-AoiNeural"),
        "zh-CN": ("Azure", "zh-CN-XiaoshuangNeural"),
        "pl-PL": ("Azure", "pl-PL-MarekNeural"),
    },
    "Volodymyr": {
        "en-US": ("ElevenLabs", "Volodymyr"),
        "ru-RU": None,
        "pt-PT": ("ElevenLabs", "Volodymyr"),
        "pt-BR": ("ElevenLabs", "Volodymyr"),
        "de-DE": ("ElevenLabs", "Volodymyr"),
        "es-US": ("ElevenLabs", "Volodymyr"),
        "uk-UA": None,
        "es-MX": ("ElevenLabs", "Volodymyr"),
        "es-ES": ("ElevenLabs", "Volodymyr"),
        "fr-FR": ("ElevenLabs", "Volodymyr"),
        "sv-SE": None,
        "tr-TR": None,
        "it-IT": ("ElevenLabs", "Volodymyr"),
        "ar-SA": None,
        "et-EE": None,
        "fi-FI": None,
        "ja-JP": None,
        "zh-CN": None,
        "pl-PL": ("ElevenLabs", "Volodymyr"),
    },
    "Artyom": {
        "en-US": ("ElevenLabs", "Artyom"),
        "ru-RU": None,
        "pt-PT": ("ElevenLabs", "Artyom"),
        "pt-BR": ("ElevenLabs", "Artyom"),
        "de-DE": ("ElevenLabs", "Artyom"),
        "es-US": ("ElevenLabs", "Artyom"),
        "uk-UA": None,
        "es-MX": ("ElevenLabs", "Artyom"),
        "es-ES": ("ElevenLabs", "Artyom"),
        "fr-FR": ("ElevenLabs", "Artyom"),
        "sv-SE": None,
        "tr-TR": None,
        "it-IT": ("ElevenLabs", "Artyom"),
        "ar-SA": None,
        "et-EE": None,
        "fi-FI": None,
        "ja-JP": None,
        "zh-CN": None,
        "pl-PL": ("ElevenLabs", "Artyom"),
    },
    "Sophie": {
        "en-US": ("ElevenLabs", "Bella"),
        "ru-RU": None,
        "pt-PT": ("ElevenLabs", "Bella"),
        "pt-BR": ("ElevenLabs", "Bella"),
        "de-DE": ("ElevenLabs", "Bella"),
        "es-US": ("ElevenLabs", "Bella"),
        "uk-UA": None,
        "es-MX": ("ElevenLabs", "Bella"),
        "es-ES": ("ElevenLabs", "Bella"),
        "fr-FR": ("ElevenLabs", "Bella"),
        "sv-SE": None,
        "tr-TR": None,
        "it-IT": ("ElevenLabs", "Bella"),
        "ar-SA": None,
        "et-EE": None,
        "fi-FI": None,
        "ja-JP": None,
        "zh-CN": None,
        "pl-PL": ("ElevenLabs", "Bella"),
    },
    "Margaret": {
        "en-US": ("ElevenLabs", "Elli"),
        "ru-RU": None,
        "pt-PT": ("ElevenLabs", "Elli"),
        "pt-BR": ("ElevenLabs", "Elli"),
        "de-DE": ("ElevenLabs", "Elli"),
        "es-US": ("ElevenLabs", "Elli"),
        "uk-UA": None,
        "es-MX": ("ElevenLabs", "Elli"),
        "es-ES": ("ElevenLabs", "Elli"),
        "fr-FR": ("ElevenLabs", "Elli"),
        "sv-SE": None,
        "tr-TR": None,
        "it-IT": ("ElevenLabs", "Elli"),
        "ar-SA": None,
        "et-EE": None,
        "fi-FI": None,
        "ja-JP": None,
        "zh-CN": None,
        "pl-PL": ("ElevenLabs", "Elli"),
    },
    "John": {
        "en-US": ("ElevenLabs", "Antoni"),
        "ru-RU": None,
        "pt-PT": ("ElevenLabs", "Antoni"),
        "pt-BR": ("ElevenLabs", "Antoni"),
        "de-DE": ("ElevenLabs", "Antoni"),
        "es-US": ("ElevenLabs", "Antoni"),
        "uk-UA": None,
        "es-MX": ("ElevenLabs", "Antoni"),
        "es-ES": ("ElevenLabs", "Antoni"),
        "fr-FR": ("ElevenLabs", "Antoni"),
        "sv-SE": None,
        "tr-TR": None,
        "it-IT": ("ElevenLabs", "Antoni"),
        "ar-SA": None,
        "et-EE": None,
        "fi-FI": None,
        "ja-JP": None,
        "zh-CN": None,
        "pl-PL": ("ElevenLabs", "Antoni"),
    },
    "Tim": {
        "en-US": ("ElevenLabs", "Josh"),
        "ru-RU": None,
        "pt-PT": ("ElevenLabs", "Josh"),
        "pt-BR": ("ElevenLabs", "Josh"),
        "de-DE": ("ElevenLabs", "Josh"),
        "es-US": ("ElevenLabs", "Josh"),
        "uk-UA": None,
        "es-MX": ("ElevenLabs", "Josh"),
        "es-ES": ("ElevenLabs", "Josh"),
        "fr-FR": ("ElevenLabs", "Josh"),
        "sv-SE": None,
        "tr-TR": None,
        "it-IT": ("ElevenLabs", "Josh"),
        "ar-SA": None,
        "et-EE": None,
        "fi-FI": None,
        "ja-JP": None,
        "zh-CN": None,
        "pl-PL": ("ElevenLabs", "Josh"),
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

# Number of retries when making a request to speech API.
API_RETRIES = 3

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

CACHE_SIZE = 0


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
        case "ElevenLabs":
            raise NotImplementedError("Can't transcribe with ElevenLabs")
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
        case "latest_long" | "general" | "whisper-large":
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
            if "duration" in phrase  # filter out empty phrases
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


async def _synthesize_text(
    text: str,
    duration_ms: int | None,
    voice: Voice,
    lang: Language,
    output_dir: Path | str,
    cache_dir: str = os.path.join(os.path.dirname(__file__), "../../.cache/freespeech"),
) -> Tuple[Path, Voice]:
    character = voice.character
    if character not in VOICES:
        raise ValueError(
            f"Unsupported voice: {character}\n" f"Supported voices: {VOICES}"
        )

    if lang not in VOICES[character]:
        raise ValueError(f"Unsupported lang {lang} for {voice}\n")

    provider_and_voice = VOICES[character][lang]

    if not provider_and_voice:
        raise ValueError(f"No provider for {voice} in {lang}")

    provider, provider_voice = provider_and_voice
    match provider:
        case "Google":
            all_voices = supported_google_voices()
        case "Azure":
            all_voices = await supported_azure_voices()
        case "ElevenLabs":
            speech = await elevenlabs.synthesize(
                text, voice.character, voice.speech_rate, Path(output_dir)
            )
            return speech, voice
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

    synthesized_hash = hash.obj((text, duration_ms, voice, lang))
    synthesized_path = f"{cache_dir}/{synthesized_hash}.wav"
    voice_path = f"{cache_dir}/{synthesized_hash}-voice.json"

    if not os.path.exists(cache_dir):
        os.makedirs(cache_dir)

    if os.path.exists(voice_path) and os.path.exists(synthesized_path):
        async with aiofiles.open(voice_path, "r") as cached_voice:
            voice = Voice(**json.loads(await cached_voice.read()))
        return Path(synthesized_path), voice

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
            case "ElevenLabs":
                raise ValueError("Can do adaptive rate synthesis with ElevenLabs")
            case "Deepgram":
                raise ValueError("Can not use Deepgram as a TTS provider")
            case never:
                assert_never(never)

        def is_valid_file(file: str) -> bool:
            try:
                media.probe(file)
                return True
            except Exception:
                return False

        with TemporaryDirectory() as tmp_dir:
            files = [f"{media.new_file(tmp_dir)}.wav" for _ in responses]
            for file, response in zip(files, responses):
                with open(file, "wb") as fd:
                    fd.write(response)

            # filter out invalid files (e.g. empty files)
            files = [file for file in files if is_valid_file(file)]

            if files:
                audio_file = await media.concat(files, output_dir)
            else:
                # fallback to a silent audio file
                audio_file = Path(f"{media.new_file(output_dir)}.wav")
                fd = pydub.AudioSegment.silent(duration=1, frame_rate=44100).export(
                    audio_file, format="wav"
                )
                fd.close()  # type: ignore

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

    shutil.copyfile(output_file, synthesized_path)
    async with aiofiles.open(voice_path, "w") as voice_cache:
        await voice_cache.write(
            json.dumps(
                {
                    "speech_rate": speech_rate,
                    "character": voice.character,
                    "pitch": voice.pitch,
                }
            )
        )

    await obj.rotate_cache(cache_dir)

    return output_file, Voice(
        speech_rate=speech_rate, character=voice.character, pitch=voice.pitch
    )


async def synthesize_text(
    text: str,
    duration_ms: int | None,
    voice: Voice,
    lang: Language,
    output_dir: Path | str,
    cache_dir: str = os.path.join(os.path.dirname(__file__), "../../.cache/freespeech"),
) -> Tuple[Path, Voice]:
    for retry in range(API_RETRIES):
        try:
            return await _synthesize_text(
                text, duration_ms, voice, lang, output_dir, cache_dir
            )
        except (
            ConnectionAbortedError,
            aiohttp.ServerDisconnectedError,
            aiohttp.ClientOSError,
            asyncio.TimeoutError,
        ):
            sleep_time = 2**retry * 2.0
            logger.warning(
                f"Connection error, retrying in {sleep_time} seconds ({retry}/{API_RETRIES})"  # noqa: E501
            )
            await asyncio.sleep(sleep_time)
    raise RuntimeError(f"Unable to connect to TTS API after {API_RETRIES} retries")


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


def fix_sentence_boundaries(
    sentences: list[tuple[str, tuple[int, int] | None]],
    phrase_start_ms: int,
    phrase_finish_ms: int,
) -> list[tuple[str, tuple[int, int]]]:
    def _reducer(
        acc: list[tuple[str, tuple[int, int | None]]],
        next_sentence: tuple[str, tuple[int, int] | None],
    ) -> list[tuple[str, tuple[int, int | None]]]:
        sentence, span = next_sentence
        if span is None:
            if len(acc) == 0:
                return [(sentence, (phrase_start_ms, None))]
            else:
                prev_sentence, (prev_start, prev_finish) = acc[-1]
                return acc[:-1] + [(prev_sentence + " " + sentence, (prev_start, None))]
        else:
            if len(acc) == 0:
                return [(sentence, span)]
            else:
                prev_sentence, (prev_start, prev_finish) = acc[-1]
                if prev_finish is None:
                    return acc[:-1] + [
                        (prev_sentence + " " + sentence, (prev_start, span[1]))
                    ]
                else:
                    return acc + [(sentence, span)]

    fixed_sentences: list[tuple[str, tuple[int, int | None]]] = reduce(
        _reducer, sentences, []
    )

    if len(fixed_sentences) > 0:
        last_sentence, (last_start, last_finish) = fixed_sentences.pop()
        if last_finish is None:
            fixed_sentences += [(last_sentence, (last_start, phrase_finish_ms))]
        else:
            fixed_sentences += [(last_sentence, (last_start, last_finish))]

    for _, (_, finish_ms) in fixed_sentences:
        assert finish_ms is not None, "finish_ms is None"

    return [
        (s, (start_ms, finish_ms))
        for s, (start_ms, finish_ms) in fixed_sentences
        if finish_ms is not None
    ]


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
    if not words:
        return []

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
        (num, (int(start), int(start) + int(duration)))
        for i, j, n in matcher.get_matching_blocks()
        for (_, num), (_, start, duration) in zip(
            display_tokens[i : i + n], lexical_tokens[j : j + n]
        )
    ]

    # Group matches by sentence number. The first and the last item
    # in the group will represent the first and last overlaps with the timed words.
    sentence_timings = {
        num: (start := timings[0][0], timings[-1][1] - start)
        for num, timings in [
            (num, [(start, finish) for _, (start, finish) in timings])
            for num, timings in groupby(matches, key=lambda a: a[0])
        ]
    }

    # If timing information is missing for a sentence, use None
    res = [
        (sentence, sentence_timings.get(num, None))
        for num, sentence in enumerate(_sentences)
    ]

    phrase_start_ms = lexical_tokens[0][1]
    phrase_end_ms = lexical_tokens[-1][1] + lexical_tokens[-1][2]

    return [
        (sentence, *timing)
        for sentence, timing in fix_sentence_boundaries(
            res, phrase_start_ms, phrase_end_ms
        )
    ]


def restore_full_sentences(events: list[Event]) -> list[Event]:
    """Join events to ensure no sentences are split across events."""
    res: list[Event] = []
    for event in events:
        if not res:
            res.append(event)
            continue

        prev_event = res.pop()
        prev_event_text = " ".join(prev_event.chunks).strip()
        event_text = " ".join(event.chunks).strip()
        if any(prev_event_text.endswith(p) for p in (".", "!", "?")):
            res.append(prev_event)
            res.append(event)
        else:
            assert prev_event.duration_ms is not None
            res.append(
                replace(
                    prev_event,
                    chunks=[prev_event_text + " " + event_text],
                    duration_ms=prev_event.duration_ms + event.duration_ms
                    if event.duration_ms is not None
                    else None,
                )
            )
    return res
