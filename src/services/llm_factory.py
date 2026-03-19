from langchain_openai import ChatOpenAI
from config.sqlconfig import modelconfig


def get_openai_llm() -> ChatOpenAI:
    """
    Factory function that returns the configured OpenAI LLM instance.
    Model, temperature, and seed are driven by settings / .env.
    Streaming is intentionally disabled — callers use ainvoke() without a
    streaming sink, so enabling it only adds latency overhead.
    """
    from pydantic import SecretStr

    return ChatOpenAI(
        api_key=SecretStr(modelconfig.OPENAI_API_KEY),
        model=modelconfig.MODEL_NAME,
        temperature=modelconfig.TEMPERATURE,
        streaming=False,
        seed=42,
        model_kwargs={"response_format": {"type": "json_object"}},
    )


