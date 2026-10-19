"""Tests for Spanish/English detection on LinkedIn message text."""

from jarvis.infrastructure.users.message_language import (
    detect_message_language,
    normalize_reply_language,
    resolve_reply_language,
)


def test_detect_english_recruiter_outreach():
    text = (
        "Hi, I’m Vinita, Founder of DVRS Talent in London. I’m hiring a "
        "Senior Software Engineer for a leading global AI consultancy in Madrid. "
        "Your profile looks like a great fit—open to connecting?\n\n"
        "Thank you for accepting my invitation. Please find the job description "
        "attached for your review. I’d be happy to arrange a call via Teams."
    )
    assert detect_message_language(text) == "English"


def test_detect_spanish_recruiter_outreach():
    text = (
        "Hola Javier, gracias por aceptar mi invitación. Te comparto la "
        "descripción del puesto. ¿Tienes disponibilidad para una llamada "
        "esta semana? Un saludo,"
    )
    assert detect_message_language(text) == "Spanish"


def test_detect_defaults_to_english_when_empty():
    assert detect_message_language("") == "English"
    assert detect_message_language("   ") == "English"


def test_normalize_reply_language_aliases():
    assert normalize_reply_language("en") == "English"
    assert normalize_reply_language("Spanish") == "Spanish"
    assert normalize_reply_language("es") == "Spanish"
    assert normalize_reply_language("  ") is None
    assert normalize_reply_language("french") is None


def test_resolve_reply_language_override_wins():
    spanish_thread = "Hola, gracias por tu interés en el puesto remoto."
    assert (
        resolve_reply_language(spanish_thread, override="English") == "English"
    )
    assert resolve_reply_language("Hello there", override="es") == "Spanish"
