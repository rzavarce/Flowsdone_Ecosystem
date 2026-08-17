"""Small cross-cutting utility helpers."""

from api_gateway.app.core.context import correlation_id_ctx


def get_correlation_id() -> str | None:
    """Return the correlation id of the request currently being processed.

    Returns:
        The correlation id, or None if called outside a request context.
    """
    return correlation_id_ctx.get()
