from dataclasses import replace

import pytest
from test_transcript import EXPECTED_TRANSCRIPT

from freespeech.lib import gdocs


def test_extract():
    correct_url = (
        "https://docs.google.com/document/d/"
        "1OlGGnR41Z7rC3UKxgiMSSlfvvfa_vddw3JHaKbP8z6w/edit"
    )
    res = gdocs.extract(correct_url)
    assert res == ("Hello World", "Hello World\n\nNew Paragraph\n")

    with pytest.raises(RuntimeError, match=r"Requested entity was not found."):
        gdocs.extract("https://docs.google.com/document/d/INVALID_ID/edit")

    with pytest.raises(PermissionError, match=r"The caller does not have permission"):
        no_perm = (
            "https://docs.google.com/document/d/"
            "1kfP8KZo4wKfPrFWDfdbMJvvGR6ZBzHgcOMu-DAgstuc/edit"
        )
        gdocs.extract(no_perm)

    with pytest.raises(ValueError, match=r"Invalid URL: .*"):
        gdocs.extract("https://docs.google.com/INVALID_GDOCS_URL")


def test_load():
    expected_transcript = replace(
        EXPECTED_TRANSCRIPT, title="Google Docs with speechrate integration test"
    )
    url = "https://docs.google.com/document/d/1zzvy4wBE96quSWP3VT7P_rj8b7gg7STEoLSNGSiZ_jM/edit?usp=sharing"  # noqa: E501
    transcript = gdocs.load(url, format="SSMD")
    assert transcript == expected_transcript


def test_create():
    expected_transcript = replace(EXPECTED_TRANSCRIPT, title="test_gdocs::test_create")
    url = gdocs.create(source=expected_transcript, format="SSMD")
    transcript = gdocs.load(url, format="SSMD")
    assert transcript == expected_transcript


def test_long_transcript():
    url = "https://docs.google.com/document/d/1FQEWOvJPq3_KR7pm2-L_GWqHgKRP9iq0Cx1vwNGCptg/edit#"  # noqa: E501
    transcript = gdocs.load(url=url, format="SSMD")

    assert transcript.source.url == "https://www.youtube.com/watch?v=U93QRMcQU5Y"
    assert len(transcript.events) == 14
