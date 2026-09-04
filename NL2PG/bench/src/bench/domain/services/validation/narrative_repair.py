"""Servizio di dominio per il ripristino e la sanificazione della prosa narrativa.

Rimuove convenzioni sintattiche del DBMS (snake_case con underscore) dalla prosa naturale
(storie, quesiti e descrizioni dei twist), convertendole in espressioni naturali con spazi,
al fine di eliminare il data leakage e preservare l'integrità dello schema linking.

:author: Riccardo Morabito
"""

from re import compile as re_compile

_RE_URL = re_compile(r"https?://[^\s<>\"'()\[\]{}]+|www\.[^\s<>\"'()\[\]{}]+")
_RE_EMAIL = re_compile(r"\b[a-zA-Z0-9_.+-]+@[a-zA-Z0-9_.-]+\.[a-zA-Z0-9_.-]+\b")
_RE_WORD_OR_SNAKE = re_compile(r"([a-zA-Z0-9\u00C0-\u017F_]+)")


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

    def _sanitize_text(self, text: str, priority_tokens: list[str] | None = None) -> str:
        """Sostituisce prioritariamente i token noti (es. tabelle) e poi i generici snake_case."""
        if not isinstance(text, str) or not text:
            return ""

        placeholders: dict[str, str] = {}
        idx = 0

        def _save_url(m) -> str:
            nonlocal idx
            key = f"__REPAIRURL{idx}REPAIR__"
            placeholders[key] = m.group(0)
            idx += 1
            return key

        def _save_email(m) -> str:
            nonlocal idx
            key = f"__REPAIREMAIL{idx}REPAIR__"
            placeholders[key] = m.group(0)
            idx += 1
            return key

        result = _RE_URL.sub(_save_url, text)
        result = _RE_EMAIL.sub(_save_email, result)

        if priority_tokens:
            for tok in sorted(priority_tokens, key=len, reverse=True):
                if "_" in tok and tok in result:
                    spaced = tok.replace("_", " ")
                    result = result.replace(tok, spaced)

        if "_" in result:
            def _replace_snake(match) -> str:
                token = match.group(1)
                if token.startswith("__REPAIR") and token.endswith("REPAIR__"):
                    return token
                if "_" not in token:
                    return token
                parts = [p for p in token.split("_") if p]
                return " ".join(parts)

            result = _RE_WORD_OR_SNAKE.sub(_replace_snake, result)

        for placeholder, original in placeholders.items():
            result = result.replace(placeholder, original)

        return result
