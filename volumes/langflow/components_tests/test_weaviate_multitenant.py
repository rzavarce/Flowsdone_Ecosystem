"""Tests for WeaviateMultiTenantComponent in weaviate_multitenant.py.

Same isolation approach as the sibling test files: stubs `langflow.*`,
`weaviate` and `langchain_community.vectorstores.Weaviate` instead of
importing the real packages. The point of these tests is to verify the one
thing the native Langflow Weaviate component doesn't do: thread `tenant`
through to the underlying add_texts()/similarity_search() calls.

Run directly with:
    pytest volumes/langflow/components_tests/test_weaviate_multitenant.py
"""

from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path


class _FakeDocument:
    def __init__(self, page_content, metadata):
        self.page_content = page_content
        self.metadata = metadata


class _FakeWeaviateVectorStore:
    """Stand-in for langchain_community.vectorstores.Weaviate."""

    last_instance = None

    def __init__(self, client, index_name, text_key, embedding, by_text, attributes=None):
        self.client = client
        self.index_name = index_name
        self.text_key = text_key
        self.embedding = embedding
        self.by_text = by_text
        self.attributes = attributes
        self.add_texts_calls = []
        self.similarity_search_calls = []
        type(self).last_instance = self

    def add_texts(self, texts, metadatas=None, **kwargs):
        self.add_texts_calls.append({"texts": texts, "metadatas": metadatas, **kwargs})
        return [f"id-{i}" for i in range(len(texts))]

    def similarity_search(self, query, k, **kwargs):
        self.similarity_search_calls.append({"query": query, "k": k, **kwargs})
        return [_FakeDocument(page_content="resultado", metadata={"sku": "A1"})]


class _FakeTenant:
    def __init__(self, name):
        self.name = name


class _FakeSchema:
    """Simulates Weaviate server-side schema state, shared across fake clients.

    A real weaviate.Client holds no schema state itself (it lives on the
    server), so a fresh _FakeWeaviateClient() per test still needs to see
    whatever a previous call in that same test already created - hence the
    class-level (not instance-level) registries here.
    """

    classes: set = set()
    tenants: dict = {}
    create_class_calls: list = []
    add_class_tenants_calls: list = []
    properties: dict = {}

    def get(self, class_name):
        return {"class": class_name, "properties": [{"name": n} for n in type(self).properties.get(class_name, [])]}

    def exists(self, class_name):
        return class_name in type(self).classes

    def create_class(self, schema_class):
        type(self).classes.add(schema_class["class"])
        type(self).tenants.setdefault(schema_class["class"], set())
        type(self).create_class_calls.append(schema_class)

    def get_class_tenants(self, class_name):
        return [_FakeTenant(name=n) for n in type(self).tenants.get(class_name, set())]

    def add_class_tenants(self, class_name, tenants):
        type(self).tenants.setdefault(class_name, set())
        for t in tenants:
            type(self).tenants[class_name].add(t.name)
        type(self).add_class_tenants_calls.append((class_name, list(tenants)))


def _reset_weaviate_schema_state():
    _FakeSchema.classes = set()
    _FakeSchema.tenants = {}
    _FakeSchema.create_class_calls = []
    _FakeSchema.add_class_tenants_calls = []
    _FakeSchema.properties = {}


class _FakeWeaviateClient:
    def __init__(self, url=None, auth_client_secret=None):
        self.url = url
        self.auth_client_secret = auth_client_secret
        self.schema = _FakeSchema()


def _install_stubs() -> None:
    """Register minimal stand-ins for the third-party symbols this module imports."""

    class Component:
        pass

    class _InputBase:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    class StrInput(_InputBase):
        pass

    class SecretStrInput(_InputBase):
        pass

    class IntInput(_InputBase):
        pass

    class BoolInput(_InputBase):
        pass

    class HandleInput(_InputBase):
        pass

    class Output(_InputBase):
        pass

    class QueryInput(_InputBase):
        pass

    class Data:
        def __init__(self, data=None, **kwargs):
            self.data = data if data is not None else kwargs

        def to_lc_document(self):
            metadata = {k: v for k, v in self.data.items() if k != "text"}
            return _FakeDocument(page_content=self.data.get("text", ""), metadata=metadata)

    def docs_to_data(docs):
        return [Data(data={"text": d.page_content, **d.metadata}) for d in docs]

    def check_cached_vector_store(f):
        return f

    class LCVectorStoreComponent(Component):
        inputs = [
            HandleInput(name="ingest_data", display_name="Ingest Data"),
            QueryInput(name="search_query", display_name="Search Query"),
            BoolInput(name="should_cache_vector_store", display_name="Cache Vector Store"),
        ]

        def _prepare_ingest_data(self):
            ingest_data = self.ingest_data
            if not ingest_data:
                return []
            if not isinstance(ingest_data, list):
                ingest_data = [ingest_data]
            return ingest_data

    weaviate_module = types.ModuleType("weaviate")
    weaviate_module.Client = _FakeWeaviateClient
    weaviate_module.AuthApiKey = lambda api_key: {"api_key": api_key}
    weaviate_module.Tenant = _FakeTenant

    langchain_vectorstores_module = types.ModuleType("langchain_community.vectorstores")
    langchain_vectorstores_module.Weaviate = _FakeWeaviateVectorStore
    langchain_community_module = types.ModuleType("langchain_community")

    langflow = types.ModuleType("langflow")
    langflow_custom = types.ModuleType("langflow.custom")
    langflow_custom.Component = Component
    langflow_io = types.ModuleType("langflow.io")
    langflow_io.StrInput = StrInput
    langflow_io.SecretStrInput = SecretStrInput
    langflow_io.IntInput = IntInput
    langflow_io.BoolInput = BoolInput
    langflow_io.HandleInput = HandleInput
    langflow_io.Output = Output
    langflow_schema = types.ModuleType("langflow.schema")
    langflow_schema.Data = Data
    langflow_base = types.ModuleType("langflow.base")
    langflow_base_vectorstores = types.ModuleType("langflow.base.vectorstores")
    langflow_base_vectorstores_model = types.ModuleType("langflow.base.vectorstores.model")
    langflow_base_vectorstores_model.LCVectorStoreComponent = LCVectorStoreComponent
    langflow_base_vectorstores_model.check_cached_vector_store = check_cached_vector_store
    langflow_helpers = types.ModuleType("langflow.helpers")
    langflow_helpers_data = types.ModuleType("langflow.helpers.data")
    langflow_helpers_data.docs_to_data = docs_to_data

    sys.modules.setdefault("langflow", langflow)
    sys.modules["langflow.custom"] = langflow_custom
    sys.modules["langflow.io"] = langflow_io
    sys.modules["langflow.schema"] = langflow_schema
    sys.modules["langflow.base"] = langflow_base
    sys.modules["langflow.base.vectorstores"] = langflow_base_vectorstores
    sys.modules["langflow.base.vectorstores.model"] = langflow_base_vectorstores_model
    sys.modules["langflow.helpers"] = langflow_helpers
    sys.modules["langflow.helpers.data"] = langflow_helpers_data
    sys.modules["weaviate"] = weaviate_module
    sys.modules["langchain_community"] = langchain_community_module
    sys.modules["langchain_community.vectorstores"] = langchain_vectorstores_module


_install_stubs()

_MODULE_PATH = Path(__file__).parent.parent / "components" / "weaviate_multitenant.py"
_spec = importlib.util.spec_from_file_location("weaviate_multitenant", _MODULE_PATH)
weaviate_multitenant = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(weaviate_multitenant)

Data = sys.modules["langflow.schema"].Data
WeaviateMultiTenantComponent = weaviate_multitenant.WeaviateMultiTenantComponent


def _make_component(**overrides):
    component = WeaviateMultiTenantComponent()
    component.url = "http://weaviate:8080"
    component.api_key = ""
    component.index_name = "Productos"
    component.tenant = "fibralan"
    component.text_key = "text"
    component.id_key = ""
    component.where_filter_json = ""
    component.metadata_fields = ""
    component.search_by_text = False
    component.auto_provision = True
    component.embedding = None
    component.number_of_results = 4
    component.ingest_data = []
    component.search_query = ""
    component.should_cache_vector_store = True
    for key, value in overrides.items():
        setattr(component, key, value)
    return component


def test_build_vector_store_rejects_lowercase_index_name():
    component = _make_component(index_name="productos")

    try:
        component.build_vector_store()
    except ValueError as exc:
        assert "Productos" in str(exc)
    else:
        raise AssertionError("Expected ValueError")


def test_build_vector_store_passes_tenant_when_ingesting():
    productos = [
        Data(data={"text": "adaptador usb", "sku": "A1"}),
        Data(data={"text": "cable hdmi", "sku": "A2"}),
    ]
    component = _make_component(ingest_data=productos)

    component.build_vector_store()

    calls = _FakeWeaviateVectorStore.last_instance.add_texts_calls
    assert len(calls) == 1
    assert calls[0]["tenant"] == "fibralan"
    assert calls[0]["texts"] == ["adaptador usb", "cable hdmi"]


def test_build_vector_store_computes_deterministic_uuids_from_id_key():
    productos = [Data(data={"text": "adaptador usb", "sku": "A1"})]
    component = _make_component(ingest_data=productos, id_key="sku")

    component.build_vector_store()

    calls = _FakeWeaviateVectorStore.last_instance.add_texts_calls
    assert "uuids" in calls[0]
    assert len(calls[0]["uuids"]) == 1
    # Same sku must always produce the same id, across separate runs/components.
    other = _make_component(ingest_data=productos, id_key="sku")
    other.build_vector_store()
    assert calls[0]["uuids"] == _FakeWeaviateVectorStore.last_instance.add_texts_calls[0]["uuids"]


def test_build_vector_store_raises_when_id_key_missing_from_metadata():
    productos = [Data(data={"text": "adaptador usb"})]
    component = _make_component(ingest_data=productos, id_key="sku")

    try:
        component.build_vector_store()
    except ValueError as exc:
        assert "sku" in str(exc)
    else:
        raise AssertionError("Expected ValueError")


def test_search_documents_passes_tenant_and_returns_empty_without_query():
    component = _make_component(search_query="")

    results = component.search_documents()

    assert results == []


def test_search_documents_passes_tenant_to_similarity_search():
    component = _make_component(search_query="audifonos gamer")

    results = component.search_documents()

    calls = _FakeWeaviateVectorStore.last_instance.similarity_search_calls
    assert calls[0]["tenant"] == "fibralan"
    assert calls[0]["query"] == "audifonos gamer"
    assert len(results) == 1


def test_search_documents_parses_where_filter_json():
    where = '{"path": ["active"], "operator": "Equal", "valueBoolean": true}'
    component = _make_component(search_query="audifonos", where_filter_json=where)

    component.search_documents()

    calls = _FakeWeaviateVectorStore.last_instance.similarity_search_calls
    assert calls[0]["where_filter"] == {"path": ["active"], "operator": "Equal", "valueBoolean": True}


def test_search_documents_raises_on_invalid_where_filter_json():
    component = _make_component(search_query="audifonos", where_filter_json="{not json")

    try:
        component.search_documents()
    except ValueError as exc:
        assert "JSON" in str(exc)
    else:
        raise AssertionError("Expected ValueError")


def test_build_vector_store_creates_collection_and_tenant_when_missing():
    _reset_weaviate_schema_state()
    component = _make_component()

    component.build_vector_store()

    assert len(_FakeSchema.create_class_calls) == 1
    created = _FakeSchema.create_class_calls[0]
    assert created["class"] == "Productos"
    assert created["vectorizer"] == "none"
    assert created["multiTenancyConfig"] == {"enabled": True}
    assert len(_FakeSchema.add_class_tenants_calls) == 1
    class_name, tenants = _FakeSchema.add_class_tenants_calls[0]
    assert class_name == "Productos"
    assert [t.name for t in tenants] == ["fibralan"]


def test_build_vector_store_skips_creation_when_collection_and_tenant_already_exist():
    _reset_weaviate_schema_state()
    _FakeSchema.classes.add("Productos")
    _FakeSchema.tenants["Productos"] = {"fibralan"}
    component = _make_component()

    component.build_vector_store()

    assert _FakeSchema.create_class_calls == []
    assert _FakeSchema.add_class_tenants_calls == []


def test_build_vector_store_adds_only_the_missing_tenant_to_an_existing_collection():
    _reset_weaviate_schema_state()
    _FakeSchema.classes.add("Productos")
    _FakeSchema.tenants["Productos"] = {"otro_tenant"}
    component = _make_component()

    component.build_vector_store()

    assert _FakeSchema.create_class_calls == []
    assert len(_FakeSchema.add_class_tenants_calls) == 1
    _, tenants = _FakeSchema.add_class_tenants_calls[0]
    assert [t.name for t in tenants] == ["fibralan"]


def test_build_vector_store_does_not_touch_schema_when_auto_provision_is_false():
    _reset_weaviate_schema_state()
    component = _make_component(auto_provision=False)

    component.build_vector_store()

    assert _FakeSchema.create_class_calls == []
    assert _FakeSchema.add_class_tenants_calls == []


def test_build_vector_store_returns_every_collection_property_but_the_text_key_by_default():
    _reset_weaviate_schema_state()
    _FakeSchema.classes.add("Productos")
    _FakeSchema.tenants["Productos"] = {"fibralan"}
    _FakeSchema.properties["Productos"] = ["text", "documentId", "sku", "active"]
    component = _make_component()

    component.build_vector_store()

    assert _FakeWeaviateVectorStore.last_instance.attributes == ["documentId", "sku", "active"]


def test_build_vector_store_uses_metadata_fields_when_set():
    _reset_weaviate_schema_state()
    _FakeSchema.classes.add("Productos")
    _FakeSchema.tenants["Productos"] = {"fibralan"}
    _FakeSchema.properties["Productos"] = ["text", "documentId", "sku", "active"]
    component = _make_component(metadata_fields=" documentId , sku ,text")

    component.build_vector_store()

    assert _FakeWeaviateVectorStore.last_instance.attributes == ["documentId", "sku"]


def test_build_vector_store_passes_no_attributes_when_the_collection_does_not_exist_yet():
    _reset_weaviate_schema_state()
    component = _make_component(auto_provision=False)

    component.build_vector_store()

    assert _FakeWeaviateVectorStore.last_instance.attributes == []


def test_component_without_metadata_fields_still_works_for_flows_saved_before_it_existed():
    _reset_weaviate_schema_state()
    _FakeSchema.classes.add("Productos")
    _FakeSchema.tenants["Productos"] = {"fibralan"}
    _FakeSchema.properties["Productos"] = ["text", "documentId"]
    component = _make_component()
    del component.metadata_fields

    component.build_vector_store()

    assert _FakeWeaviateVectorStore.last_instance.attributes == ["documentId"]

