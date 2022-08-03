from aiohttp import web
from pydantic.json import pydantic_encoder

from freespeech.types import Error


def bad_request(error: Error) -> web.HTTPBadRequest:
    return web.HTTPBadRequest(
        text=pydantic_encoder(error), content_type="application/json"
    )
