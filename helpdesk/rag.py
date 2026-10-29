"""Hybrid retriever: dense (nomic-embed-text + ChromaDB) fused with BM25 via reciprocal rank fusion."""
from __future__ import annotations

import json
import re
from functools import lru_cache

import chromadb
from rank_bm25 import BM25Okapi

from . import config
from .ingest import embed

RRF_K = 60
CANDIDATES = 12


def tokenize(text: str) -> list[str]:
    """Lower-case word tokens with a crude plural strip so that 'electives' matches 'elective'."""
    return [t[:-1] if len(t) > 3 and t.endswith("s") and not t.endswith("ss") else t
            for t in re.findall(r"[a-z0-9]+", text.lower())]


class Retriever:
    def __init__(self):
        client = chromadb.PersistentClient(path=str(config.VECTOR_DIR))
        try:
            self.collection = client.get_collection(config.COLLECTION)
        except Exception as exc:
            raise RuntimeError("Vector store not found. Run `python -m helpdesk.ingest` first.") from exc
        with (config.VECTOR_DIR / "chunks.jsonl").open(encoding="utf-8") as f:
            self.chunks = [json.loads(line) for line in f]
        self.by_id = {c["id"]: c for c in self.chunks}
        self.position = {c["id"]: i for i, c in enumerate(self.chunks)}
        self.bm25 = BM25Okapi([tokenize(f"{c['title']} {c['text']}") for c in self.chunks])

    def search(self, query: str, k: int = config.TOP_K) -> list[dict]:
        dense = self.collection.query(query_embeddings=embed([query], kind="query"), n_results=CANDIDATES)
        dense_ids = dense["ids"][0]
        dense_sim = {i: 1 - d for i, d in zip(dense_ids, dense["distances"][0])}

        scores = self.bm25.get_scores(tokenize(query))
        bm25_ids = [self.chunks[i]["id"] for i in sorted(range(len(scores)), key=lambda i: -scores[i])[:CANDIDATES]
                    if scores[i] > 0]

        fused: dict[str, float] = {}
        for ranking in (dense_ids, bm25_ids):
            for rank, cid in enumerate(ranking):
                fused[cid] = fused.get(cid, 0.0) + 1.0 / (RRF_K + rank + 1)

        results, used = [], set()
        for cid in sorted(fused, key=lambda c: -fused[c]):
            if cid in used:
                continue
            c = self.by_id[cid]
            text, used_ids = self.expand(cid)
            used.update(used_ids)
            results.append({**c, "text": text, "similarity": round(dense_sim.get(cid, 0.0), 3),
                            "rrf": round(fused[cid], 4)})
            if len(results) == k:
                break
        return results

    def expand(self, cid: str) -> tuple[str, list[str]]:
        """Append the following chunk of the same page, so that tables and lists cut by
        the chunker are returned whole (small-to-big retrieval)."""
        chunk = self.chunks[self.position[cid]]
        nxt_pos = self.position[cid] + 1
        if nxt_pos >= len(self.chunks):
            return chunk["text"], [cid]
        nxt = self.chunks[nxt_pos]
        if (nxt["source"], nxt["page"]) != (chunk["source"], chunk["page"]):
            return chunk["text"], [cid]
        head = nxt["text"][:60]
        cut = chunk["text"].find(head)
        merged = (chunk["text"][:cut] if cut > 0 else chunk["text"] + " ") + nxt["text"]
        return merged, [cid, nxt["id"]]


@lru_cache(maxsize=1)
def get_retriever() -> Retriever:
    return Retriever()
