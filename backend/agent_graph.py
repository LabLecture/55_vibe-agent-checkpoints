"""2-3 에이전트(create_agent)가 안에 짠 그래프를 꺼내 보고, stream 으로 칸마다 한 걸음씩 돌려 표로 남긴다."""
import os
import sys
import time
from pathlib import Path

from langchain.agents import create_agent
from langchain_core.messages import AIMessage, ToolMessage
from langchain_openai import ChatOpenAI

# 2-3 에이전트의 도구 · 시스템 프롬프트 · 질문과 2-2 의 표 도우미를 고치지 않고 가져다 쓴다
from run_agent import QUESTIONS, SYSTEM_PROMPT, TOOLS, TRACE_CHARS, text_of
from run_news import BASE_URL, cell

OUT_PATH = Path("/app/out/agent_graph.md")
ATTEMPTS = 2  # 막히면 한 번만 다시 보낸다


def describe(m) -> tuple[str, str, str]:
    # 메시지 하나를 (종류, 도구 이름, 앞부분) 으로 바꾼다 — 앞부분은 TRACE_CHARS 글자만
    if isinstance(m, AIMessage) and m.tool_calls:
        names = ", ".join(c["name"] for c in m.tool_calls)
        args = "; ".join(str(c["args"]) for c in m.tool_calls)
        return "도구 쪽지", names, args[:TRACE_CHARS]
    if isinstance(m, ToolMessage):
        return "도구 결과", m.name or "", text_of(m.content)[:TRACE_CHARS]
    if isinstance(m, AIMessage):
        return "답", "", text_of(m.content)[:TRACE_CHARS]
    return type(m).__name__, "", text_of(m.content)[:TRACE_CHARS]


def run_once(agent, question: str) -> list[tuple]:
    # stream 기본값(updates)은 칸이 끝날 때마다 {칸 이름: 그 칸이 더한 것} 을 준다
    rows, count = [], 1  # 입력 질문 1개부터 센다 (시스템 프롬프트는 state 에 들어가지 않는다)
    for step, chunk in enumerate(agent.stream({"messages": [{"role": "user", "content": question}]}), 1):
        for name, update in chunk.items():
            # messages 를 더하지 않는 칸(None 등)은 건너뛴다
            new = update.get("messages", []) if isinstance(update, dict) else []
            if not new:
                continue
            count += len(new)
            parts = [describe(m) for m in new]
            kind, tools, head = (", ".join(p[i] for p in parts if p[i]) for i in range(3))
            rows.append((step, name, kind, tools, head, count))
            print(f"STEP {step} · {name} · {kind} · {tools} · {head} · messages {count}개")
    return rows


def main() -> None:
    model = os.environ.get("LLM_MODEL")
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not model:
        sys.exit("환경 변수 LLM_MODEL 이 없습니다.")
    if not api_key:
        sys.exit("환경 변수 OPENROUTER_API_KEY 가 없습니다.")

    llm = ChatOpenAI(model=model, base_url=BASE_URL, api_key=api_key, max_retries=0)
    agent = create_agent(model=llm, tools=TOOLS, system_prompt=SYSTEM_PROMPT)
    question = QUESTIONS[0]

    # with_retry 는 stream 을 다시 보내 주지 않으므로 손으로 두 번까지 시도한다
    rows, error, attempt = [], "", 0
    start = time.monotonic()
    for attempt in range(1, ATTEMPTS + 1):
        try:
            rows, error = run_once(agent, question), ""
            break
        except Exception as e:  # 막힌 시도의 STEP 줄은 버리고 처음부터 다시
            rows, error = [], f"{type(e).__name__}: {e}"
            print(f"[{attempt}번째 시도 실패] {error}")
    sec = time.monotonic() - start
    status = "호출 실패" if error else "완료"
    print(f"=== ({sec:.1f}초) {status} · 시도 {attempt}번")

    lines = [
        "# 에이전트 안 그래프 STEP 확인",
        "",
        f"모델: {model} · 시도 횟수: {attempt} · 걸린 초: {sec:.1f} · 상태: {status}",
        "",
        f"질문: {question}",
        "",
        "```mermaid",
        agent.get_graph().draw_mermaid().strip(),
        "```",
        "",
        "| STEP | 칸 이름 | 더한 메시지 종류 | 도구 이름 | 앞부분 | 쌓인 messages 개수 |",
        "|---|---|---|---|---|---|",
    ]
    lines += [f"| {' | '.join(cell(x) for x in row)} |" for row in rows]
    if error:
        lines += ["", f"오류: {cell(error)}"]

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"표 저장: {OUT_PATH}")


if __name__ == "__main__":
    main()
