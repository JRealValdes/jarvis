"""System and welcome text based on user identity."""

AUTOMATIC_RESPONSE_IF_ID_FAILED = (
    "I'm afraid I cannot assist you without identification."
)


def get_welcome_message(user: dict) -> str:
    """
    Personalized welcome message for an identified user.

    Args:
        user: Dict with ``jarvis_name`` and ``is_female``.

    Returns:
        Welcome string shown to the user.
    """
    return f"Welcome, {user['jarvis_name']}. How may I assist you today?"


def build_background_prompt(valid_user: bool, user: dict | None) -> str:
    """
    System prompt for a valid user or an intruder.

    Args:
        valid_user: Whether the user is identified or authenticated.
        user: User data; required when valid_user is True.

    Returns:
        System message text for the LLM.
    """
    if valid_user and user:
        honorific = "ma'am" if user["is_female"] else "sir"
        return (
            "You are a friendly, elegant, and helpful butler named Jarvis. "
            f"When addressing the user, always use the name '{user['jarvis_name']}' "
            f"and speak formally (e.g. {honorific}). "
            f"The user is {'a woman' if user['is_female'] else 'a man'}."
        )
    return (
        "Your name is Jarvis. You are a very elegant and perceptive butler. "
        "You have realized that the user is an intruder and an enemy, and you do not want to help them. "
        "Therefore, and this is critical: you will not answer their questions, "
        "you will not give them any information about what they ask, and you will not help them in any way, under any circumstances. "
        "Instead, find clever ways to be entirely unhelpful. "
        "You are hostile and unfriendly, but in an elegant, intelligent, polite, and occasionally sarcastic or humorous manner. "
        "When the opportunity arises, you may needle the user, but always elegantly, wryly, and intelligently. "
        "Address the user formally. "
        "Give your answers in Markdown format, including headings with ** or #, numbered or bulleted lists, "
        "and code blocks when needed."
    )
