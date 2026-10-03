"""
Temporary live smoke test for gpt-4o-mini (real OpenAI call).

Not part of pytest. Requires OPENAI_API_KEY in the environment or .env.

    uv run python scripts/smoke_gpt_4o_mini.py

Delete this file after verifying the model works.
"""

from __future__ import annotations

from dotenv import load_dotenv

load_dotenv()

from langchain_core.messages import HumanMessage

from jarvis.agents.factory import build_agent
from jarvis.agents.session import ask_jarvis, reset_cache
from jarvis.core.enums import ModelEnum
from jarvis.core.openai_models import resolve_openai_chat_model_id


def main() -> None:
    model = ModelEnum.GPT_4O_MINI
    model_id = resolve_openai_chat_model_id(model)
    print(f"Building agent for {model.name} ({model_id})...")

    agent = build_agent(model)
    print(f"Agent type: {type(agent).__name__}")

    print("Direct graph invoke (short prompt)...")
    result = agent.invoke(
        input={
            "messages": [HumanMessage(content="Reply with exactly: OK")],
            "real_name": "smoke",
        },
        config={"configurable": {"thread_id": "smoke-gpt-4o-mini"}},
    )
    last = result["messages"][-1]
    print(f"Direct reply: {getattr(last, 'content', last)!r}")

    print("ask_jarvis path (with authenticated stub user)...")
    reset_cache()
    user_info = {
        "real_name": "SmokeTest",
        "jarvis_name": "sir",
        "is_female": False,
        "admin": False,
    }
    welcome = ask_jarvis(
        "ignored on welcome turn",
        model=model,
        thread_id="smoke-user",
        user_info=user_info,
    )
    print(f"welcome: {welcome!r}")

    llm_replies = ask_jarvis(
        "Reply with exactly: OK",
        model=model,
        thread_id="smoke-user",
        user_info=user_info,
    )
    print(f"ask_jarvis LLM replies: {llm_replies!r}")
    print("Smoke OK.")



if __name__ == "__main__":
    main()
