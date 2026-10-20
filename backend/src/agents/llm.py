"""모델 종류를 받아 OpenRouter 의 ChatOpenAI 를 돌려준다."""
import os
from functools import lru_cache

from langchain_openai import ChatOpenAI

from src.config.agents import LLMType

BASE_URL = "https://openrouter.ai/api/v1"


# 같은 종류를 다시 부르면 처음 만든 것을 그대로 돌려준다
@lru_cache
def get_llm_by_type(llm_type: LLMType) -> ChatOpenAI:
    # 세 종류 모두 같은 모델을 쓴다 (종류는 캐시 열쇠 역할만 한다)
    return ChatOpenAI(
        model=os.environ["LLM_MODEL"],
        base_url=BASE_URL,
        api_key=os.environ["OPENROUTER_API_KEY"],
        temperature=0,
    )
