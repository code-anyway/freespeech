import logging
from typing import Generator

import aiohttp
import pytest
import pytest_asyncio
from aiohttp import ClientResponseError, web
from aiohttp.pytest_plugin import AiohttpClient

from freespeech.api.errors import bad_request
from freespeech.api.middleware import error_handler_middleware
from freespeech.client.errors import _raise_if_error
from freespeech.types import Error

logger = logging.getLogger(__name__)


@pytest_asyncio.fixture
async def webapp(aiohttp_server, aiohttp_client):
    routes = web.RouteTableDef()

    @routes.get("/success")
    async def make_success(request):
        return web.Response(text="OK")

    @routes.get("/handled_exception")
    async def make_handled_exception(request):
        raise AttributeError("Handled exception. Some user message.")

    @routes.get("/permission_error")
    async def make_permission_error(request):
        raise PermissionError("Permissions not enough")

    @routes.get("/unhandled_exception")
    async def make_unhandled_exception(request):
        raise TypeError("Just an unhandled error - should be 500")

    @routes.get("/downstream_client_error")
    async def make_downstream_client_error(request):
        async with aiohttp.ClientSession() as session:
            async with session.get("http://google.com/abracadabranont_1234asd") as resp:
                resp.raise_for_status()
                assert False, "Should not reach here"

    app = web.Application(middlewares=[error_handler_middleware])
    app.add_routes(routes)
    return app


@pytest_asyncio.fixture
async def client(aiohttp_client, webapp) -> Generator[AiohttpClient, None, None]:
    return await aiohttp_client(webapp)


@pytest.mark.asyncio
async def test_success(client):
    result = await client.get("/success")
    assert result.ok
    text = await result.text()
    assert text == "OK"


@pytest.mark.asyncio
async def test_handled_exception_should_be_4XX(client):
    resp = await client.get("/handled_exception")
    try:
        await _raise_if_error(resp)
        assert False, "Should have raised an exception"
    except ClientResponseError as e:
        assert e.status == 400
        assert e.message == "Handled exception. Some user message."

    result = await client.get("permission_error")
    try:
        await _raise_if_error(result)
        assert False, "Should have raised an exception"
    except ClientResponseError as e:
        assert e.status == 400
        assert e.message == "Permissions not enough"


@pytest.mark.asyncio
async def test_500_exception(client):
    resp = await client.get("/unhandled_exception")
    try:
        await _raise_if_error(resp)
        assert False, "Should have raised an exception"
    except ClientResponseError as e:
        assert e.status == 500
        assert e.message == "500 Internal Server Error\n\nServer got itself in trouble"


@pytest.mark.asyncio
async def test_downstream_http_error(client):
    try:
        resp = await client.get("/downstream_client_error")
        await _raise_if_error(resp)
    except ClientResponseError as e:
        assert e.status == 400
        assert e.message == "Not Found"


def test_bad_request_formatting():
    e = Error(message="Test error", details="This is extra details")
    http_error = bad_request(e)
    assert http_error.status == 400
    assert (
        http_error.text
        == '{"message": "Test error", "details": "This is extra details"}'
    )
