from tempfile import TemporaryDirectory

from fastapi import APIRouter

from freespeech import env
from freespeech.lib import media, speech, tts
from freespeech.lib.storage import obj
from freespeech.types import Transcript

from . import transcript

router = APIRouter()


SENTENCE_PAUSE_MS = 50
MIN_RATE = 0.8
MIN_SILENCE_SCALE = 0.8
VARIANCE_THRESHOLD = 0.1


@router.post("/dub")
async def dub(source: Transcript | str, is_smooth: bool) -> str:
    if isinstance(source, str):
        source = await transcript.load(source)

    with TemporaryDirectory() as tmp_dir:
        synth_file, spans = await _synthesize(source, is_smooth, tmp_dir)

        audio_url = await obj.put(
            synth_file, f"{env.get_storage_url()}/media/{synth_file.name}"
        )

        video_url = None
        if source.video:
            video_file = await obj.get(obj.storage_url(source.video), dst_dir=tmp_dir)

            if source.settings.space_between_events == "Crop":
                video_file = str(
                    await media.keep_events(
                        file=video_file, spans=spans, output_dir=tmp_dir, mode="both"
                    )
                )

            dub_file = await media.dub(
                video=video_file, audio=synth_file, output_dir=tmp_dir
            )

            video_url = await obj.put(
                dub_file, f"{env.get_storage_url()}/media/{dub_file.name}"
            )

    gs_url = video_url or audio_url
    return obj.public_url(gs_url)


async def _synthesize(source, is_smooth: bool, tmp_dir):
    spans: list[media.Span] = []
    if is_smooth:
        synth_file = await tts.synthesize(
            list(source.events),
            lang=source.lang,
            output_dir=tmp_dir,
        )
        first = source.events[0]
        last = source.events[-1]
        spans = [("event", first.time_ms, last.time_ms + last.duration_ms)]
    else:
        synth_file, _, spans = await speech.synthesize_events(
            events=source.events,
            lang=source.lang,
            output_dir=tmp_dir,
        )

    if source.audio:
        audio_file = await obj.get(obj.storage_url(source.audio), dst_dir=tmp_dir)
        mono_audio = await media.multi_channel_audio_to_mono(
            audio_file, output_dir=tmp_dir
        )

        match source.settings.space_between_events:
            case "Fill" | "Crop":
                # has side effects :(
                synth_file = await media.mix(
                    files=(mono_audio, synth_file),
                    weights=(source.settings.original_audio_level, 10),
                    output_dir=tmp_dir,
                )
                if source.settings.space_between_events == "Crop":
                    synth_file = await media.keep_events(
                        file=synth_file,
                        spans=spans,
                        output_dir=tmp_dir,
                        mode="audio",
                    )
            case "Blank":
                synth_stream = media.mix_spans(
                    original=mono_audio,
                    synth_file=synth_file,
                    spans=spans,
                    weights=(source.settings.original_audio_level, 10),
                )
                synth_file = await media.write_streams(
                    streams=[synth_stream], output_dir=tmp_dir, extension="wav"
                )
                # writes only here ^

    return synth_file, spans
