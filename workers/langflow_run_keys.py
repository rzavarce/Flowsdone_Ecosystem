"""Wiring shared by the workers that run Langflow flows: builds the
resolver that runs each flow with its owner tenant's key (see
app/application/services/langflow_run_keys.py).
"""

from app.adapters.outbound.db.langflow_account_repository import SqlAlchemyLangflowAccountRepository
from app.adapters.outbound.langflow.admin_client import LangflowAdminClient
from app.application.services.langflow_run_keys import LangflowRunKeys
from app.infrastructure.database import create_engine, create_sessionmaker


def build_langflow_run_keys() -> LangflowRunKeys:
    """Build the per-tenant run key resolver against Postgres and Langflow.

    Returns:
        LangflowRunKeys: The resolver, for ExecuteWorkflowUseCase.
    """
    sessionmaker = create_sessionmaker(create_engine())
    return LangflowRunKeys(
        admin=LangflowAdminClient(),
        accounts=SqlAlchemyLangflowAccountRepository(sessionmaker),
    )
