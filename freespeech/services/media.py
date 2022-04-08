

def import_transcript_from_notion_page(page_id: str) -> Transcript:
    transcript = nc.get_transcript(page_id)
    datastore.put(transcript)
    return transcript


def create_voiceover_from_notion_page(page_id: str) -> Dict[str, object]:
    page_info = nc.get_page_info(page_id)
    properties = nc.get_page_properties(page=page_info)

    def _unpack_rollup_property(property: Dict) -> str:
        value = nc.parse_property_value(property)
        assert type(value) is list
        assert type(value[0]) is dict

        res = nc.parse_property_value(value[0])
        assert type(res) is str

        return res

    origin = _unpack_rollup_property(properties["Origin"])
    source_lang = _unpack_rollup_property(properties["Source Language"])
    voice = properties["Voice"]
    ratio = 0.8 if not (value := properties["Weight"]) else float(value)

    transcript = import_transcript_from_notion_page(page_id)

    media = voiceover(
        url=origin,
        transcript_id=transcript._id,
        source_lang=source_lang,
        voice=voice,
        ratio=ratio,
    )

    assert media.video, "Translated media has no video"
    video = media.video[0]

    assert video.url, "Resulting video has no URL"
    url = video.url

    result = {
        "url": url.replace("gs://", "https://storage.googleapis.com/"),
        "duration_ms": video.duration_ms,
        "title": media.title,
        "description": media.description,
        "tags": media.tags,
    }

    return result

