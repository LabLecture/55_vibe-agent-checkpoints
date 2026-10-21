"""확정 모델로 대본 세 턴을 차례로 돌리며 학습지 챗봇 그래프 전체에 Langfuse CallbackHandler 를 꽂고, trace 주소를 표로 남긴다."""
import os
import sys
import time
from datetime import datetime
from pathlib import Path

from langchain_core.messages import AIMessage, HumanMessage
from langfuse import get_client
from langfuse.langchain import CallbackHandler

# 3-1 의 trace 도우미와 3-4 의 대본 · 표 도우미를 고치지 않고 가져다 쓴다
from run_graph import cell, turn
from src.config.agents import TEAM_MEMBERS
from src.graph.builder import build_graph
from trace_rag import check_env, propagate_attributes, trace_link

CONFIRMED_MODEL = "google/gemma-4-26b-a4b-it"  # CLAUDE.md 의 확정 모델
RECURSION_LIMIT = 5  # 서버(workflow_service)와 같은 걸음 한도
TAG = "3-8-manus"
TURNS = [1, 2, 3]
PREVIEW_LEN = 80
OUT_PATH = Path("/app/out/trace_manus.md")


def run_turn(graph, langfuse, n: int, messages: list) -> dict:
    """한 턴을 돌린다. 턴마다 새 handler 로 trace 하나를 남기고, 오류가 나도 다시 보내지 않는다."""
    name = f"3-8-turn{n}"
    tags = [TAG, f"turn{n}"]
    # 턴마다 새로 만들어 last_trace_id 가 다른 턴과 섞이지 않게 한다
    handler = CallbackHandler()
    config = {
        "recursion_limit": RECURSION_LIMIT,
        "callbacks": [handler],
        "run_name": name,
        "metadata": {"langfuse_tags": tags},
    }
    start = time.monotonic()
    answer, status = "", "완료"
    try:
        with propagate_attributes(trace_name=name, tags=tags):
            result = graph.invoke({"messages": messages, "TEAM_MEMBERS": TEAM_MEMBERS}, config=config)
        # 이번에 넣은 말 뒤에 새로 생긴 AI 답 가운데 내용 있는 마지막 것 (앞 턴 답을 집지 않게)
        new = [m for m in result["messages"][len(messages):] if isinstance(m, AIMessage) and m.content]
        answer = new[-1].content if new else ""
        if not answer:
            status = "완료 (새 답 없음)"
    except Exception as e:  # 한도 초과를 포함한 오류 원문을 그대로 남긴다
        status = f"오류: {type(e).__name__}: {e}"
    sec = time.monotonic() - start
    return {"turn": n, "name": name, "answer": answer, "status": status, "sec": sec,
            "url": trace_link(langfuse, handler.last_trace_id)}


def main_run() -> None:
    check_env()
    model = os.environ["LLM_MODEL"]
    if model != CONFIRMED_MODEL:
        sys.exit(f"LLM_MODEL 이 확정 모델({CONFIRMED_MODEL})이 아니다: {model}")
    langfuse = get_client()
    started = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    # 서버처럼 그래프는 한 번만 짓는다
    graph = build_graph()

    rows = []
    messages = []
    try:
        for n in TURNS:
            question, _ = turn(n)
            if rows and not rows[-1]["answer"]:
                # 앞 턴 답이 없으면 이어 붙일 말이 없으니 돌리지 않는다
                rows.append({"turn": n, "name": f"3-8-turn{n}", "answer": "", "sec": 0.0,
                             "status": f"건너뜀: 턴 {n - 1} 답 없음", "url": "(없음)"})
                continue
            messages.append(HumanMessage(question))
            print(f"[턴 {n}] {question} ...", flush=True)
            r = run_turn(graph, langfuse, n, list(messages))
            print(f"  -> {r['sec']:.1f}초 {r['status'][:80]}", flush=True)
            rows.append(r)
            # 다음 턴 앞 챗봇 말은 그래프가 이번 턴에 실제로 낸 답
            messages.append(AIMessage(r["answer"]))
    finally:
        # 끝나기 전에 쌓인 기록을 Langfuse 로 밀어 보낸다
        langfuse.flush()

    lines = [
        "# 3-8 그래프 trace: 대본 세 턴",
        "",
        f"모델: {model} · 실행: {started} · 걸음 한도: {RECURSION_LIMIT}",
        "",
        f"태그: 모든 trace 에 `{TAG}` · 턴 번호(`turn1` ~ `turn3`). 턴 2 · 3 의 앞 챗봇 말은 그래프가 앞 턴에 실제로 낸 답이다",
        "",
        "뒤 세 칸은 Langfuse 화면에서 읽어 사람이 채운다.",
        "",
        "| 턴 | 고객 말 | 답 앞 80자 | 걸린 초 | 상태 | trace 이름 | trace 주소 | 줄 차례 | supervisor 가 고른 일꾼 | 가장 오래 걸린 줄과 초 |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        head = cell(r["answer"][:PREVIEW_LEN]) if r["answer"] else "(답 없음)"
        lines.append(
            f"| {r['turn']} | {cell(turn(r['turn'])[0])} | {head} | {r['sec']:.1f} | {cell(r['status'])} "
            f"| {r['name']} | {cell(r['url'])} |  |  |  |"
        )
    lines += ["", "## 답 전문", ""]
    for r in rows:
        lines += [f"### 턴 {r['turn']}", "", "~~~text", r["answer"] or "(답 없음)", "~~~", ""]

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text("\n".join(lines), encoding="utf-8")
    print(f"표 저장: {OUT_PATH}")


if __name__ == "__main__":
    main_run()
