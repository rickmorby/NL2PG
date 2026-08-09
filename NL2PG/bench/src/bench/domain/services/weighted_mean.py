"""Funzione pura per calcolare la media pesata dei punteggi critici.

:author: Riccardo Morabito
"""

from bench.domain.models.nlp import CriticScoresDTO


def weighted_mean(scores: CriticScoresDTO, weights: dict) -> float:
    """Calcola la media pesata dei punteggi CriticScoresDTO usando i pesi dati."""
    total_w = sum(weights.values())
    if total_w <= 0:
        return 0.0
    s_dict = scores.model_dump()
    total_s = sum(s_dict.get(key, 0.0) * w for key, w in weights.items())
    return round(total_s / total_w, 2)
