from __future__ import annotations
import logging
import structlog


def configure_logging(level: str = "INFO") -> None:
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.JSONRenderer(),
        ],
        logger_factory=structlog.PrintLoggerFactory(),
    )
    logging.basicConfig(level=getattr(logging, level.upper()))


def bind_task_context(task_id: str) -> None:
    structlog.contextvars.bind_contextvars(task_id=task_id)


def clear_task_context() -> None:
    structlog.contextvars.clear_contextvars()