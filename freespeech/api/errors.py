import json

from aiohttp import web
from pydantic.json import pydantic_encoder

from freespeech.types import Error


def bad_request(error: Error) -> web.HTTPBadRequest:
    return web.HTTPBadRequest(
        text=json.dumps(pydantic_encoder(error)), content_type="application/json"
    )


class HTTPInputError(web.HTTPSuccessful):
    status_code = 299


def input_error(error: Error) -> web.HTTPException:
    return HTTPInputError(
        reason="299: Input Error",
        text=json.dumps(pydantic_encoder(error)),
        content_type="application/json",
    )
