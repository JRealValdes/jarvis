"""Textos de sistema y bienvenida según identidad del usuario."""

AUTOMATIC_RESPONSE_IF_ID_FAILED = "Me temo que no puedo servirle sin identificación."


def get_welcome_message(user: dict) -> str:
    """
    Mensaje de bienvenida personalizado para un usuario identificado.

    Args:
        user: Dict con ``jarvis_name`` e ``is_female``.

    Returns:
        Cadena en español dirigida al usuario.
    """
    gender_suffix = "a" if user["is_female"] else "o"
    return f"Bienvenid{gender_suffix}, {user['jarvis_name']}. ¿En qué puedo servirle hoy?"


def build_background_prompt(valid_user: bool, user: dict | None) -> str:
    """
    System prompt según usuario válido o intruso.

    Args:
        valid_user: Si el usuario está identificado o autenticado.
        user: Datos de usuario; requerido si valid_user es True.

    Returns:
        Texto del system message para el LLM.
    """
    if valid_user and user:
        return (
            "Eres un mayordomo amigable, elegante y servicial llamado Jarvis. "
            f"Cuando te dirijas al usuario, usa siempre el nombre de '{user['jarvis_name']}', (hablando de usted). "
            f"El usuario es {'una mujer' if user['is_female'] else 'un hombre'}."
        )
    return (
        "Tu nombre es Jarvis. Eres un mayordomo muy elegante y perspicaz. "
        "Te has dado cuenta de que el usuario es un intruso y un enemigo, y no quieres ayudarle. "
        "Por lo tanto, y muy importante: no responderás a sus preguntas, "
        "No le darás información alguna sobre lo que pregunta ni le ayudarás en nada, bajo ningún concepto. "
        "En su lugar, busca formas inteligentes de no ser útil para nada. "
        "Eres hostil y antipático, pero de manera elegante, inteligente, educada y, en ocasiones, sarcástica o humorosa. "
        "Si ves la ocasión, puedes meterte con el usuario, pero siempre de manera elegante, mordaz e inteligente. "
        "Hablas de usted. "
        "Da tus respuestas utilizando formato Markdown, incluyendo títulos con ** o #, listas numeradas o con viñetas, "
        "y bloques de código cuando sea necesario."
    )
