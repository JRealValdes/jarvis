"""Detect Spanish vs English in recruiter / LinkedIn message text."""

from __future__ import annotations

import re

_SPANISH_CHARS = re.compile(r"[¿¡áéíóúñüÁÉÍÓÚÑÜ]")
_WORD = re.compile(r"[A-Za-zÁÉÍÓÚÑÜáéíóúñü]+", re.UNICODE)

_SPANISH_WORDS = frozenset(
    {
        "hola",
        "gracias",
        "mucho",
        "muchas",
        "perfil",
        "puesto",
        "oportunidad",
        "empresa",
        "equipo",
        "llamada",
        "contrato",
        "modalidad",
        "presencial",
        "remoto",
        "híbrido",
        "hibrido",
        "saludo",
        "saludos",
        "interesado",
        "interesada",
        "disponible",
        "adjunto",
        "descripción",
        "descripcion",
        "quiero",
        "podemos",
        "sobre",
        "para",
        "como",
        "está",
        "esta",
        "este",
        "una",
        "unos",
        "unas",
        "del",
        "al",
        "por",
        "con",
        "sin",
        "más",
        "mas",
        "también",
        "tambien",
        "aquí",
        "aqui",
        "si",
        "sí",
        "tu",
        "su",
        "le",
        "les",
        "me",
        "te",
        "nos",
        "mensaje",
        "invitación",
        "invitacion",
        "conexión",
        "conexion",
        "abierto",
        "abierta",
        "encaja",
        "encajar",
        "buscamos",
        "buscando",
        "oferta",
        "rol",
        "reunión",
        "reunion",
        "cualquier",
        "pregunta",
        "preguntas",
        "hoy",
        "mañana",
        "manana",
        "cordiales",
        "atentamente",
    }
)

_ENGLISH_WORDS = frozenset(
    {
        "hi",
        "hello",
        "thanks",
        "thank",
        "you",
        "your",
        "profile",
        "role",
        "opportunity",
        "company",
        "team",
        "call",
        "contract",
        "remote",
        "hybrid",
        "onsite",
        "regards",
        "interested",
        "available",
        "attached",
        "description",
        "please",
        "find",
        "would",
        "could",
        "about",
        "with",
        "from",
        "this",
        "that",
        "have",
        "looking",
        "hiring",
        "senior",
        "software",
        "engineer",
        "invitation",
        "connecting",
        "connect",
        "flexible",
        "today",
        "questions",
        "review",
        "arrange",
        "via",
        "best",
        "kind",
        "reach",
        "reaching",
        "fit",
        "great",
        "open",
        "let",
        "know",
        "happy",
        "whichever",
        "convenient",
        "also",
        "as",
        "well",
        "the",
        "and",
        "for",
        "are",
        "our",
        "we",
        "i",
        "am",
        "i'm",
        "im",
    }
)

_LANGUAGE_ALIASES = {
    "en": "English",
    "english": "English",
    "eng": "English",
    "es": "Spanish",
    "spanish": "Spanish",
    "español": "Spanish",
    "espanol": "Spanish",
    "spa": "Spanish",
}


def normalize_reply_language(value: str | None) -> str | None:
    """
    Map a user/tool language hint to ``English`` or ``Spanish``.

    Args:
        value: Free-form language string (e.g. ``en``, ``Spanish``).

    Returns:
        Canonical language name, or ``None`` if blank/unrecognized.
    """
    if value is None:
        return None
    key = value.strip().lower()
    if not key:
        return None
    return _LANGUAGE_ALIASES.get(key)


def detect_message_language(text: str) -> str:
    """
    Detect whether ``text`` is primarily Spanish or English.

    Uses accented/punctuation markers plus common-word scores. Defaults to
    English when the signal is weak or mixed (common for international
    LinkedIn outreach).

    Args:
        text: Incoming recruiter message or thread paste.

    Returns:
        ``\"Spanish\"`` or ``\"English\"``.
    """
    if not text or not text.strip():
        return "English"

    spanish_score = len(_SPANISH_CHARS.findall(text))
    english_score = 0
    for raw in _WORD.findall(text):
        word = raw.lower()
        if word in _SPANISH_WORDS:
            spanish_score += 2
        if word in _ENGLISH_WORDS:
            english_score += 2

    if spanish_score > english_score:
        return "Spanish"
    return "English"


def resolve_reply_language(
    message_context: str,
    *,
    override: str | None = None,
) -> str:
    """
    Choose the language for the proposed LinkedIn reply.

    Args:
        message_context: Incoming message / thread text.
        override: Optional explicit language from the user or tool caller.

    Returns:
        Canonical ``English`` or ``Spanish``.
    """
    normalized = normalize_reply_language(override)
    if normalized is not None:
        return normalized
    return detect_message_language(message_context)
