from fastapi import APIRouter

from .internal import health as internal_health
from .proxy import anime as proxy_anime
from .proxy import episodes as proxy_episodes
from .proxy import import_anilist as proxy_import_anilist
from .proxy import schedule as proxy_schedule
from .proxy import search as proxy_search
from .admin import anime as admin_anime

router = APIRouter(prefix="/api")

_internal_routers = [
    internal_health.router,
]

_admin_routers = [
    admin_anime.router,
]

_proxy_routers = [
    proxy_schedule.router,
    proxy_search.router,
    proxy_anime.router,
    proxy_episodes.router,
    proxy_import_anilist.router,
]

for _router in [*_internal_routers, *_admin_routers, *_proxy_routers]:
    router.include_router(_router)
