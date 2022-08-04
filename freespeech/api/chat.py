import logging
from typing import Dict, Tuple

import aiohttp
from aiohttp import web
from pydantic import ValidationError
from pydantic.json import pydantic_encoder

from freespeech.api import errors
from freespeech.client import client, tasks, transcript
from freespeech.client.tasks import Task
from freespeech.lib import chat
from freespeech.types import (
    OPERATIONS,
    AskRequest,
    AskResponse,
    Error,
    LoadRequest,
    SynthesizeRequest,
    TranslateRequest,
    assert_never,
    is_operation,
)

routes = web.RouteTableDef()
logger = logging.getLogger(__name__)

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


def handle_response(response: Task | Error) -> web.Response:
    match response:
        case Error():
            raise web.HTTPBadRequest(body=pydantic_encoder(response))
        case Task():
            return web.Response(body=pydantic_encoder(response))


def _raise_unknown_query(intent: str | None = None):
    raise aiohttp.web.HTTPBadRequest(
        text=f"Don't know how to handle {intent or 'this'}.\n{USER_EXAMPLES['other']}"
    )


def _build_request(
    intent: str, entities: Dict
) -> Tuple[LoadRequest | TranslateRequest | SynthesizeRequest, Dict]:
    operation = intent.capitalize()
    # todo (alex) remove when new training data arrives
    if operation == "Dub":
        operation = "Synthesize"
    if not is_operation(operation):
        raise ValueError(f"Unknown intent: {operation}. Expected: {OPERATIONS}")

    url, *_ = entities.get("url", None) or [None]
    method, *_ = entities.get("method", None) or ["Machine B"]
    lang, *_ = entities.get("language", None) or [None]

    state = {"url": url, "method": method, "lang": lang}
    state = {k: v for k, v in state.items() if v}

    match operation:
        case "Transcribe":
            return LoadRequest(**{"source": url, "method": method, "lang": lang}), state
        case "Translate":
            return TranslateRequest(**{"transcript": url, "lang": lang}), state
        case "Synthesize":
            return SynthesizeRequest(**{"transcript": url}), state
        case never:
            assert_never(never)


async def _ask(
    ask_request: AskRequest, session: aiohttp.ClientSession
) -> AskResponse | Error:
    if ask_request.intent:
        intent = ask_request.intent
        entities: Dict = {}
    else:
        intent, entities = await chat.intent(ask_request.message)

    state = {**ask_request.state, **entities}
    request, state = _build_request(intent, state)

    match request:
        case LoadRequest():
            assert isinstance(request.source, str)
            response = await transcript.load(
                source=request.source,
                method=request.method,
                lang=request.lang,
                session=client.create(),
            )
            result = await tasks.future(response, session)
            if isinstance(result, Error):
                return result

            save_response = await transcript.save(
                result, method="Google", location=None, session=session
            )
            saved = await tasks.future(save_response, session)
            if isinstance(saved, Error):
                return saved

            return AskResponse(message=f"Here you are: {saved.url}", state=state)

        case TranslateRequest():
            response = await transcript.translate(
                transcript=request.transcript,
                lang=request.lang,
                session=client.create(),
            )
            result = await tasks.future(response, session)
            if isinstance(result, Error):
                return result

            save_response = await transcript.save(
                result, method="Google", location=None, session=session
            )
            saved = await tasks.future(save_response, session)
            if isinstance(saved, Error):
                return saved

            return AskResponse(message=f"Here you are: {saved.url}", state=state)

        case SynthesizeRequest():
            response = await transcript.synthesize(
                transcript=request.transcript, session=session
            )
            result = await tasks.future(response, session)
            if isinstance(result, Error):
                return result

            media_url = result.video or result.audio
            return AskResponse(message=f"Here you are: {media_url}", state=state)


@routes.post("/chat/ask")
async def ask(web_request: web.Request) -> web.Response:
    params = await web_request.json()

    try:
        response = await _ask(ask_request=AskRequest(**params), session=client.create())
        if isinstance(response, Error):
            raise errors.bad_request(response)

        return web.json_response(pydantic_encoder(response))
    except (ValidationError, ValueError) as e:
        raise errors.bad_request(Error(message=str(e)))
