"""Índice por versión/documento; recuperación por criterio sin perder cobertura."""
from __future__ import annotations

import os
from functools import lru_cache

import numpy as np

CRITERIA = ["moneda subtotal impuestos IGV precio total", "cantidad unidad precio unitario parcial equipos servicios",
            "plazo de entrega instalación condiciones de pago", "vigencia validez de la oferta", "garantía exclusiones alcance",
            "especificaciones técnicas capacidad carga velocidad dimensiones potencia normas certificaciones",
            "contradicciones entre cotización ficha técnica y anexos"]


@lru_cache(maxsize=1)
def model():
    from fastembed import TextEmbedding
    return TextEmbedding(model_name=os.getenv("E3_EMBEDDING_MODEL", "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"),
                         cache_dir=os.getenv("FASTEMBED_CACHE_PATH", "/datos/modelos"), threads=2)


def index_document(document: dict, embedding_model=None) -> list[dict]:
    if not document["uso_rag"]:
        return []
    engine = embedding_model or model()
    fragments = document["fragmentos"]
    vectors = np.asarray(list(engine.embed([x["texto"] for x in fragments])), dtype=float)
    vectors /= np.maximum(np.linalg.norm(vectors, axis=1, keepdims=True), 1e-12)
    queries = np.asarray(list(engine.embed(CRITERIA)), dtype=float)
    queries /= np.maximum(np.linalg.norm(queries, axis=1, keepdims=True), 1e-12)
    for fragment, vector in zip(fragments, vectors):
        fragment["embedding"] = vector.tolist()
    document["modelo_embedding"] = os.getenv("E3_EMBEDDING_MODEL", "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
    retrieved = []
    for criterion, vector in zip(CRITERIA, queries):
        indexes = np.argsort(vectors @ vector)[::-1][:3]
        retrieved.append({"criterio": criterion, "fragmentos": [fragments[int(i)]["id"] for i in indexes]})
    document["consultas_rag"] = retrieved
    return retrieved


def context_batches(documents: list[dict], maximum: int | None = None) -> list[list[dict]]:
    """Prioriza RAG y agrega el resto. Cada fragmento llega al modelo exactamente una vez."""
    maximum = maximum or int(os.getenv("E3_CONTEXT_CHARS", "24000"))
    all_fragments = {x["id"]: x for d in documents for x in d["fragmentos"]}
    selected = list(dict.fromkeys(x for d in documents for q in d.get("consultas_rag", []) for x in q["fragmentos"]))
    selected += [x for x in all_fragments if x not in set(selected)]
    batches, batch, used = [], [], 0
    for key in selected:
        fragment = all_fragments[key]
        if len(fragment["texto"]) > maximum:
            raise ValueError("Una fila supera el contexto máximo; no se recortó silenciosamente.")
        if batch and used + len(fragment["texto"]) > maximum:
            batches.append(batch)
            batch, used = [], 0
        batch.append({k: v for k, v in fragment.items() if k != "embedding"})
        used += len(fragment["texto"])
    if batch:
        batches.append(batch)
    assert {f["id"] for b in batches for f in b} == set(all_fragments)
    return batches
