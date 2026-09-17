"""Weaviate (Multi-Tenant): reusable vector store component with tenant isolation.

The native "Weaviate" component that ships with this Langflow version
(langflow/components/vectorstores/weaviate.py, built on
langchain_community.vectorstores.Weaviate + weaviate-client v3, pinned in
dockers/Dockerfile.langflow) has no tenant support anywhere in its code
path: build_vector_store() never passes `tenant` to Weaviate.from_documents(),
and search_documents() calls similarity_search() with no kwargs. This holds
even in the latest upstream Langflow (verified against langflow-ai/langflow
main, which moved to weaviate-client v4 but still doesn't expose a tenant
input on its Weaviate component).

What DOES support tenant, already, without touching the v3 REST/batch API
directly: the instance methods of langchain_community.vectorstores.Weaviate
itself - add_texts(..., tenant=...) forwards to
client.batch.add_data_object(..., tenant=...), and
similarity_search_by_text/similarity_search_by_vector(..., tenant=...) call
.with_tenant(...) on the query builder. Weaviate.from_documents() (a
classmethod used by the native component) does NOT thread tenant through,
so this component builds the Weaviate instance directly and calls its
instance methods instead, to reach that tenant support.

One component per Langflow project would duplicate this same logic with a
different `tenant` value hardcoded in each; instead this single component
takes tenant as a required input, so any flow in any project can reuse it
by just setting which tenant it operates for.

The `url` field's default comes from the WEAVIATE_URL env var of the
Langflow container (docker-compose.yml service `langflow`) rather than a
literal - same pattern already used for GATEWAY_INTERNAL_URL in that same
service block ("la tool lee esto via os.environ, nunca hardcodeado en el
flow"). It's still a plain default: editable per-flow from the canvas like
any other input, and falls back to the local dev URL if the env var isn't
set, so a missing env var can't break Langflow's component scan at import.
"""

from __future__ import annotations

import json
import os
import uuid
from typing import Any

import weaviate
from langchain_community.vectorstores import Weaviate
from langflow.base.vectorstores.model import LCVectorStoreComponent, check_cached_vector_store
from langflow.helpers.data import docs_to_data
from langflow.io import BoolInput, HandleInput, IntInput, SecretStrInput, StrInput
from langflow.schema import Data

_ID_NAMESPACE = uuid.NAMESPACE_URL
_DEFAULT_WEAVIATE_URL = os.environ.get("WEAVIATE_URL", "http://weaviate:8080")


class WeaviateMultiTenantComponent(LCVectorStoreComponent):
    display_name = "Weaviate (Multi-Tenant)"
    description = (
        "Vector store de Weaviate con soporte de multi-tenancy nativo (tenant obligatorio en "
        "cada escritura y búsqueda). Reusable en cualquier proyecto/tenant de Langflow: la "
        "colección y el tenant se configuran como inputs, no están hardcodeados."
    )
    name = "WeaviateMultiTenant"
    icon = "Weaviate"

    inputs = [
        StrInput(name="url", display_name="Weaviate URL", value=_DEFAULT_WEAVIATE_URL, required=True),
        SecretStrInput(name="api_key", display_name="API Key", required=False),
        StrInput(
            name="index_name",
            display_name="Nombre de la colección",
            required=True,
            info="Requiere nombre capitalizado (ej. 'Productos').",
        ),
        StrInput(
            name="tenant",
            display_name="Tenant",
            required=True,
            info="Nombre del tenant dentro de la colección (debe existir previamente vía /v1/schema/{clase}/tenants).",
        ),
        StrInput(name="text_key", display_name="Text Key", value="text", advanced=True),
        StrInput(
            name="id_key",
            display_name="Campo de id determinístico",
            advanced=True,
            info=(
                "Nombre del campo en los metadatos (ej. 'sku') a partir del cual se computa un "
                "id determinístico (uuid5) para cada objeto, así los reruns de sync actualizan "
                "en vez de duplicar. Vacío = Weaviate genera un id aleatorio en cada insert."
            ),
        ),
        StrInput(
            name="where_filter_json",
            display_name="Filtro (JSON)",
            advanced=True,
            info='Filtro opcional de Weaviate para la búsqueda, como JSON (ej. \'{"path":["active"],"operator":"Equal","valueBoolean":true}\').',
        ),
        BoolInput(
            name="search_by_text",
            display_name="Buscar por texto",
            value=False,
            advanced=True,
            info="Activar solo si la colección tiene un vectorizer configurado en el servidor. Con vectorizer 'none' dejar en false.",
        ),
        BoolInput(
            name="auto_provision",
            display_name="Auto-crear colección/tenant",
            value=True,
            advanced=True,
            info=(
                "Si la colección 'index_name' no existe, la crea con multiTenancyConfig "
                "habilitado (sin properties explícitas - se infieren por auto-schema del "
                "primer insert). Si el tenant no existe dentro de la colección, lo da de "
                "alta. Desactivar en un Weaviate donde el schema deba controlarse aparte."
            ),
        ),
        *LCVectorStoreComponent.inputs,
        HandleInput(name="embedding", display_name="Embedding", input_types=["Embeddings"]),
        IntInput(
            name="number_of_results",
            display_name="Number of Results",
            value=4,
            advanced=True,
        ),
    ]

    def _connect_client(self) -> weaviate.Client:
        """Connects to Weaviate using the v3 client API (pinned in the Langflow image)."""
        if self.api_key:
            auth_config = weaviate.AuthApiKey(api_key=self.api_key)
            return weaviate.Client(url=self.url, auth_client_secret=auth_config)
        return weaviate.Client(url=self.url)

    def _ensure_collection(self, client: weaviate.Client) -> None:
        """Creates `index_name` with multi-tenancy enabled if it doesn't exist yet.

        No `properties` are declared on purpose: this component is generic
        across projects, so property names/types are left to Weaviate's
        auto-schema, inferred from whatever gets ingested first.

        Args:
            client (weaviate.Client): Connected Weaviate v3 client.
        """
        if client.schema.exists(self.index_name):
            return
        client.schema.create_class(
            {
                "class": self.index_name,
                "vectorizer": "none",
                "multiTenancyConfig": {"enabled": True},
                "replicationConfig": {"factor": 1},
            }
        )

    def _ensure_tenant(self, client: weaviate.Client) -> None:
        """Registers `tenant` inside `index_name` if it isn't already a tenant there.

        Args:
            client (weaviate.Client): Connected Weaviate v3 client.
        """
        existing = {t.name for t in client.schema.get_class_tenants(self.index_name)}
        if self.tenant in existing:
            return
        client.schema.add_class_tenants(self.index_name, [weaviate.Tenant(name=self.tenant)])

    def _compute_uuids(self, metadatas: list[dict]) -> list[str] | None:
        """Computes deterministic uuid5 ids from `id_key`, if configured.

        Args:
            metadatas (list[dict]): Metadata dict for each document being ingested.

        Returns:
            list[str] | None: One uuid5 string per item, or None if `id_key` is not set.

        Raises:
            ValueError: If `id_key` is set but missing from some item's metadata.
        """
        if not self.id_key:
            return None
        uuids = []
        for metadata in metadatas:
            if self.id_key not in metadata:
                msg = f"Falta el campo '{self.id_key}' en los metadatos de un item a ingerir."
                raise ValueError(msg)
            uuids.append(str(uuid.uuid5(_ID_NAMESPACE, str(metadata[self.id_key]))))
        return uuids

    def _parse_where_filter(self) -> dict | None:
        """Parses `where_filter_json` into a Weaviate where-filter dict.

        Returns:
            dict | None: The parsed filter, or None if the input is empty.

        Raises:
            ValueError: If the input is set but not valid JSON.
        """
        if not self.where_filter_json:
            return None
        try:
            return json.loads(self.where_filter_json)
        except json.JSONDecodeError as exc:
            msg = f"'Filtro (JSON)' no es JSON válido: {exc}"
            raise ValueError(msg) from exc

    @check_cached_vector_store
    def build_vector_store(self) -> Weaviate:
        """Builds the Weaviate vector store and, if `ingest_data` has items, upserts them for `tenant`.

        Returns:
            Weaviate: The LangChain Weaviate wrapper, scoped to `index_name`/`tenant` for
            the search methods called later in the same component run.
        """
        if self.index_name != self.index_name.capitalize():
            msg = f"Weaviate requiere el nombre de colección capitalizado. Usá: {self.index_name.capitalize()}"
            raise ValueError(msg)

        client = self._connect_client()
        if self.auto_provision:
            self._ensure_collection(client)
            self._ensure_tenant(client)

        vector_store = Weaviate(
            client=client,
            index_name=self.index_name,
            text_key=self.text_key,
            embedding=self.embedding,
            by_text=self.search_by_text,
        )

        self.ingest_data = self._prepare_ingest_data()
        documents = []
        for _input in self.ingest_data or []:
            documents.append(_input.to_lc_document() if isinstance(_input, Data) else _input)

        if documents:
            texts = [doc.page_content for doc in documents]
            metadatas = [doc.metadata for doc in documents]
            uuids = self._compute_uuids(metadatas)
            add_kwargs: dict[str, Any] = {"tenant": self.tenant}
            if uuids is not None:
                add_kwargs["uuids"] = uuids
            vector_store.add_texts(texts=texts, metadatas=metadatas, **add_kwargs)

        return vector_store

    def search_documents(self) -> list[Data]:
        """Runs a tenant-scoped similarity search, if `search_query` is set.

        Returns:
            list[Data]: Matching documents, or an empty list if there's no search query.
        """
        vector_store = self.build_vector_store()

        if self.search_query and isinstance(self.search_query, str) and self.search_query.strip():
            search_kwargs: dict[str, Any] = {"tenant": self.tenant}
            where_filter = self._parse_where_filter()
            if where_filter is not None:
                search_kwargs["where_filter"] = where_filter

            docs = vector_store.similarity_search(
                query=self.search_query,
                k=self.number_of_results,
                **search_kwargs,
            )

            data = docs_to_data(docs)
            self.status = data
            return data
        return []
