from aiohttp import web

routes = web.RouteTableDef()


# Service: dub
# POST /media/{id}/{lang}/dub {lang, voice}
# Async. Launches a dubbing process that will create or update media for target lang
@routes.post("/media/{id}/{lang}/dub")
async def create_dub(request):
    raise NotImplementedError()
