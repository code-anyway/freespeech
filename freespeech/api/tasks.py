import json

from aiohttp import web

from freespeech.api import chat, media, transcript
from freespeech.lib import tasks
from freespeech.types import Error

routes = web.RouteTableDef()


def get_full_url(service: str, endpoint: str) -> str:
    SERVICE_URLS = {
        "transcript": "https://transcript-qux7zlmkmq-uc.a.run.app",
        "media": "https://media-qux7zlmkmq-uc.a.run.app",
        "chat": None,
    }
    return f"{SERVICE_URLS[service]}/{service}/{endpoint}"


async def schedule(web_request: web.Request) -> web.Response:  # type: ignore
    service = web_request.match_info["service"]
    endpoint = web_request.match_info["endpoint"]

    url = get_full_url(service, endpoint)

    tasks.schedule(method="POST", url=url, payload=await web_request.read())


async def run(web_request: web.Request) -> web.Response:
    service = web_request.match_info["service"]
    endpoint = web_request.match_info["endpoint"]

    if service == "transcript":
        if endpoint == "load":
            response = await transcript.load(web_request)
        elif endpoint == "translate":
            response = await transcript.translate(web_request)
        elif endpoint == "synthesize":
            response = await transcript.synthesize(web_request)
        elif endpoint == "save":
            response = await transcript.save(web_request)
        else:
            raise ValueError(f"Unknown endpoint {service}/{endpoint}")
    elif service == "media":
        if endpoint == "ingest":
            response = await media.ingest(web_request)
        else:
            raise ValueError(f"Unknown endpoint {service}/{endpoint}")
    elif service == "chat":
        if endpoint == "ask":
            response = await chat.ask(web_request)
        else:
            raise ValueError(f"Unknown endpoint {service}/{endpoint}")
    else:
        raise ValueError(f"Unknown service: {service}")

    return web.json_response(
        {
            "state": "Error" if isinstance(response, Error) else "Done",
            "result": json.loads(response.text),  # type: ignore
            "id": "42",
        }
    )
