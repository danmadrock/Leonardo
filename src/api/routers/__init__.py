from src.api.routers.health import router as health_router
from src.api.routers.papers import router as papers_router
from src.api.routers.reports import router as reports_router
from src.api.routers.research import router as research_router
from src.api.routers.tasks import router as tasks_router

__all__ = [
    "health_router",
    "papers_router",
    "tasks_router",
    "reports_router",
    "research_router",
]
