"""계산 도구 셋을 모델에 쥐여 주고, 모델이 고른 도구를 그 인자로 실제 실행해 표로 남긴다."""
import asyncio
import os
import sys
import time
from pathlib import Path

from langchain_core.tools import tool
from langchain_openai import ChatOpenAI

BASE_URL = "https://openrouter.ai/api/v1"
TIMEOUT_SEC = 60  # 시도당 제한 시간
RETRY_WAIT_SEC = 5  # 재시도 전 대기
OUT_PATH = Path("/app/out/tool_run.md")

QUESTIONS = [
    "3.5와 7을 곱해줘",
    "2의 10승이 뭐야?",
    "123 더하기 456은?",
]


@tool
def multiply(x: float, y: float) -> float:
    """x와 y를 곱합니다."""
    return x * y


@tool
def exponentiate(x: float, y: float) -> float:
    """x의 y승(거듭제곱)을 계산합니다."""
    return x**y


@tool
def add(x: float, y: float) -> float:
    """x와 y를 더합니다."""
    return x + y


TOOLS = [multiply, exponentiate, add]
TOOLS_BY_NAME = {t.name: t for t in TOOLS}


async def ask(llm, question: str) -> dict:
    error = ""
    for attempt in range(2):
        try:
            msg = await asyncio.wait_for(llm.ainvoke(question), TIMEOUT_SEC)
            return {"msg": msg, "error": ""}
        except asyncio.TimeoutError:
            error = f"TimeoutError: {TIMEOUT_SEC}초 초과"
        except Exception as e:  # 받은 오류 원문을 그대로 남긴다
            error = f"{type(e).__name__}: {e}"
        if attempt == 0:
            await asyncio.sleep(RETRY_WAIT_SEC)
    return {"msg": None, "error": error}


def run_call(call: dict) -> tuple[str, bool]:
    """도구 하나를 실행해 (결과 또는 오류 원문, 성공 여부)를 돌려준다."""
    t = TOOLS_BY_NAME.get(call["name"])
    if t is None:
        return f"KeyError: 없는 도구 {call['name']!r}", False
    try:
        return str(t.invoke(call["args"])), True
    except Exception as e:  # 인자가 틀린 경우 등, 오류 원문을 그대로 남긴다
        return f"{type(e).__name__}: {e}", False


def cell(text: str) -> str:
    # 표가 깨지지 않게 | 와 줄바꿈을 바꾼다
    return str(text).replace("|", "\\|").replace("\r", " ").replace("\n", " ")


async def main() -> None:
    model = os.environ.get("LLM_MODEL")
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not model:
        sys.exit("환경 변수 LLM_MODEL 이 없습니다.")
    if not api_key:
        sys.exit("환경 변수 OPENROUTER_API_KEY 가 없습니다.")

    llm = ChatOpenAI(
        model=model, base_url=BASE_URL, api_key=api_key, max_retries=0
    ).bind_tools(TOOLS)

    lines = [
        "# 도구 실행 확인",
        "",
        f"모델: {model}",
        "",
        "기대 기준: 1 multiply → 24.5 · 2 exponentiate → 1024 · 3 add → 579",
        "",
        "| 질문 | 고른 도구 | 인자 원문 | 실행 결과 | 걸린 초 | 상태 | 같은 도구인가 | 같은 결과인가 |",
        "|---|---|---|---|---|---|---|---|",
    ]

    for q in QUESTIONS:
        start = time.monotonic()
        r = await ask(llm, q)
        sec = time.monotonic() - start

        if r["msg"] is None:
            names, args, result, status = "", "", r["error"], "호출 실패"
        elif not r["msg"].tool_calls:
            names, args, result, status = "(없음)", "", r["msg"].content, "글 답"
        else:
            calls = r["msg"].tool_calls
            runs = [run_call(c) for c in calls]
            names = "; ".join(c["name"] for c in calls)
            args = "; ".join(str(c["args"]) for c in calls)
            result = "; ".join(out for out, _ in runs)
            status = "도구 실행" if all(ok for _, ok in runs) else "실행 실패"

        print(f"=== {q} ({sec:.1f}초) {status}: {names} {args} -> {result}")
        lines.append(
            f"| {cell(q)} | {cell(names)} | {cell(args)} | {cell(result)} "
            f"| {sec:.1f} | {status} |  |  |"
        )

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"표 저장: {OUT_PATH}")


if __name__ == "__main__":
    asyncio.run(main())
