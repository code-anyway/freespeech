from aiohttp import web

routes = web.RouteTableDef()

# Service: speech
# POST /media/{id}/{lang}/transcribe
# Async. Launches a transcription job that will
# update media's transcript for a given language
# TODO: return a job id, maintain a jon queue, don't allow duplicates.
