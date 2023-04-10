import logging
from pathlib import Path

import aiohttp

from freespeech import env
from freespeech.lib import audio, hash, media

ROOT_URL = "https://api.elevenlabs.io"


logger = logging.getLogger(__name__)


async def change_speech_rate(speech_file: Path, rate: float) -> Path:
    """Change speech rate."""
    logger.info(f"Changing speech rate to {rate}")
    wav = await media.multi_channel_audio_to_mono(
        speech_file, output_dir=speech_file.parent, sample_rate=22_050
    )
    duration = audio.duration(wav)
    new_duration = round(duration / rate)
    return Path(audio.resample(str(wav), new_duration, str(wav.parent)))


async def synthesize(text: str, voice: str, rate: float, output: Path) -> Path:
    """Synthesize speech from text input."""
    api_key = env.get_elevenlabs_key()

    voices = await get_voices()
    if voice not in voices:
        raise ValueError(f"Voice {voice} not available.")
    voice_id = voices[voice]

    output_file = output / Path(f'{hash.string(f"{voice_id} {text}")}.mp3')
    if not output_file.exists():
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{ROOT_URL}/v1/text-to-speech/{voice_id}",
                headers={"xi-api-key": api_key},
                json={"language_id": "en-us", "model_id": "prod", "text": text},
            ) as response:
                if response.status != 200:
                    raise RuntimeError(
                        f"Error synthesizing speech: {response.status} {response.reason}"  # noqa: E501
                    )

                # write response into file
                with open(output_file, "wb") as f:
                    while True:
                        chunk = await response.content.read(1024)
                        if not chunk:
                            break
                        f.write(chunk)

    return await change_speech_rate(output_file, rate)


async def get_voices() -> dict[str, str]:
    """Get a list of voices available for synthesis."""
    api_key = env.get_elevenlabs_key()

    async with aiohttp.ClientSession() as session:
        async with session.get(
            f"{ROOT_URL}/v1/voices", headers={"xi-api-key": api_key}
        ) as response:
            if response.status != 200:
                raise RuntimeError(
                    f"Error getting voices: {response.status} {response.reason}"
                )

            data = await response.json()
            return {d["name"]: d["voice_id"] for d in data["voices"]}
