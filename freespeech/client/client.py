from typing import Dict

import aiohttp


def create(
    api_key: str | None = None,
    *,
    headers: Dict[str, str] | None = None,
    url: str = "https://api.freespeech.com",
    timeout_sec: int = 1_800,
) -> aiohttp.ClientSession:
    timeout = aiohttp.ClientTimeout(total=timeout_sec)
    headers = headers or {}
    headers = {**headers, "Authorization": f"Bearer {api_key}"}
    return aiohttp.ClientSession(base_url=url, timeout=timeout, headers=headers)
