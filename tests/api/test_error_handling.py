import logging
from typing import Generator

import aiohttp
import pytest
import pytest_asyncio
from aiohttp import ClientResponseError, web
from aiohttp.pytest_plugin import AiohttpClient

from freespeech import cli

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

    app = web.Application(middlewares=[cli.error_handler_middleware])
    app.add_routes(routes)
    _ = await aiohttp_server(app, port=8088)
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
    result = await client.get("/handled_exception")
    try:
        result.raise_for_status()
        assert False, "Should have raised an exception"
    except ClientResponseError as e:
        assert e.status == 400
        assert e.message == "Handled exception. Some user message."

    result = await client.get("permission_error")
    try:
        result.raise_for_status()
        assert False, "Should have raised an exception"
    except ClientResponseError as e:
        assert e.status == 400
        assert e.message == "Permissions not enough"


@pytest.mark.asyncio
async def test_500_exception(client):
    result = await client.get("/unhandled_exception")
    try:
        result.raise_for_status()
        assert False, "Should have raised an exception"
    except ClientResponseError as e:
        assert e.status == 500
        assert e.message == "Internal Server Error"


@pytest.mark.asyncio
async def test_downstream_http_error(client):
    try:
        result = await client.get("/downstream_client_error")
        result.raise_for_status()
    except ClientResponseError as e:
        assert e.status == 400
        assert e.message == "Not Found"
