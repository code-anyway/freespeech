from aiohttp import ClientResponse, ClientResponseError


async def _raise_if_error(resp) -> None:
    """Raise if error response, take details from body
    This function should be used instead of a standard `raise_for_status()` since
    we are passing exception details in response body rather than in HTTP response
    reason.
    """
    if ok(resp):
        return
    error_message = await resp.text()
    raise ClientResponseError(
        status=resp.status,
        request_info=resp.request_info,
        message=error_message,
        history=resp.history,
    )


def ok(resp: ClientResponse):
    return resp.ok and resp.status != 299
