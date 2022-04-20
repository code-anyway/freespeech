from aiohttp import web

routes = web.RouteTableDef()

# Service: publish
# POST /media/{id}/{lang}/publish {url}
# Upload the media to a URL.


def upload_to_youtube(media_id, url):
    pass
