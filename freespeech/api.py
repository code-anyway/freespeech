from aiohttp import web
from freespeech import services


routes = web.RouteTableDef()


@routes.get('/dubs/from_notion/{page_id}')
async def dubs_from_notion(request):
    page_id = request.match_info.get('page_id', None)
    dub = services.create_voiceover_from_notion_page(page_id)
    return web.json_response(dub)
