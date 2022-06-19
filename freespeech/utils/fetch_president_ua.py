from bs4 import BeautifulSoup as bs
import requests
import asyncio
import itertools

headers = {
    "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 12_3_1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/100.0.4896.127 Safari/537.36",
}


def fast_soup(url):
    request = requests.get(url, headers=headers)
    return bs(request.content, "html.parser")


def pull_transcript(url):
    try:
        soup = fast_soup(url)
        body_paragraphs = soup.find("div", "article_content").find_all("p")
        return "\n".join([p.getText() for p in body_paragraphs])
    except AttributeError:
        print("missing transcript")
        return ""


def pull_languages(base_path):
    langs = [
        ("en", "/en"),
        ("ru", "/ru"),
        ("uk", ""),
    ]  # ukranian isn't part of the path
    languages_to_transcripts = {}
    for key_lang, lang_path in langs:
        url = f"https://www.president.gov.ua{lang_path}{base_path}"
        transcript = pull_transcript(url)

        if transcript:
            languages_to_transcripts[key_lang] = transcript

    return languages_to_transcripts


async def link_to_transcript(li):
    # you could pull the video while pulling 1 of the languages
    try:
        video_page = li.find("div", "row").find("a").get("href")
        soup = fast_soup(video_page)
        yt_embed_soup = fast_soup(soup.find("iframe").get("src"))
        yt_url = yt_embed_soup.find("head").find("link", rel="canonical").get("href")

        transcript_url = li.find("div", "item_stat_headline").find("a").get("href")
        transcript_path = transcript_url.replace("https://www.president.gov.ua", "")

        pulled = pull_languages(transcript_path)
        return (yt_url, pulled)
    except AttributeError:
        print("missing a video or something")
        return False


async def get_speeches(url):
    soup = fast_soup(url)
    speech_list_items = soup.find_all("div", "item_stat cat_stat")
    page_scrapers = [link_to_transcript(li) for li in speech_list_items]

    links_to_transcrips = await asyncio.gather(*page_scrapers)
    links_to_transcripts = [item for item in links_to_transcrips if item]
    return links_to_transcripts


async def all_speeches(url, pagerange=False):
    out = []
    if pagerange:
        start, end = pagerange
    else:
        start = 1
        # I'd fix this but it's too funny
        end = int(fast_soup(url).find_all("a", "pag")[:-2].getText())
    for x in range(start, end):
        out += [get_speeches(url + str(x))]
    speeches = await asyncio.gather(*out)
    return dict(itertools.chain(*speeches))
