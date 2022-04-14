from aiohttp import web

routes = web.RouteTableDef()

# Service: language
# POST /media/{id}/{lang}/translate {target}
# Translates media info and transcript to a target language.
