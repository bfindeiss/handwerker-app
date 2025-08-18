from pathlib import Path

import numpy as np

from app.template_engine import TemplateEngine


class DummyModel:
    """Einfache Keyword-basierte Embeddings für Tests."""

    def encode(self, texts: list[str]) -> np.ndarray:
        vecs = []
        for t in texts:
            t_low = t.lower()
            vecs.append(
                [
                    1.0 if "heizung" in t_low else 0.0,
                    1.0 if "streichen" in t_low else 0.0,
                ]
            )
        return np.array(vecs, dtype="float32")


def test_template_matcher_returns_best_template(tmp_path: Path) -> None:
    (tmp_path / "heizung.txt").write_text("Heizung reparieren")
    (tmp_path / "maler.txt").write_text("Wände streichen")
    engine = TemplateEngine(tmp_path, model=DummyModel())
    template, score = engine.query("Meine Heizung ist kaputt")
    assert template is not None
    assert "Heizung" in template
    assert score > 0.5


def test_template_matcher_low_similarity(tmp_path: Path) -> None:
    (tmp_path / "heizung.txt").write_text("Heizung reparieren")
    engine = TemplateEngine(tmp_path, model=DummyModel())
    template, score = engine.query("Völlig anderes Thema", threshold=0.8)
    assert template is None
    assert score < 0.8
