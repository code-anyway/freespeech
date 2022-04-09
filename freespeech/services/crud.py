# Conventions:
# - id is sha256 of a URL
# - lang is a language tag (i.e. en-US, pt-BR)

# Service: CRUD
# POST /media/ {url, lang}
# Upload media.
# Media will be available under /media/{id}/{lang} where id is a sha256 of a url.

# Service: CRUD
# LIST /media/
# Get all media records

# Service: CRUD
# LIST /media/{id}
# Get all media records for an ID.

# Service: CRUD
# GET /media/{id}/{lang}
# Get a media record for a given id and language.

# Service: CRUD
# GET /media/{id}/{lang}/transcript
# Get transcript in lang for media

# Service: CRUD
# POST /media/{id}/{lang}/transcript {events}
# Updates transcript for a language.


def get_media(url: str) -> Media:
    res = datastore.get_by_key_value("origin", url, "media")
    if res:
        media, *tail = res
        logger.info(f"Cache hit for {url}. _id={media._id}")

        if tail:
            logger.warning(f"Extra records for {url}: {tail}")
    else:
        media = youtube.download(url, env.get_storage_url())
        logger.info(f"Downloaded {url} as {media._id}")

    datastore.put(media)

    return media
