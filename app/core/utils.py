from app.core.context import correlation_id_ctx

def get_correlation_id() -> str | None:
    return correlation_id_ctx.get()
