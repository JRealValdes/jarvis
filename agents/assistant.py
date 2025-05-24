from enums.core_enums import ModelEnums
from langchain.schema import AIMessage
from agents.factory import build_agent

model_used = ModelEnums.GPT_3_5
agent = build_agent(model_used)

def ask_jarvis(question: str):
    response = agent.invoke({"messages": [{"role": "user", "content": question}]})
    ai_messages = [msg.content for msg in response['messages'] if isinstance(msg, AIMessage) and msg.content]
    return ai_messages[-1] if ai_messages else "Lo siento, señor. No tengo respuesta para su petición."
