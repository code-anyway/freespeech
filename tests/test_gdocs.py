import pytest

from freespeech import gdocs
from googleapiclient import errors


def test_extract():
    res = gdocs.extract(
        "https://docs.google.com/document/d/1OlGGnR41Z7rC3UKxgiMSSlfvvfa_vddw3JHaKbP8z6w/edit"  # noqa: E501
    )
    assert res == "Hello World\n\nNew Paragraph\n"

    with pytest.raises(errors.HttpError, match=r"HttpError 404 .+"):
        gdocs.extract("https://docs.google.com/document/d/INVALID_ID/edit")

    with pytest.raises(ValueError, match=r"Invalid URL: .*"):
        gdocs.extract("https://docs.google.com/INVALID_GDOCS_URL")
