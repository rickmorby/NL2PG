"""Funzione pura per calcolare la media pesata dei punteggi critici.

:author: Riccardo Morabito
"""

from bench.domain.models.nlp import CriticScoresDTO


def weighted_mean(scores: CriticScoresDTO, weights: dict) -> float:
    """Calcola la media pesata dei punteggi CriticScoresDTO usando i pesi dati."""
    total_w, total_s = 0.0, 0.0
    for key, w in weights.items():
        total_w += w
        total_s += getattr(scores, key, 0.0) * w
    return round(total_s / total_w, 2) if total_w > 0 else 0.0