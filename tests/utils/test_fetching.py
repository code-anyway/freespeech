from freespeech.utils import fetching
import pytest

# test 1 page
# test multiple pages with 3 oldest pages


@pytest.mark.asyncio
async def test_fetching():
    out1 = await fetching.scrape_transcripts(
        "https://www.president.gov.ua/news/speeches?page="
    )
    assert out1 == {}
