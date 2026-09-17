"""Adattatore outbound per il recupero RAG vettoriale tramite Qdrant e FastEmbed.

:author: Riccardo Morabito
"""

from glob import glob
from logging import getLogger
from pathlib import Path
from re import split as re_split
from typing import Any
from uuid import NAMESPACE_DNS, uuid5
from warnings import filterwarnings

filterwarnings("ignore", category=UserWarning)

from fastembed import TextEmbedding  # noqa: E402
from httpx import HTTPError  # noqa: E402
from qdrant_client import QdrantClient  # noqa: E402
from qdrant_client.http.exceptions import (  # noqa: E402
    ResponseHandlingException,
    UnexpectedResponse,
)
from qdrant_client.models import Distance, PointStruct, VectorParams  # noqa: E402

from solver.domain.ports.outbound.rag_port import DocRAGPort  # noqa: E402

_log = getLogger("solver.adapters.rag")
_MIN_SECTION_LEN = 30
_MAX_CHUNK_LEN = 1200
_BATCH_SIZE = 64
_MODEL_ALIASES = {
    "microsoft/harrier-oss-v1-0.6b": "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
}


class DocRAGAdapter(DocRAGPort):
    """Adattatore per la ricerca semantica vettoriale su Qdrant con modello multilingua."""

    def __init__(
        self,
        qdrant_url: str = "http://127.0.0.1:6333",
        collection_name: str = "doc_knowledge",
        embedding_model: str = "microsoft/harrier-oss-v1-0.6b",
        rag_dir: Path | None = None,
        docs_dir: Path | None = None,
    ) -> None:
        """Inizializza la connessione a Qdrant, il modello di embedding e l'indice."""
        self._url = qdrant_url
        self._collection_name = collection_name
        self._model_name = embedding_model
        self._root = rag_dir or docs_dir or Path("./rag")

        self._client = QdrantClient(url=self._url, timeout=10.0)
        actual_model = _MODEL_ALIASES.get(self._model_name, self._model_name)
        self._embedder = TextEmbedding(model_name=actual_model)
        self._dim = self._get_embedding_dimension()

        self._ensure_collection_and_index()

    def search_documentation(self, query: str, top_k: int = 3) -> str:
        """Esegue la ricerca semantica densa su Qdrant per la query fornita."""
        if not query or not query.strip():
            return "Query vuota."

        try:
            query_vectors = list(self._embedder.embed([query.strip()]))
            if not query_vectors:
                return "Impossibile calcolare il vettore per la query."

            q_vec = query_vectors[0].tolist()
            search_res = self._client.query_points(
                collection_name=self._collection_name,
                query=q_vec,
                limit=top_k,
            )

            hits = search_res.points
            if not hits:
                return "Nessun risultato rilevante trovato nella documentazione aziendale."

            results_str = []
            for rank, hit in enumerate(hits, 1):
                payload = hit.payload or {}
                source = payload.get("source", "documentazione")
                content = payload.get("content", "")
                score = hit.score or 0.0
                results_str.append(
                    f"--- DOCUMENTO #{rank} (Fonte: {source}, Attinenza: {score:.3f}) ---\n"
                    f"{content}"
                )

            return "\n\n".join(results_str)
        except (
            HTTPError,
            UnexpectedResponse,
            ResponseHandlingException,
            OSError,
            ValueError,
            RuntimeError,
        ) as e:
            _log.warning("Errore durante la ricerca vettoriale su Qdrant: %s", e)
            return f"Errore recupero documentazione: {e}"

    def is_healthy(self) -> bool:
        """Verifica che il database Qdrant sia raggiungibile e la collezione pronta."""
        try:
            return self._client.collection_exists(self._collection_name)
        except (HTTPError, UnexpectedResponse, ResponseHandlingException, OSError, RuntimeError):
            return False

    def indexed_chunks_count(self) -> int:
        """Restituisce il numero totale di chunk vettoriali indicizzati nella collezione."""
        try:
            if not self._client.collection_exists(self._collection_name):
                return 0
            info = self._client.get_collection(self._collection_name)
            return info.points_count or 0
        except (HTTPError, UnexpectedResponse, ResponseHandlingException, OSError, RuntimeError):
            return 0

    def _get_embedding_dimension(self) -> int:
        """Calcola la dimensione del vettore restituito dal modello di embedding."""
        sample = next(iter(self._embedder.embed(["probe"])))
        return len(sample)

    def _ensure_collection_and_index(self) -> None:
        """Crea la collezione se assente e sincronizza i file markdown."""
        try:
            if not self._client.collection_exists(self._collection_name):
                _log.info(
                    "Creazione collezione Qdrant '%s' (dim: %d, distance: Cosine)...",
                    self._collection_name,
                    self._dim,
                )
                self._client.create_collection(
                    collection_name=self._collection_name,
                    vectors_config=VectorParams(size=self._dim, distance=Distance.COSINE),
                )

            self._index_all_markdown_files()
        except (
            HTTPError,
            UnexpectedResponse,
            ResponseHandlingException,
            OSError,
            ValueError,
            RuntimeError,
        ) as e:
            _log.warning("Inizializzazione indice Qdrant non riuscita: %s", e)

    def _index_all_markdown_files(self) -> None:
        """Scansiona i file markdown ed esegue l'upsert vettoriale incrementale."""
        if not self._root.exists():
            _log.warning("Cartella documentazione RAG non trovata in %s.", self._root)
            return

        pattern = str(self._root / "**/*.md")
        files = [f for f in glob(pattern, recursive=True) if ".venv" not in f and ".git" not in f]
        chunks: list[dict[str, Any]] = []

        for fpath in sorted(files):
            try:
                content = Path(fpath).read_text(encoding="utf-8")
                rel_path = str(Path(fpath).relative_to(self._root))
                raw_sections = [
                    s.strip()
                    for s in re_split(r"\n(?=#{2,3}\s)", content)
                    if len(s.strip()) > _MIN_SECTION_LEN
                ]
                for sec_idx, s in enumerate(raw_sections):
                    sub_chunks = self._chunk_text(s, _MAX_CHUNK_LEN)
                    for sub_idx, chunk_text in enumerate(sub_chunks):
                        doc_id = str(uuid5(NAMESPACE_DNS, f"{rel_path}:{sec_idx}:{sub_idx}"))
                        chunks.append(
                            {
                                "id": doc_id,
                                "source": rel_path,
                                "content": chunk_text,
                            }
                        )
            except (OSError, UnicodeDecodeError, ValueError) as e:
                _log.warning("Impossibile leggere %s: %s", fpath, e)

        if not chunks:
            return

        current_count = self.indexed_chunks_count()
        if current_count >= len(chunks):
            _log.info(
                "Collezione '%s' allineata con %d vettori.",
                self._collection_name,
                current_count,
            )
            return

        start_from = max(0, current_count - (current_count % _BATCH_SIZE))
        _log.info(
            "Completamento indicizzazione Qdrant da chunk %d a %d...",
            start_from,
            len(chunks),
        )

        for start_idx in range(start_from, len(chunks), _BATCH_SIZE):
            batch = chunks[start_idx : start_idx + _BATCH_SIZE]
            texts = [c["content"] for c in batch]
            vectors = list(self._embedder.embed(texts))

            points = [
                PointStruct(
                    id=c["id"],
                    vector=vec.tolist(),
                    payload={"content": c["content"], "source": c["source"]},
                )
                for c, vec in zip(batch, vectors, strict=True)
            ]
            self._client.upsert(collection_name=self._collection_name, points=points)

        _log.info(
            "Indicizzazione completata con successo: %d chunk in '%s'.",
            len(chunks),
            self._collection_name,
        )

    @staticmethod
    def _chunk_text(text: str, max_len: int) -> list[str]:
        """Spezza il testo in blocchi di dimensione massima rispettando i paragrafi."""
        if len(text) <= max_len:
            return [text]
        paragraphs = text.split("\n\n")
        chunks = []
        buf = ""
        for p in paragraphs:
            if len(buf) + len(p) <= max_len:
                buf = f"{buf}\n\n{p}" if buf else p
            else:
                if buf:
                    chunks.append(buf)
                buf = p[:max_len]
        if buf:
            chunks.append(buf)
        return chunks
