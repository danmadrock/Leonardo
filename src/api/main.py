from fastapi import FastAPI
from src.api.routers import health_router, papers_router, reports_router, tasks_router
from src.core.logging import configure_logging

configure_logging()

app = FastAPI(title="Leonardo Research API", version="0.1.0")
app.include_router(health_router)
app.include_router(papers_router)
app.include_router(tasks_router)
app.include_router(reports_router)