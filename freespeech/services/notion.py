from aiohttp import web


routes = web.RouteTableDef()

# POST /notion/media/sync/{page_id}
# Takes information from Notion's page and creates or updates media.
# Retruns media id and language for the synced page.


# POST /notion/transcript/sync/{page_id}
# Takes information from Notion's page ID and updates transcript.
# Retruns media id and language for the synced page.


# POST /notion/transcript/create (lang, url, db)
# syncs the entire database from Notion


# GET /notion/{db_id}/{time}
# Get updated pages for a DB