class LeonardoError(Exception):
    """Base exception for all application errors."""


class SourceError(LeonardoError):
    """A data source failed to return results."""


class LLMError(LeonardoError):
    """LLM call failed after all retries."""


class PipelineError(LeonardoError):
    """Fatal pipeline error; task should be marked failed."""


class TaskNotFoundError(LeonardoError):
    """Requested task ID does not exist."""
