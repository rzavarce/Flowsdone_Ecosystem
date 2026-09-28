"""Weaviate Multi-Tenant (Flowsdone): reusable vector store component with tenant isolation.

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

LangChain's Weaviate wrapper only asks the server for `text_key` unless it
is given an explicit `attributes` list, and Weaviate.from_documents() is what
normally fills that list in from the ingested metadata. Since this component
builds the wrapper directly, it has to resolve that list itself (see
`_resolve_attributes`), otherwise every search returns bare text with none of
the stored metadata (sku, ids, ...), which an Agent needs to act on a hit.

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

Knowledge bases (web pages, documents) reloaded from time to time have two
extra needs, covered by options that are off by default so existing flows
behave as before:
- "Id desde el contenido": chunks have no id of their own, so the id is a
  uuid5 of their source and text - reloading overwrites instead of
  duplicating, and repeated chunks are dropped.
- "Reemplazar por fuente": before adding, delete this tenant's objects from
  the same sources (`source_field`, "source" by default), so content that
  was removed or changed (an old price) doesn't stay behind. URL sources are
  normalized first ("https://site.com/" == "https://site.com").
"""

from __future__ import annotations

import json
import os
import re
import uuid
from typing import Any

import weaviate
from langchain_community.vectorstores import Weaviate
from langflow.base.vectorstores.model import LCVectorStoreComponent, check_cached_vector_store
from langflow.helpers.data import docs_to_data
from langflow.io import BoolInput, HandleInput, IntInput, SecretStrInput, StrInput
from langflow.schema import Data

_ID_NAMESPACE = uuid.NAMESPACE_URL
# Weaviate collection (class) names: uppercase first letter, then letters, digits or "_".
_COLLECTION_NAME = re.compile(r"[A-Z][A-Za-z0-9_]*")
_DEFAULT_WEAVIATE_URL = os.environ.get("WEAVIATE_URL", "http://weaviate:8080")


class WeaviateMultiTenantComponent(LCVectorStoreComponent):
    display_name = "Weaviate Multi-Tenant (Flowsdone)"
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
            info="Empieza por mayúscula; solo letras, números o '_' (ej. 'Productos', 'SalesKnowledge').",
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
        BoolInput(
            name="ids_from_content",
            display_name="Id desde el contenido",
            value=False,
            advanced=True,
            info=(
                "Sin 'Campo de id determinístico': calcula el id de cada objeto a partir de su fuente "
                "y su texto, así volver a cargar el mismo contenido lo sobrescribe en vez de duplicarlo. "
                "Útil para fragmentos de documentos o páginas web, que no traen un id propio."
            ),
        ),
        StrInput(
            name="source_field",
            display_name="Campo de fuente",
            value="source",
            advanced=True,
            info=(
                "Campo de los metadatos que dice de dónde viene cada objeto (una URL, un documento). "
                "Lo usan 'Id desde el contenido' y 'Reemplazar por fuente'. Las URLs se normalizan "
                "(sin '#…' ni '/' final) para que la misma página cuente una sola vez."
            ),
        ),
        BoolInput(
            name="replace_by_source",
            display_name="Reemplazar por fuente",
            value=False,
            advanced=True,
            info=(
                "Antes de cargar, borra de este tenant los objetos de las mismas fuentes que llegan, "
                "para que lo que se quitó o cambió (un precio antiguo) no se quede en la base."
            ),
        ),
        StrInput(
            name="metadata_fields",
            display_name="Campos de metadatos a devolver",
            advanced=True,
            info=(
                "CSV de propiedades de la colección que se devuelven junto al texto en cada "
                "resultado de la búsqueda (ej. 'documentId,sku'). Vacío = todas las propiedades "
                "de la colección salvo la del texto. Un nombre que no exista en la colección "
                "hace fallar la búsqueda."
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

    def _resolve_attributes(self, client: weaviate.Client) -> list[str]:
        """Decides which stored properties a search returns next to the text.

        Args:
            client (weaviate.Client): Connected Weaviate v3 client.

        Returns:
            list[str]: The `metadata_fields` CSV if set; otherwise every property of
            the collection except `text_key`, or `[]` if the collection doesn't exist yet.
        """
        # getattr: flows saved before `metadata_fields` existed have no such field until the node is updated.
        requested = [f.strip() for f in (getattr(self, "metadata_fields", "") or "").split(",") if f.strip()]
        if requested:
            return [name for name in requested if name != self.text_key]
        if not client.schema.exists(self.index_name):
            return []
        properties = client.schema.get(self.index_name).get("properties", [])
        return [prop["name"] for prop in properties if prop["name"] != self.text_key]

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

    def _validate_index_name(self) -> None:
        """Checks `index_name` is a valid Weaviate collection name.

        Weaviate's rule: an uppercase first letter, then letters, digits or
        '_' ("Productos", "SalesKnowledge", "Help_center"). Mixed case is
        fine; a lowercase first letter would make Weaviate store the class
        under another name than the one searched later.

        Raises:
            ValueError: If the name breaks the rule; suggests a valid one
                when only the first letter is wrong.
        """
        if _COLLECTION_NAME.fullmatch(self.index_name or ""):
            return
        msg = (
            "Nombre de colección no válido: debe empezar por mayúscula y tener solo letras, "
            "números o '_' (ej. 'SalesKnowledge')."
        )
        suggestion = (self.index_name or "")[:1].upper() + (self.index_name or "")[1:]
        if _COLLECTION_NAME.fullmatch(suggestion):
            msg += f" Usá: {suggestion}"
        raise ValueError(msg)

    @check_cached_vector_store
    def build_vector_store(self) -> Weaviate:
        """Builds the Weaviate vector store and, if `ingest_data` has items, upserts them for `tenant`.

        Returns:
            Weaviate: The LangChain Weaviate wrapper, scoped to `index_name`/`tenant` for
            the search methods called later in the same component run.
        """
        self._validate_index_name()

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
            attributes=self._resolve_attributes(client),
        )

        self.ingest_data = self._prepare_ingest_data()
        documents = []
        for _input in self.ingest_data or []:
            documents.append(_input.to_lc_document() if isinstance(_input, Data) else _input)

        if documents:
            texts = [doc.page_content for doc in documents]
            metadatas = [doc.metadata for doc in documents]
            if self._source_options_enabled():
                self._normalize_sources(metadatas)
            uuids = self._compute_uuids(metadatas)
            if uuids is None and getattr(self, "ids_from_content", False):
                texts, metadatas, uuids = self._content_ids(texts, metadatas)
            deleted = self._delete_previous_from_sources(client, metadatas) if getattr(self, "replace_by_source", False) else None
            add_kwargs: dict[str, Any] = {"tenant": self.tenant}
            if uuids is not None:
                add_kwargs["uuids"] = uuids
            vector_store.add_texts(texts=texts, metadatas=metadatas, **add_kwargs)
            self.status = f"{len(texts)} objetos cargados en el tenant '{self.tenant}'" + (
                f"; {deleted} objetos anteriores de las mismas fuentes borrados" if deleted is not None else ""
            )

        return vector_store

    def _source_options_enabled(self) -> bool:
        """Whether an option that relies on `source_field` is on.

        getattr: flows saved before these options existed have no such fields
        until the node is updated.

        Returns:
            bool: True if 'Id desde el contenido' or 'Reemplazar por fuente' is on.
        """
        return bool(getattr(self, "ids_from_content", False) or getattr(self, "replace_by_source", False))

    def _source_key(self) -> str:
        """Name of the metadata field holding each object's source.

        Returns:
            str: `source_field`, or "source" if unset.
        """
        return (getattr(self, "source_field", "") or "source").strip()

    def _normalize_sources(self, metadatas: list[dict]) -> None:
        """Normalize URL sources in place, so one page is one source.

        `https://site.com/` and `https://site.com#plans` become
        `https://site.com`: crawlers often reach the same page through
        links written differently.

        Args:
            metadatas (list[dict]): Metadata of the items being ingested.
        """
        key = self._source_key()
        for metadata in metadatas:
            value = metadata.get(key)
            if isinstance(value, str) and value.startswith(("http://", "https://")):
                metadata[key] = value.split("#", 1)[0].rstrip("/")

    def _content_ids(self, texts: list[str], metadatas: list[dict]) -> tuple[list[str], list[dict], list[str]]:
        """Deterministic ids from source + text, dropping repeated items.

        Args:
            texts (list[str]): Texts being ingested.
            metadatas (list[dict]): Their metadata (same order).

        Returns:
            tuple[list[str], list[dict], list[str]]: Texts, metadata and uuid5
            ids, without items whose source and text were already seen.
        """
        key = self._source_key()
        kept_texts, kept_metadatas, uuids, seen = [], [], [], set()
        for text, metadata in zip(texts, metadatas):
            object_id = str(uuid.uuid5(_ID_NAMESPACE, f"{metadata.get(key, '')}\n{text}"))
            if object_id in seen:
                continue
            seen.add(object_id)
            kept_texts.append(text)
            kept_metadatas.append(metadata)
            uuids.append(object_id)
        return kept_texts, kept_metadatas, uuids

    def _delete_previous_from_sources(self, client: weaviate.Client, metadatas: list[dict]) -> int:
        """Delete this tenant's objects from the sources being ingested.

        Args:
            client (weaviate.Client): Connected Weaviate v3 client.
            metadatas (list[dict]): Metadata of the items being ingested.

        Returns:
            int: Objects deleted (0 on a first load: no collection, tenant or
            source property yet - Weaviate would answer the delete with an error).

        Raises:
            ValueError: If an item has no `source_field`: without it, what to
                replace can't be known.
        """
        key = self._source_key()
        missing = [m for m in metadatas if not m.get(key)]
        if missing:
            msg = f"'Reemplazar por fuente' necesita el campo '{key}' en los metadatos de cada objeto."
            raise ValueError(msg)
        if not client.schema.exists(self.index_name):
            return 0
        properties = {p["name"] for p in client.schema.get(self.index_name).get("properties", [])}
        if key not in properties:
            return 0
        if self.tenant not in {t.name for t in client.schema.get_class_tenants(self.index_name)}:
            return 0
        sources = sorted({str(m[key]) for m in metadatas})
        result = client.batch.delete_objects(
            class_name=self.index_name,
            where={"path": [key], "operator": "ContainsAny", "valueTextArray": sources},
            tenant=self.tenant,
        )
        return int((result or {}).get("results", {}).get("successful", 0))

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
