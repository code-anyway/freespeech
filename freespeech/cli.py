import click
import freespeech.ops as ops

@click.group()
@click.version_option()
def cli():
    "null"


@cli.command(name="voiceover")
@click.argument('files', nargs=-1, type=click.Path())
@click.option("-o", "--output", required=True, help="File name for the resulting video")
@click.option("-v", "--video", required=True, help="Path to the video stream")
@click.option("-w", "--weights", required=True, help="Weights for each audio stream")
def add_audio(files, output, video, weights):
    click.echo(
        ops.add_audio(
            video_path=video,
            audio_paths=files,
            output_path=output,
            weights=[int(w.strip()) for w in weights.split(",")]
        )
    )


@cli.command(name="ingest")
@click.option("-u", "--url", required=True, help="URL containing original stream")
@click.option("-o", "--output_dir", required=True, help="Directory to store output files.", type=click.Path())
def download(url, output_dir):
    click.echo(
        ops.download(
            url=url,
            root=output_dir
        )
    )


@cli.command(name="synthesize")
@click.option("-t", "--text", required=True, help="Text file to synthesize from")
@click.option("-o", "--output", required=True, help="File name for the resulting audio")
@click.option("-p", "--pitch", help="Voice pitch: -10..10", default=-4.0)
@click.option("-r", "--rate", required=True, type=click.FLOAT, help="Speaking rate: 0..5")
@click.option("-l", "--language", required=True, help="ex: ru-RU, en-EN")
@click.option("-v", "--voice", required=True, help="ex: ru-RU-Wavenet-D, en-US-Wavenet-I")
@click.option("-d", "--duration", required=True, type=click.FLOAT, help="Target duration. Will be used to adjust speaking rate.")
def synthesize(text, output, pitch, rate, language, voice, duration):
    ops.text_to_speech(
        file_name=text,
        language_code=language,
        voice_name=voice,
        speaking_rate=rate,
        pitch=pitch,
        output_path=output
    )
    speech_duration = float(ops.probe(path=output)['format']['duration'])
    click.echo(f"To match desired duration, set speaking rate to: {rate * speech_duration / duration}")


@cli.command(name="probe")
@click.argument('path', nargs=1, type=click.Path())
def probe(path):
    click.echo(ops.probe(path=path))
