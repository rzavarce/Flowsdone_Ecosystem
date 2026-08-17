"""Tests for AppConnectorFactory."""

from __future__ import annotations

from api_gateway.app.adapters.outbound.apps.factory import AppConnectorFactory
from api_gateway.app.adapters.outbound.apps.langflow_app_connector import LangflowAppConnector


def test_build_all_registers_langflow():
    connectors = AppConnectorFactory().build_all(ingest_message_use_case="fake-ingest-use-case")

    assert set(connectors.keys()) == {"langflow"}
    assert isinstance(connectors["langflow"], LangflowAppConnector)
