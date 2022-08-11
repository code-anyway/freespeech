import json

from aiohttp import web
from pydantic.json import pydantic_encoder

from freespeech.types import Error


def bad_request(error: Error) -> web.HTTPBadRequest:
    return web.HTTPBadRequest(
        text=json.dumps(pydantic_encoder(error)), content_type="application/json"
    )
