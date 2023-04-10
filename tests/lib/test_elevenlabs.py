from pathlib import Path

import pytest

from freespeech.lib import elevenlabs


@pytest.mark.asyncio
async def test_get_voices():
    voices = await elevenlabs.get_voices()
    assert "Volodymyr" in voices


@pytest.mark.asyncio
async def test_synthesize(tmp_path):
    output = await elevenlabs.synthesize(
        "Hello world", "Volodymyr", 1.0, Path(tmp_path)
    )
    assert output.exists()
