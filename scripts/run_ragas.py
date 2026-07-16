"""
Module: run_ragas.py
Description: Production-ready RAG system con Langfuse v4, ragas 0.2.x y OpenAI.

Soluciones aplicadas:
  1. Namespace de métricas público para evitar el TypeError.
  2. Aislamiento condicional de ContextPrecision/Recall para evitar el ValueError de 'reference'.
  3. Inyección dinámica de 'embed_query' en Ragas OpenAIEmbeddings para solucionar el AttributeError de Job[1].
"""

import json
import os
import re
import uuid
import warnings
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

# Silenciar advertencias de deprecación internas de librerías de terceros
warnings.filterwarnings("ignore", category=DeprecationWarning)

from openai import OpenAI
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# ── Langfuse v4 ───────────────────────────────────────────────────────
from langfuse import get_client, propagate_attributes

# ── Ragas 0.2.x ──────────────────────────────────────────────────────
from datasets import Dataset
from ragas import evaluate
from ragas.metrics import (
    Faithfulness,
    AnswerRelevancy,
    ContextPrecision,
    ContextRecall,
)
from ragas.llms import llm_factory
from ragas.embeddings import OpenAIEmbeddings

# ─────────────────────────────────────────────────────────────────────
DOCUMENTS = [
    "Ragas are melodic frameworks in Indian classical music.",
    "There are many types of ragas, each with its own mood and time of day.",
    "Ragas are used to evoke specific emotions in the listener.",
    "The performance of a raga involves improvisation within a set structure.",
    "Ragas can be performed on various instruments or sung vocally.",
]


# =====================================================================
# 1. CONFIGURACIÓN DEL ENTORNO
# =====================================================================

class SystemConfig(BaseSettings):
    """Configuración tipada. Soporta LANGFUSE_HOST o LANGFUSE_BASE_URL."""
    model_config = SettingsConfigDict(
        env_file=("../.env", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    openai_api_key: str
    ragas_openai_model: str = "gpt-4o-mini"

    langfuse_public_key: str
    langfuse_secret_key: str
    langfuse_host: Optional[str] = None
    langfuse_base_url: Optional[str] = None

    @property
    def resolved_host(self) -> str:
        host = self.langfuse_host or self.langfuse_base_url or "https://cloud.langfuse.com"
        return host.rstrip("/")


try:
    config = SystemConfig()
except Exception as err:
    print(f"❌ Configuration Error:\n{err}")
    raise SystemExit(1)

os.environ["LANGFUSE_PUBLIC_KEY"] = config.langfuse_public_key
os.environ["LANGFUSE_SECRET_KEY"] = config.langfuse_secret_key
os.environ["LANGFUSE_HOST"] = config.resolved_host
os.environ["OPENAI_API_KEY"] = config.openai_api_key
os.environ["RAGAS_DO_NOT_TRACK"] = "true"

print(f"🔌 Langfuse host: {config.resolved_host}")


# =====================================================================
# 2. MODELOS DE DATOS Y RETRIEVER
# =====================================================================

@dataclass
class TraceEvent:
    event_type: str
    component: str
    data: Dict[str, Any]


class MaskingUtility:
    @staticmethod
    def sanitize(text: str) -> str:
        if not text:
            return text
        return re.sub(r'\b(?:\d[ -]*?){13,16}\b', "[MASKED_CARD_NUMBER]", text)


class BaseRetriever:
    def __init__(self):
        self.documents: List[str] = []

    def fit(self, documents: List[str]):
        self.documents = documents

    def get_top_k(self, query: str, k: int = 3) -> List[tuple]:
        raise NotImplementedError


class SimpleKeywordRetriever(BaseRetriever):
    def _count_keyword_matches(self, query: str, document: str) -> int:
        query_words = query.lower().split()
        doc_words = document.lower().split()
        return sum(1 for w in query_words if w in doc_words)

    def get_top_k(self, query: str, k: int = 3) -> List[tuple]:
        scores = [(i, self._count_keyword_matches(query, doc)) for i, doc in enumerate(self.documents)]
        scores.sort(key=lambda x: x[1], reverse=True)
        return scores[:k]


# =====================================================================
# 3. SISTEMA RAG — Langfuse v4
# =====================================================================

class ExampleRAG:

    def __init__(
        self,
        llm_client: OpenAI,
        retriever: Optional[BaseRetriever] = None,
        system_prompt: Optional[str] = None,
        logdir: str = "logs",
    ):
        self.llm_client = llm_client
        self.langfuse = get_client()
        self.retriever = retriever or SimpleKeywordRetriever()
        self.system_prompt = system_prompt or (
            "Answer the following question based on the provided documents:\n"
            "Question: {query}\n"
            "Documents:\n{context}\n"
            "Answer:\n"
        )
        self.documents: List[str] = []
        self.logdir = logdir
        os.makedirs(self.logdir, exist_ok=True)

    def add_documents(self, documents: List[str]):
        self.documents.extend(documents)
        self.retriever.fit(self.documents)

    def retrieve_documents(self, query: str, top_k: int = 3) -> List[Dict[str, Any]]:
        with self.langfuse.start_as_current_observation(
            as_type="span",
            name="Retrieval",
            input={"query": query, "top_k": top_k},
        ) as span:
            top_docs = self.retriever.get_top_k(query, k=top_k)
            retrieved_docs = [
                {
                    "content": MaskingUtility.sanitize(self.documents[idx]),
                    "similarity_score": score,
                    "document_id": idx,
                }
                for idx, score in top_docs if score > 0
            ]
            span.update(output={"num_retrieved": len(retrieved_docs)})
            return retrieved_docs

    def generate_response(self, query: str, retrieved_docs: List[Dict[str, Any]]) -> str:
        if not retrieved_docs:
            return "I couldn't find any relevant documents to answer your question."

        context = "\n\n".join(
            f"Document {i}:\n{doc['content']}" for i, doc in enumerate(retrieved_docs, 1)
        )
        prompt = self.system_prompt.format(query=query, context=context)

        with self.langfuse.start_as_current_observation(
            as_type="generation",
            name="RAG-LLM-Response",
            model="gpt-4o",
            input=[
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": prompt},
            ],
        ) as gen:
            try:
                response = self.llm_client.chat.completions.create(
                    model="gpt-4o",
                    messages=[
                        {"role": "system", "content": self.system_prompt},
                        {"role": "user", "content": prompt},
                    ],
                    temperature=0.0,
                )
                response_text = MaskingUtility.sanitize(
                    response.choices[0].message.content.strip()
                )
                if response.usage:
                    gen.update(
                        output=response_text,
                        usage={
                            "input": response.usage.prompt_tokens,
                            "output": response.usage.completion_tokens,
                        },
                    )
                return response_text
            except Exception as e:
                gen.update(level="ERROR", status_message=str(e))
                return f"Error generating response: {str(e)}"

    def query(self, question: str, session_id: str, top_k: int = 3) -> Dict[str, Any]:
        run_id = f"run-{uuid.uuid4().hex[:8]}"

        with self.langfuse.start_as_current_observation(
            as_type="span",
            name="RAG_Pipeline_Execution",
            input={"question": question},
        ) as root_span:
            with propagate_attributes(session_id=session_id):
                try:
                    retrieved_docs = self.retrieve_documents(question, top_k=top_k)
                    response = self.generate_response(question, retrieved_docs)

                    result = {"answer": response, "run_id": run_id}
                    root_span.update(output=result)

                    trace_id = self.langfuse.get_current_trace_id()
                    logs_path = self.export_log(run_id, question, result)

                    return {
                        "answer": response,
                        "run_id": run_id,
                        "logs": logs_path,
                        "trace_id": trace_id or run_id,
                        "contexts": [d["content"] for d in retrieved_docs],
                    }

                except Exception as e:
                    root_span.update(level="ERROR", status_message=str(e))
                    logs_path = self.export_log(run_id, question, None)
                    return {
                        "answer": f"Error: {str(e)}",
                        "run_id": run_id,
                        "logs": logs_path,
                        "trace_id": run_id,
                        "contexts": [],
                    }

    def export_log(self, run_id: str, query: str, result: Optional[Dict]) -> str:
        path = os.path.join(self.logdir, f"rag_run_{run_id}.json")
        with open(path, "w") as f:
            json.dump({
                "run_id": run_id,
                "timestamp": datetime.now().isoformat(),
                "query": query,
                "result": result,
            }, f, indent=2)
        return path


# =====================================================================
# 4. EVALUADOR RAGAS — ragas 0.2.x + Langfuse v4
# =====================================================================

class EmbeddedRagasEvaluator:

    def __init__(self, model_name: str):
        self.langfuse = get_client()
        from openai import OpenAI as _OpenAI
        
        shared_client = _OpenAI(api_key=os.environ.get("OPENAI_API_KEY", ""))
        
        self.eval_llm = llm_factory(model=model_name, client=shared_client)
        self.eval_embeddings = OpenAIEmbeddings(model="text-embedding-3-small", client=shared_client)
        
        # ── SOLUCIÓN DEFINITIVA AL ATTRIBUTERROR (embed_query) ────────
        # En Ragas 0.2.x, el objeto nativo usa 'embed_text', pero llamadas internas de AnswerRelevancy 
        # todavía buscan el método heredado 'embed_query'. Inyectamos dinámicamente el puntero.
        if not hasattr(self.eval_embeddings, "embed_query"):
            self.eval_embeddings.embed_query = self.eval_embeddings.embed_text
        # ─────────────────────────────────────────────────────────────

        self.faithfulness_metric = Faithfulness(llm=self.eval_llm)
        self.answer_relevancy_metric = AnswerRelevancy(llm=self.eval_llm, embeddings=self.eval_embeddings)
        self.context_precision_metric = ContextPrecision(llm=self.eval_llm)
        self.context_recall_metric = ContextRecall(llm=self.eval_llm)

    def evaluate_and_publish(
        self,
        question: str,
        answer: str,
        contexts: List[str],
        trace_id: str,
        reference: Optional[str] = None,
    ):
        # Mapeo Múltiple de Columnas para asegurar compatibilidad estructural absoluta
        payload: Dict[str, Any] = {
            "question": question,
            "user_input": question,
            "answer": answer,
            "response": answer,
            "contexts": contexts,
            "retrieved_contexts": contexts,
        }
        
        # Métricas Autónomas (No requieren Ground Truth)
        metrics = [
            self.faithfulness_metric,
            self.answer_relevancy_metric,
        ]
        
        # Métricas Basadas en Referencias (Requieren estrictamente 'reference' en v0.2.x)
        if reference:
            payload["reference"] = reference
            metrics.extend([
                self.context_precision_metric,
                self.context_recall_metric,
            ])
        else:
            print("⚠️ [Ragas] No reference provided. Skipping ContextPrecision and ContextRecall.")

        dataset = Dataset.from_list([payload])

        print(f"🧠 [Ragas] Calculando métricas para trace_id: {trace_id}...")
        results = evaluate(dataset=dataset, metrics=metrics)

        df = results.to_pandas()
        
        exclude_cols = {"question", "user_input", "answer", "response", "contexts", "retrieved_contexts", "reference"}
        metric_cols = [c for c in df.columns if c not in exclude_cols]

        print("📝 [Ragas] Publicando scores a Langfuse...")
        for col in metric_cols:
            try:
                val = float(df[col].iloc[0])
                if val != val:  # Evitar NaN
                    continue
                self.langfuse.create_score(
                    trace_id=trace_id,
                    name=f"ragas_{col}",
                    value=val,
                )
                print(f"   {col}: {val:.4f}")
            except (TypeError, ValueError):
                continue

        self.langfuse.flush()


# =====================================================================
# 5. ENTRYPOINT DE EJECUCIÓN
# =====================================================================

if __name__ == "__main__":
    openai_client = OpenAI(api_key=config.openai_api_key)

    rag_system = ExampleRAG(llm_client=openai_client, logdir="logs")
    rag_system.add_documents(DOCUMENTS)

    eval_session = f"session-rag-eval-{uuid.uuid4().hex[:6]}"
    print(f"🚀 Session: {eval_session}\n")

    test_query = "What types of ragas exist in classical music?"
    print(f"❓ Query: {test_query}")

    output = rag_system.query(test_query, session_id=eval_session, top_k=3)
    print(f"📢 Response: {output['answer']}")
    print(f"🔗 Trace ID: {output['trace_id']}")

    if output["contexts"]:
        evaluator = EmbeddedRagasEvaluator(model_name=config.ragas_openai_model)
        evaluator.evaluate_and_publish(
            question=test_query,
            answer=output["answer"],
            contexts=output["contexts"],
            trace_id=output["trace_id"],
            reference="In Indian classical music, ragas are melodic frameworks that exist in many types, each associated with specific moods, emotions, and times of day."
        )
        print("\n✅ Pipeline y evaluación completados con éxito. Revisa tu consola de Langfuse.")
    else:
        print("\n❌ No se pudo evaluar: sin contextos válidos.")