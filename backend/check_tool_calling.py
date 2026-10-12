"""후보 모델 3종이 도구 호출을 실제로 돌려주는지 한 번씩 확인한다. 도구는 실행하지 않는다."""
import asyncio
import os
import sys
import time

from langchain_core.tools import tool
from langchain_openai import ChatOpenAI

BASE_URL = "https://openrouter.ai/api/v1"
TIMEOUT_SEC = 60  # 시도당 제한 시간
RETRY_WAIT_SEC = 5  # 재시도 전 대기

MODELS = [
    "google/gemma-4-26b-a4b-it",
    "nvidia/nemotron-3-super-120b-a12b:free",
    "dots-studio/dots-3-note-preview:free",
]

PROMPT = "덧셈 도구를 써서 답해줘. 3 더하기 4는?"


@tool
def add(a: int, b: int) -> int:
    """두 수를 더한다."""
    return a + b  # 정의만 알려 줄 뿐, 실제로 호출하지 않는다


async def check(model: str, api_key: str) -> dict:
    llm = ChatOpenAI(
        model=model, base_url=BASE_URL, api_key=api_key, max_retries=0
    ).bind_tools([add])
    error = ""
    for attempt in range(2):
        try:
            msg = await asyncio.wait_for(llm.ainvoke(PROMPT), TIMEOUT_SEC)
            return {"msg": msg, "error": ""}
        except asyncio.TimeoutError:
            error = f"TimeoutError: {TIMEOUT_SEC}초 초과"
        except Exception as e:  # 받은 오류 원문을 그대로 남긴다
            error = f"{type(e).__name__}: {e}"
        if attempt == 0:
            await asyncio.sleep(RETRY_WAIT_SEC)
    return {"msg": None, "error": error}


async def main() -> None:
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        sys.exit("환경 변수 OPENROUTER_API_KEY 가 없습니다.")

    for model in MODELS:
        start = time.monotonic()
        r = await check(model, api_key)
        sec = time.monotonic() - start
        print(f"=== {model} ({sec:.1f}초)")
        if r["msg"] is None:
            print("판정: 응답 없음")
            print(f"오류 원문: {r['error']}")
            continue
        calls = r["msg"].tool_calls
        print("판정:", "○" if calls else "×")
        print("tool_calls 원문:", calls)
        print("content 원문:", repr(r["msg"].content))


if __name__ == "__main__":
    asyncio.run(main())
