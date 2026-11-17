"""The knowledge base: markdown articles, embedded into a ChromaDB vector store."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from pathlib import Path

import chromadb
from chromadb.config import Settings as ChromaSettings
from pydantic import BaseModel

from casewise.gateway import ModelGateway


class Article(BaseModel):
    id: str
    title: str
    body: str


@dataclass(frozen=True)
class Match:
    article: Article
    distance: float
    """Cosine distance to the query: 0 is identical, 1 is unrelated."""


def load_articles(kb_dir: Path) -> list[Article]:
    """Load ``*.md`` articles. The id is the file stem; the title is the first ``# `` line."""
    articles = []
    for path in sorted(Path(kb_dir).glob("*.md")):
        heading, _, body = path.read_text(encoding="utf-8").partition("\n")
        articles.append(
            Article(id=path.stem, title=heading.removeprefix("#").strip(), body=body.strip())
        )
    if not articles:
        raise FileNotFoundError(f"No knowledge-base articles (*.md) found in {kb_dir}")
    return articles


class KnowledgeBase:
    """Articles embedded through the gateway and searchable by cosine distance."""

    def __init__(self, articles: list[Article], gateway: ModelGateway, embedding_model: str):
        self._articles = {article.id: article for article in articles}
        self._gateway = gateway
        self._embedding_model = embedding_model
        client = chromadb.EphemeralClient(ChromaSettings(anonymized_telemetry=False))
        # Ephemeral clients share one in-process store, so every index gets its own name.
        self._collection = client.create_collection(
            name=f"kb-{uuid.uuid4().hex}", metadata={"hnsw:space": "cosine"}
        )
        self._collection.add(
            ids=[article.id for article in articles],
            embeddings=gateway.embed(
                embedding_model, [f"{article.title}\n\n{article.body}" for article in articles]
            ),
        )

    def search(self, query: str, top_k: int = 3) -> list[Match]:
        """Return the closest articles to ``query``, best first."""
        [embedding] = self._gateway.embed(self._embedding_model, [query])
        found = self._collection.query(
            query_embeddings=[embedding], n_results=min(top_k, len(self._articles))
        )
        return [
            Match(article=self._articles[article_id], distance=float(distance))
            for article_id, distance in zip(found["ids"][0], found["distances"][0], strict=True)
        ]
