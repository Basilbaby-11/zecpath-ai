"""Semantic resume-to-job matching using sentence embeddings and cosine similarity.

The model is loaded lazily. Tests can inject an encoder implementing encode(texts).
Scores are similarity signals, not calibrated hiring probabilities.
"""
from __future__ import annotations

from typing import Any, Protocol
import numpy as np

ENGINE_VERSION = "1.0.0"
DEFAULT_MODEL = "sentence-transformers/all-MiniLM-L6-v2"


class Encoder(Protocol):
    def encode(self, sentences: list[str], **kwargs: Any) -> Any: ...


class SentenceTransformerEncoder:
    """Lazy adapter around Sentence Transformers; downloads model on first use."""
    def __init__(self, model_name: str = DEFAULT_MODEL) -> None:
        self.model_name = model_name
        self._model = None

    def encode(self, sentences: list[str], **kwargs: Any) -> Any:
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
            except ImportError as exc:
                raise ImportError(
                    "Semantic matching requires sentence-transformers. Install with: "
                    "python -m pip install sentence-transformers"
                ) from exc
            self._model = SentenceTransformer(self.model_name)
        return self._model.encode(sentences, convert_to_numpy=True, normalize_embeddings=True)


def _text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, dict):
        return " ".join(part for part in (_text(v) for v in value.values()) if part)
    if isinstance(value, (list, tuple, set)):
        return " ".join(part for part in (_text(v) for v in value) if part)
    return str(value).strip()


def _cosine(left: Any, right: Any) -> float:
    a = np.asarray(left, dtype=float).reshape(-1)
    b = np.asarray(right, dtype=float).reshape(-1)
    if a.size == 0 or b.size == 0 or a.size != b.size:
        raise ValueError("Embedding vectors must be non-empty and have equal dimensions")
    denominator = float(np.linalg.norm(a) * np.linalg.norm(b))
    if denominator == 0:
        return 0.0
    # Convert cosine from [-1, 1] to [0, 1] for an intuitive normalized score.
    return round(max(0.0, min(1.0, (float(np.dot(a, b)) / denominator + 1.0) / 2.0)), 4)


class SemanticMatchingEngine:
    """Compare skills, experience summaries, projects, and overall resume/JD text.

    Thresholds apply to normalized cosine similarity in [0, 1]. They are
    configurable defaults, not universal or empirically calibrated cutoffs.
    """
    def __init__(self, encoder: Encoder | None = None,
                 strong_threshold: float = 0.75,
                 moderate_threshold: float = 0.55) -> None:
        if not 0 <= moderate_threshold <= strong_threshold <= 1:
            raise ValueError("Thresholds must satisfy 0 <= moderate <= strong <= 1")
        self.encoder = encoder or SentenceTransformerEncoder()
        self.strong_threshold = strong_threshold
        self.moderate_threshold = moderate_threshold

    def _embed(self, texts: list[str]) -> list[Any]:
        vectors = self.encoder.encode(texts)
        array = np.asarray(vectors, dtype=float)
        if array.ndim == 1 and len(texts) == 1:
            array = array.reshape(1, -1)
        if array.ndim != 2 or array.shape[0] != len(texts):
            raise ValueError("Encoder must return one embedding vector per input text")
        return [array[i] for i in range(len(texts))]

    def _score_pair(self, resume_text: Any, job_text: Any) -> dict[str, Any]:
        resume, job = _text(resume_text), _text(job_text)
        if not resume or not job:
            return {"score": 0.0, "status": "insufficient_data"}
        left, right = self._embed([resume, job])
        score = _cosine(left, right)
        category = ("strong" if score >= self.strong_threshold else
                    "moderate" if score >= self.moderate_threshold else "weak")
        return {"score": score, "category": category, "status": "scored"}

    
    def compare(self, resume: dict[str, Any], job_description: dict[str, Any],
                resume_id: str | None = None, job_id: str | None = None) -> dict[str, Any]:
        """Return section-level and overall semantic scores using one batch."""

        resume_skills = resume.get(
            "skills", resume.get("technical_skills", [])
        )
        job_skills = job_description.get(
            "required_skills", job_description.get("skills", [])
        )

        resume_experience = resume.get(
            "experience_summary", resume.get("experience", [])
        )
        job_experience = job_description.get(
            "experience_summary", job_description.get("responsibilities", [])
        )

        resume_projects = resume.get(
            "project_descriptions", resume.get("projects", [])
        )
        job_projects = job_description.get(
            "project_descriptions", job_description.get("relevant_projects", [])
        )

        resume_overall = " ".join(
            part for part in [
                _text(resume.get("professional_summary", "")),
                _text(resume_skills),
                _text(resume_experience),
                _text(resume_projects),
            ] if part
        )

        job_overall = " ".join(
            part for part in [
                _text(job_description.get("title", job_description.get("role", ""))),
                _text(job_description.get("description", "")),
                _text(job_skills),
                _text(job_experience),
                _text(job_projects),
            ] if part
        )

        section_inputs = {
            "skills": (resume_skills, job_skills),
            "experience": (resume_experience, job_experience),
            "projects": (resume_projects, job_projects),
            "overall": (resume_overall, job_overall),
        }

        section_scores: dict[str, dict[str, Any]] = {}
        batch_texts: list[str] = []
        batch_names: list[str] = []

        # Collect all valid pairs before calling the encoder.
        for name, (resume_part, job_part) in section_inputs.items():
            resume_text = _text(resume_part)
            job_text = _text(job_part)

            if not resume_text or not job_text:
                section_scores[name] = {
                    "score": 0.0,
                    "status": "insufficient_data",
                }
                continue

            batch_names.append(name)
            batch_texts.extend([resume_text, job_text])

        # Encode every valid section pair in one call.
        if batch_texts:
            vectors = self._embed(batch_texts)

            for index, name in enumerate(batch_names):
                score = _cosine(
                    vectors[index * 2],
                    vectors[index * 2 + 1],
                )

                category = (
                    "strong"
                    if score >= self.strong_threshold
                    else "moderate"
                    if score >= self.moderate_threshold
                    else "weak"
                )

                section_scores[name] = {
                    "score": score,
                    "category": category,
                    "status": "scored",
                }

        available = [
            result["score"]
            for result in section_scores.values()
            if result["status"] == "scored"
        ]

        overall = (
            round(sum(available) / len(available), 4)
            if available else 0.0
        )

        if not available:
            overall_category = "insufficient_data"
        elif overall >= self.strong_threshold:
            overall_category = "strong"
        elif overall >= self.moderate_threshold:
            overall_category = "moderate"
        else:
            overall_category = "weak"

        return {
            "engine_version": ENGINE_VERSION,
            "resume_id": (
                resume_id
                or resume.get("resume_id")
                or resume.get("candidate_id")
            ),
            "job_id": (
                job_id
                or job_description.get("job_id")
                or job_description.get("jd_id")
            ),
            "method": "sentence_transformer_embeddings_cosine_similarity",
            "similarity_scores": section_scores,
            "overall_score": overall,
            "overall_category": overall_category,
            "thresholds": {
                "moderate": self.moderate_threshold,
                "strong": self.strong_threshold,
            },
            "disclaimer": (
                "Similarity is a ranking signal, not a hiring probability "
                "or sole hiring criterion."
            ),
        }
