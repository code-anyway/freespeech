from freespeech.utils import fetch_president_ua
from typing import Dict


async def scrape_transcripts(url: str) -> Dict[str, Dict[str, str]]:
    # check for valid url por favor
    PRESIDENT_URL = "https://www.president.gov.ua/news/speeches?page="
    if PRESIDENT_URL.startswith(url):
        return await fetch_president_ua.all_speeches(PRESIDENT_URL)
    else:
        raise ValueError(f"Unsupported source: {url}")
