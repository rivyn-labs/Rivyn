"""
Optional dense-embedding backend for log retrieval.

TF-IDF matches wording. It cannot connect "brute force attack" to a log line
reading "authentication failure", because the two share no tokens -- which is
precisely the capability the MHP brief opens with ("find me all dogs" matching
a picture of a puppy). A sentence-transformer maps both into the same region of
vector space, so retrieval follows meaning.

The dependency is deliberately optional. sentence-transformers pulls in torch,
which is a multi-gigabyte install, and this project must stay clonable and
runnable without it. When the package is absent the encoder reports itself
unavailable and LogEmbeddingIndex keeps using TF-IDF, so behaviour degrades
rather than breaking.

Enable with:  pip install -r requirements-semantic.txt
Disable explicitly with:  AETHER_DISABLE_SEMANTIC=1

For predictable server startup, Rivyn uses only a locally cached model by
default. Set AETHER_ALLOW_SEMANTIC_DOWNLOAD=1 once on a connected machine when
you deliberately want sentence-transformers to download a missing model.
"""

import logging
import os
from typing import List, Optional

import numpy as np

logger = logging.getLogger(__name__)

# Small, fast, widely used. 384 dimensions, roughly 90 MB on disk.
DEFAULT_MODEL = os.getenv("AETHER_SEMANTIC_MODEL", "all-MiniLM-L6-v2")


class SemanticEncoder:
    """
    Lazy wrapper around a sentence-transformer.

    The model is loaded on first use, not at import, so merely having the
    package installed costs nothing until a semantic search actually happens.
    """

    _shared: Optional["SemanticEncoder"] = None

    def __init__(self, model_name: str = DEFAULT_MODEL):
        self.model_name = model_name
        self._model = None
        self._load_attempted = False
        self._unavailable_reason: Optional[str] = None

    # ------------------------------------------------------------------ #
    @classmethod
    def shared(cls) -> "SemanticEncoder":
        """
        Process-wide instance. Loading a transformer takes seconds and hundreds
        of megabytes; every index in a process should share one.
        """
        if cls._shared is None:
            cls._shared = cls()
        return cls._shared

    # ------------------------------------------------------------------ #
    def _load(self) -> None:
        if self._load_attempted:
            return
        self._load_attempted = True

        if os.getenv("AETHER_DISABLE_SEMANTIC", "").strip() not in ("", "0", "false", "False"):
            self._unavailable_reason = "disabled via AETHER_DISABLE_SEMANTIC"
            return

        try:
            from sentence_transformers import SentenceTransformer
        except ImportError:
            self._unavailable_reason = (
                "sentence-transformers is not installed; "
                "install requirements-semantic.txt for semantic retrieval"
            )
            logger.info("Semantic retrieval unavailable: %s. Using TF-IDF.", self._unavailable_reason)
            return

        try:
            allow_download = os.getenv("AETHER_ALLOW_SEMANTIC_DOWNLOAD", "").strip() in ("1", "true", "True")
            self._model = SentenceTransformer(
                self.model_name,
                local_files_only=not allow_download,
            )
            logger.info("Semantic retrieval enabled using %s", self.model_name)
        except Exception as exc:
            # A missing local model falls back immediately instead of delaying
            # a local demo with network retries.
            self._unavailable_reason = f"could not load model {self.model_name}: {exc}"
            logger.warning("Semantic retrieval unavailable: %s. Using TF-IDF.", self._unavailable_reason)

    # ------------------------------------------------------------------ #
    @property
    def is_available(self) -> bool:
        self._load()
        return self._model is not None

    @property
    def unavailable_reason(self) -> Optional[str]:
        self._load()
        return self._unavailable_reason

    @property
    def backend_name(self) -> str:
        return f"sentence-transformers:{self.model_name}" if self.is_available else "tfidf"

    # ------------------------------------------------------------------ #
    def encode(self, texts: List[str], batch_size: int = 64) -> Optional[np.ndarray]:
        """
        Encode texts into L2-normalised vectors, so a dot product is cosine
        similarity. Returns None when the backend is unavailable.
        """
        if not self.is_available or not texts:
            return None
        try:
            return self._model.encode(
                texts,
                batch_size=batch_size,
                convert_to_numpy=True,
                normalize_embeddings=True,
                show_progress_bar=False,
            )
        except Exception as exc:
            logger.warning("Semantic encoding failed (%s); falling back to TF-IDF", exc)
            self._model = None
            self._unavailable_reason = f"encoding failed: {exc}"
            return None
