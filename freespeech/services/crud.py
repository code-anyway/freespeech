from aiohttp import web


routes = web.RouteTableDef()

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
