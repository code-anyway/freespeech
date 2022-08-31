import pytest
from pydantic.json import pydantic_encoder

from freespeech.client import client


@pytest.mark.asyncio
async def test_malformed(mock_client, monkeypatch) -> None:
    monkeypatch.setattr(client, "create", mock_client)
    session = mock_client()
    # session = client.create()
    async with session.post(
        "/api/transcript/save", json=pydantic_encoder({"hello"})
    ) as resp:
        if resp.ok and resp.status != 299:
            assert False
