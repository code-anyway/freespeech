import click
import json
import logging
import freespeech.ops as ops


logger = logging.getLogger(__name__)


@click.group()
@click.version_option()
def cli():
    "null"


@cli.command(name="mix")
@click.argument('files', nargs=-1, type=click.Path())
@click.option("-o", "--output", required=True, help="File name for the resulting video")
@click.option("-v", "--video", required=True, help="Path to the video stream")
@click.option("-w", "--weights", required=True, help="Weights for each audio stream")
def mix(files, output, video, weights):
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
@click.option("-t", "--text_file", required=True, help="Text file to synthesize from")
@click.option("-o", "--output", required=True, help="File name for the resulting audio")
@click.option("-p", "--pitch", help="Voice pitch: -10..10", default=-4.0)
@click.option("-r", "--rate", type=click.FLOAT, help="Speaking rate: 0..5")
@click.option("-l", "--language", required=True, help="ex: ru-RU, en-EN")
@click.option("-v", "--voice", required=True, help="ex: ru-RU-Wavenet-D, en-US-Wavenet-I")
@click.option("-d", "--duration", required=True, type=click.FLOAT, help="Target duration used to calculate suggested speaking rate.")
def synthesize(text_file, output, pitch, rate, language, voice, duration):
    def _text_to_speech(text, rate):
        ops.text_to_speech(
            text=text,
            language_code=language,
            voice_name=voice,
            speaking_rate=rate,
            pitch=pitch,
            output_path=output
        )
        return float(ops.probe(path=output)['format']['duration'])

    if text_file.startswith("https://docs.google.com/document"):
        # Extract from google docs
        text=ops.extract_text_from_google_docs(url=text_file)
    else:
        # Read from local file
        with open(text_file) as lines:
            text = '\n'.join(lines)

    if rate == None:
        logger.info("Rate not set. Will calibrate the rate iteratively to match target duration.")
        logger.info("Setting rate to 1.0.")
        rate = 1.0
    
        while (not (0.0 <= (duration - (speech_duration := _text_to_speech(text, rate))) < 0.5)):
            rate *= speech_duration / duration
            logger.info(f"Output speech duration: {speech_duration}. Adjusted rate: {rate}")
    else:
        speech_duration = _text_to_speech(text, rate)
        click.echo(f"To match target duration, set speaking rate to: {rate * speech_duration / duration}")


@cli.command(name="probe")
@click.argument('path', nargs=1, type=click.Path())
def probe(path):
    click.echo(json.dumps(ops.probe(path=path)))
