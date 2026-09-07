"""Servizio di dominio per il ripristino e la sanificazione della prosa narrativa.

Rimuove convenzioni sintattiche del DBMS (snake_case con underscore) dalla prosa naturale
(storie, quesiti e descrizioni dei twist), convertendole in espressioni naturali con spazi,
al fine di eliminare il data leakage e preservare l'integrità dello schema linking.

:author: Riccardo Morabito
"""

from re import Match, compile as re_compile

_RE_URL = re_compile(r"https?://[^\s<>\"'()\[\]{}]+|www\.[^\s<>\"'()\[\]{}]+")
_RE_EMAIL = re_compile(r"\b[a-zA-Z0-9_.+-]+@[a-zA-Z0-9_.-]+\.[a-zA-Z0-9_.-]+\b")
_RE_WORD_OR_SNAKE = re_compile(r"([a-zA-Z0-9\u00C0-\u017F_]+)")


def _replace_snake_token(match: Match[str]) -> str:
    """Sostituisce gli underscore di un token alfanumerico con spazi se non è placeholder."""
    token = match.group(1)
    if token.startswith("__REPAIR") and token.endswith("REPAIR__"):
        return token
    if "_" not in token:
        return token
    parts = [p for p in token.split("_") if p]
    return " ".join(parts)


class NarrativeRepair:
    """Servizio di dominio per la sanificazione della prosa naturale da underscore."""

    def repair_story(self, story: str, priority_tokens: list[str] | None = None) -> str:
        """Sostituisce i riferimenti a tabelle o token snake_case con la forma naturale a spazi."""
        if not story:
            return ""
        return self._sanitize_text(story, priority_tokens)

    def repair_question(self, question: str) -> str:
        """Sostituisce eventuali token snake_case nella domanda utente con la forma a spazi."""
        if not question:
            return ""
        return self._sanitize_text(question)

    def repair_twist_value(self, value: str) -> str:
        """Sanifica i valori obsolete_value delle regole di twist in prosa naturale con spazi."""
        if not value:
            return ""
        return self._sanitize_text(value)

    @staticmethod
    def _protect_masked_entities(text: str) -> tuple[str, dict[str, str]]:
        """Protegge URL ed email sostituendoli con identificatori opachi temporanei."""
        placeholders: dict[str, str] = {}
        idx = 0

        def _save_match(m: Match[str], prefix: str) -> str:
            nonlocal idx
            key = f"__REPAIR{prefix}{idx}REPAIR__"
            placeholders[key] = m.group(0)
            idx += 1
            return key

        result = _RE_URL.sub(lambda m: _save_match(m, "URL"), text)
        result = _RE_EMAIL.sub(lambda m: _save_match(m, "EMAIL"), result)
        return result, placeholders

    @staticmethod
    def _apply_priority_replacements(text: str, tokens: list[str]) -> str:
        """Sostituisce i token prioritari ordinati per lunghezza decrescente."""
        result = text
        for tok in sorted(tokens, key=len, reverse=True):
            if "_" in tok and tok in result:
                spaced = tok.replace("_", " ")
                result = result.replace(tok, spaced)
        return result

    def _sanitize_text(self, text: str, priority_tokens: list[str] | None = None) -> str:
        """Sostituisce prioritariamente i token noti (es. tabelle) e poi i generici snake_case."""
        if not isinstance(text, str) or not text:
            return ""

        result, placeholders = self._protect_masked_entities(text)

        if priority_tokens:
            result = self._apply_priority_replacements(result, priority_tokens)

        if "_" in result:
            result = _RE_WORD_OR_SNAKE.sub(_replace_snake_token, result)

        for placeholder, original in placeholders.items():
            result = result.replace(placeholder, original)

        return result
