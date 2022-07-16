import json
import logging
from typing import Sequence

import aiohttp
from aiohttp import web
from pydantic.json import pydantic_encoder

from freespeech import client
from freespeech.lib import chat, speech
from freespeech.types import Error, Event, Job, Message, Source

routes = web.RouteTableDef()
logger = logging.getLogger(__name__)

CLIENT_TIMEOUT = 3600

# Events with the gap greater than GAP_MS won't be contatenated.
GAP_MS = 1400

# Won't attempt concatenating events if one is longer than LENGTH.
PHRASE_LENGTH = 600

# no newlines allowed in messages - would break HTTPError contract!
USER_EXAMPLES = {
    "translate": (
        "Try `translate https://docs.google.com/document/d/"
        "1FbV0eW4Q-yKWYjPkMRCrGd2yD78n7MtswVmN9LSo4mA/edit to Ukrainian` or just /help"
    ),
    "dub": (
        "Try `dub https://docs.google.com/document/d/"
        "1FbV0eW4Q-yKWYjPkMRCrGd2yD78n7MtswVmN9LSo4mA/edit` or just /help"
    ),
    "transcribe": (
        "try `Transcribe https://www.youtube.com/watch?v=N9B59PHIFbA "
        "in English using Machine A` or just /help"
    ),
    "other": (
        "To start, try following: `Transcribe https://www.youtube.com/"
        "watch?v=N9B59PHIFbA in English using Machine A` or /help"
    ),
}


def normalize_speech(
    events: Sequence[Event], method: speech.Normalization
) -> Sequence[Event]:
    return speech.normalize_speech(
        events, gap_ms=GAP_MS, length=PHRASE_LENGTH, method=method
    )


def handle_response(response: Job | Error) -> web.Response:
    text = json.dumps(response, default=pydantic_encoder)

    match response:
        case Error():
            raise web.HTTPBadRequest(text=text, content_type="application/json")
        case Job():
            return web.Response(text=text, content_type="application/json")


def _raise_unknown_query(intent: str | None = None):
    raise aiohttp.web.HTTPBadRequest(
        text=f"Don't know how to handle {intent or 'this'}.\n{USER_EXAMPLES['other']}"
    )


@routes.post("/ask")
async def ask(request):
    params = await request.json()
    message = Message(**params)

    if not message.intent:
        try:
            intent, entities = await chat.intent(message.text)
            state = {**message.state, **entities}
        except ValueError:
            _raise_unknown_query(intent)
    else:
        intent = message.intent

    lang = state.get("lang", None)
    url = state.get("url", None)

    # TODO (astaff): pass trace and auth headers here
    session = aiohttp.ClientSession(
        base_url="http://localhost:8080",
        timeout=aiohttp.ClientTimeout(CLIENT_TIMEOUT),
    )

    match intent:
        case "transcribe":
            response = await client.transcript(
                session=session, origin=Source(state), lang=lang
            )
            return handle_response(response)

        case "translate":
            response = await client.translate(
                transcript=await client.load(url=url),
                lang=lang,
            )
            return handle_response(response)

        case "synth":
            response = await client.synth(
                transcript=await client.load(url=url),
            )
            return handle_response(response)

        case _:
            _raise_unknown_query(intent=intent)
