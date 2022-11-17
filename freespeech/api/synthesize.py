from tempfile import TemporaryDirectory

from fastapi import APIRouter

from freespeech import env
from freespeech.lib import media, speech
from freespeech.lib.storage import obj
from freespeech.types import Transcript

from . import transcript

router = APIRouter()


@router.post("/synthesize")
async def synthesize(source: Transcript | str) -> str:
    if isinstance(source, str):
        source = await transcript.load(source)

    with TemporaryDirectory() as tmp_dir:
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

    return video_url or audio_url
