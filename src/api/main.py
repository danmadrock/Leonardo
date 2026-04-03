from fastapi import FastAPI
from src.api.middleware.rate_limit import RateLimitMiddleware
from src.api.routers import health_router, papers_router, reports_router, research_router, tasks_router
from src.core.logging import configure_logging
from src.core.config import settings

configure_logging(settings.LOG_LEVEL)

app = FastAPI(title="Leonardo Research API", version="0.1.0")
app.add_middleware(RateLimitMiddleware)
app.include_router(health_router)
app.include_router(research_router)

# Legacy CRUD kept for internal/admin workflows.
app.include_router(papers_router, prefix="/internal")
app.include_router(tasks_router, prefix="/internal")
app.include_router(reports_router, prefix="/internal")