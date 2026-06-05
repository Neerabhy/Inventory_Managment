"""
ml/sentiment.py — Model 8: Review Sentiment Engine using VADER with DistilBERT upgrade path.
"""
from __future__ import annotations
from typing import Any, Dict
from loguru import logger
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

from .base import BaseMLModel

try:
    from transformers import pipeline
except ImportError:
    pipeline = None  # type: ignore[assignment]


class SentimentAnalyzer(BaseMLModel):
    """
    Sentiment analysis engine for product reviews.
    Primary: DistilBERT transformer (HuggingFace pipeline) for high accuracy.
    Fallback: VADER lexicon-based model for low-latency rule scoring.

    Returns polarity scores suitable for product management dashboards.
    """

    model_name = "SentimentAnalyzer"
    model_version = "1.0.0"

    def predict(self, text: str = "", **kwargs: Any) -> Dict[str, Any]:
        """
        Analyze sentiment of a review text.

        Args:
            text: Raw customer review string.

        Returns:
            Dict with:
              - sentiment_score: float -1.0 (negative) to +1.0 (positive)
              - sentiment_label: POSITIVE | NEUTRAL | NEGATIVE
              - model_used: str
              - compound: float (VADER compound score)
              - confidence: float
        """
        if not text or not text.strip():
            return {**self._fallback_response("Empty review text"),
                    "sentiment_score": 0.0, "sentiment_label": "NEUTRAL",
                    "model_used": "none", "compound": 0.0, "confidence": 0.0}

        try:
            return self._distilbert_predict(text)
        except Exception as exc:
            logger.warning(f"DistilBERT sentiment failed: {exc}. Using VADER.")
            return self._vader_predict(text)

    def _distilbert_predict(self, text: str) -> Dict[str, Any]:
        """
        HuggingFace DistilBERT sentiment pipeline.
        Model: distilbert-base-uncased-finetuned-sst-2-english
        Raises ImportError if transformers not installed — triggers VADER fallback.
        """
        if pipeline is None:
            raise ImportError("transformers is not installed")

        classifier = pipeline(
            "sentiment-analysis",
            model="distilbert-base-uncased-finetuned-sst-2-english",
            truncation=True,
            max_length=512,
        )
        result = classifier(text[:512])[0]
        label = result["label"]       # "POSITIVE" | "NEGATIVE"
        confidence = result["score"]

        score = confidence if label == "POSITIVE" else -confidence
        normalized = (score + 1) / 2  # Map -1..1 → 0..1 for the compound proxy

        return {
            "sentiment_score": round(score, 4),
            "sentiment_label": label,
            "model_used": "distilbert",
            "compound": round(normalized, 4),
            "confidence": round(confidence, 4),
            "fallback": False,
        }

    def _vader_predict(self, text: str) -> Dict[str, Any]:
        """
        VADER lexicon-based sentiment analysis.
        Fast, no GPU required, suitable for production fallback.
        """
        analyzer = SentimentIntensityAnalyzer()
        scores = analyzer.polarity_scores(text)
        compound = scores["compound"]

        if compound >= 0.05:
            label = "POSITIVE"
        elif compound <= -0.05:
            label = "NEGATIVE"
        else:
            label = "NEUTRAL"

        return {
            "sentiment_score": round(compound, 4),
            "sentiment_label": label,
            "model_used": "vader",
            "compound": round(compound, 4),
            "confidence": round(abs(compound), 4),
            "fallback": True,
            "vader_detail": {
                "pos": scores["pos"],
                "neu": scores["neu"],
                "neg": scores["neg"],
            },
        }
