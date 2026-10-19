"""2-5 도구 셋 그래프와 2-6 고르는 칸 그래프에 Langfuse CallbackHandler 를 꽂아 한 번씩 돌리고, 고른 차례와 trace 주소를 표로 남긴다."""
import os
import sys
import time
from contextlib import nullcontext
from datetime import datetime
from pathlib import Path

from langchain_openai import ChatOpenAI
from langfuse import get_client
from langfuse.langchain import CallbackHandler
from langgraph.errors import GraphRecursionError

# 2-5 · 2-6 그래프와 실습2 의 도우미를 고치지 않고 가져다 쓴다
import supervisor_graph
import tool_graph
from main import BASE_URL
from search import cell
from trace_rag import check_env, propagate_attributes, trace_link

RETRY_WAIT_SEC = 5  # 재시도 전 대기
TAG = "3-1-graph"
TOOL_QUESTION = "내 등급이랑 주문정보 알려줘"
TOOL_TABLE = Path("/app/out/tool_graph.md")  # 2-5 표 (읽기만)
OUT_PATH = Path("/app/out/trace_graphs.md")


def send(name: str, model: str, run) -> dict:
    """그래프 하나를 돌린다. 막히면 한 번만 다시 보내고, 보낼 때마다 새 handler 로 trace 하나를 남긴다."""
    tags = [TAG, name, model]
    start = time.monotonic()
    error, trace_id = "", None
    for attempt in range(2):
        # 보낼 때마다 새로 만들어 last_trace_id 가 섞이지 않게 한다
        handler = CallbackHandler()
        config = {"callbacks": [handler], "run_name": name, "metadata": {"langfuse_tags": tags}}
        ctx = propagate_attributes(trace_name=name, tags=tags) if propagate_attributes else nullcontext()
        try:
            with ctx:
                out = run(config)
            status, error = "완료", ""
        except GraphRecursionError as e:  # 한도에 걸린 것은 막힘이 아니므로 다시 보내지 않고 그대로 적는다
            out, status, error = None, "한도에서 멈춤", f"{type(e).__name__}: {e}"
        except Exception as e:  # 받은 오류 원문을 그대로 남긴다
            error = f"{type(e).__name__}: {e}"
            trace_id = handler.last_trace_id
            print(f"  [다시 보냄] {error}" if attempt == 0 else f"  [실패] {error}", flush=True)
            if attempt == 0:
                time.sleep(RETRY_WAIT_SEC)
            continue
        return {"out": out, "status": status, "error": error, "sends": attempt + 1,
                "trace_id": handler.last_trace_id, "sec": time.monotonic() - start}
    return {"out": None, "status": "호출 실패", "error": error, "sends": 2,
            "trace_id": trace_id, "sec": time.monotonic() - start}


def old_tool_order(question: str) -> str:
    """2-5 표에서 같은 질문 줄의 「고른 도구 순서」 칸을 읽는다."""
    if not TOOL_TABLE.exists():
        return "(2-5 표 없음)"
    for line in TOOL_TABLE.read_text(encoding="utf-8").splitlines():
        parts = line.split("|")
        # 앞 두 칸(질문 · 고른 도구 순서)에는 | 가 없으므로 그대로 나눠도 된다
        if len(parts) > 2 and parts[1].strip() == question:
            return parts[2].strip()
    return "(같은 질문 없음)"


def main_run() -> None:
    check_env()
    if not os.environ.get("TAVILY_API_KEY"):
        sys.exit("환경 변수가 없습니다: TAVILY_API_KEY")
    model = os.environ["LLM_MODEL"]
    # 2-5 · 2-6 과 같은 설정 (자동 재시도는 끈다)
    llm = ChatOpenAI(model=model, base_url=BASE_URL, api_key=os.environ["OPENROUTER_API_KEY"], max_retries=0)
    langfuse = get_client()
    started = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    tool_g = tool_graph.build_graph(llm)
    sup_g = supervisor_graph.build_graph(llm)
    picks = []  # 고르는 칸이 고른 일꾼 차례 (한도에 걸려도 그때까지 쌓인 것이 남는다)

    def run_tool(config):
        out = tool_g.invoke({"messages": [("user", TOOL_QUESTION)]}, config=config)
        return tool_graph.read_messages(out["messages"])

    def run_supervisor(config):
        # run_once 는 config 에 recursion_limit 만 넣으므로, 콜백은 with_config 로 그래프에 묶어 넘긴다
        picks.clear()
        supervisor_graph.run_once(
            sup_g.with_config(config), supervisor_graph.QUESTION,
            supervisor_graph.RECURSION_LIMIT, [], picks,
        )

    try:
        print("[tool_graph] ...", flush=True)
        tool_r = send("tool_graph", model, run_tool)
        print(f"  -> {tool_r['sec']:.1f}초 {tool_r['status']}", flush=True)
        print("[supervisor_graph] ...", flush=True)
        sup_r = send("supervisor_graph", model, run_supervisor)
        print(f"  -> {sup_r['sec']:.1f}초 {sup_r['status']}", flush=True)
    finally:
        # 끝나기 전에 쌓인 기록을 Langfuse 로 밀어 보낸다
        langfuse.flush()

    tool_order = tool_r["out"][0] if tool_r["out"] else "없음"
    sup_order = " → ".join(picks) or "없음"
    rows = [
        ("tool_graph", TOOL_QUESTION, tool_order, old_tool_order(TOOL_QUESTION), tool_r),
        ("supervisor_graph", supervisor_graph.QUESTION, sup_order, "—", sup_r),
    ]

    lines = [
        "# 3-1 그래프 Langfuse trace (도구 셋 · 고르는 칸)",
        "",
        f"모델: {model} · 실행: {started} · 고르는 칸 되풀이 한도: {supervisor_graph.RECURSION_LIMIT}",
        "",
        f"태그: 모든 trace 에 `{TAG}` · 그래프 이름 · 모델 이름",
        "",
        "마지막 칸은 Langfuse 화면에서 읽어 사람이 채운다.",
        "",
        "| 그래프 | 질문 | 고른 도구(일꾼) 차례 | 2-5 표 차례 | 전체 걸린 초 | 보낸 횟수 | 상태 "
        "| trace 이름 | trace 주소 | trace 줄 차례가 표 차례와 같은가 |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for name, q, order, old, r in rows:
        lines.append(
            f"| {name} | {cell(q)} | {cell(order)} | {cell(old)} | {r['sec']:.1f} | {r['sends']} "
            f"| {r['status']} | {name} | {cell(trace_link(langfuse, r['trace_id']))} |  |"
        )
    errors = [(name, r["error"]) for name, *_, r in rows if r["error"]]
    if errors:
        lines += ["", "## 오류", ""] + [f"- {name}: {cell(e)}" for name, e in errors]
    lines += ["", f"보낸 횟수 합(Tracing 목록에 뜰 trace 수): {sum(r['sends'] for *_, r in rows)}"]

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"표 저장: {OUT_PATH}")


if __name__ == "__main__":
    main_run()
