"""Templatematcher using sentence embeddings and FAISS."""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional, Tuple

import faiss
import numpy as np
from sentence_transformers import SentenceTransformer


class TemplateEngine:
    """Lädt Textvorlagen und bietet Ähnlichkeitssuche."""

    def __init__(
        self,
        template_dir: str | Path,
        model: SentenceTransformer | None = None,
        model_name: str = "sentence-transformers/all-MiniLM-L6-v2",
    ) -> None:
        self.template_dir = Path(template_dir)
        self.model = model or SentenceTransformer(model_name)
        self.templates: List[str] = []
        self.index: Optional[faiss.Index] = None
        self.index_path = self.template_dir / "templates.faiss"
        self._load_or_build()

    def _load_or_build(self) -> None:
        paths = sorted(self.template_dir.glob("*.txt"))
        self.templates = [p.read_text(encoding="utf-8").strip() for p in paths]
        if self.index_path.exists():
            self.index = faiss.read_index(str(self.index_path))
            return
        if not self.templates:
            return
        embeddings = np.asarray(self.model.encode(self.templates), dtype="float32")
        faiss.normalize_L2(embeddings)
        dimension = embeddings.shape[1]
        self.index = faiss.IndexFlatIP(dimension)
        self.index.add(embeddings)
        faiss.write_index(self.index, str(self.index_path))

    def query(self, prompt: str, threshold: float = 0.6) -> Tuple[Optional[str], float]:
        """Gibt die ähnlichste Vorlage und den Score zurück."""
        if self.index is None or not self.templates:
            return None, 0.0
        vec = np.asarray(self.model.encode([prompt]), dtype="float32")
        faiss.normalize_L2(vec)
        scores, indices = self.index.search(vec, 1)
        score = float(scores[0][0])
        if score < threshold:
            return None, score
        template = self.templates[int(indices[0][0])]
        return template, score
