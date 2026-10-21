"""확정 · 예비 · 셋째 후보 모델로 대본 세 턴을 똑같이 돌려 한 표로 견준다.

python compare_scenario.py                  모델마다 새 프로세스를 띄워 동시에 돌리고 표를 쓴다
python compare_scenario.py --worker 경로    (부모가 부름) LLM_MODEL 모델로 세 턴을 돌려 경로에 json 을 남긴다
"""
import json
import os
import re
import signal
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from pathlib import Path

from compare_models import MODELS as CANDIDATES

# CLAUDE.md 넷째 줄의 확정 · 예비 모델 (상자 안엔 CLAUDE.md 가 없어 글자로 적는다)
MODELS = [
    "google/gemma-4-26b-a4b-it",
    "nvidia/nemotron-3-super-120b-a12b:free",
    CANDIDATES[2],  # 섹션 1-3 의 셋째 후보
]
LABELS = ["확정", "예비", "셋째 후보"]

OUT_PATH = Path("/app/out/scenario_compare.md")
TURNS = [1, 2, 3]
TURN_LIMIT_SEC = 180  # 한 턴 제한 시간
PROCESS_LIMIT_SEC = 600  # 자식 프로세스 하나 제한 시간 (세 턴 + 여유)
PREVIEW_LEN = 80
ANSWER_NODES = {"coordinator", "user_class", "class_progress"}  # 고객에게 가는 답을 남기는 칸


def cell(text: str) -> str:
    # 표가 깨지지 않게 | 와 줄바꿈을 바꾼다
    return str(text).replace("|", "\\|").replace("\r", " ").replace("\n", " ")


# ---------- 자식: 모델 하나로 한 묶음 ----------

def on_alarm(signum, frame):
    raise TimeoutError(f"{TURN_LIMIT_SEC}초 초과")


def units(expected: str) -> list[str]:
    # 대본 턴 3 기대 답에서 지난달 · 이번달 단원 글을 꺼낸다
    m = re.search(r"지난달엔 (.+?) 단원을 마쳤고, 이번달엔 (.+?) 진행하고", expected)
    if not m:
        raise ValueError("대본 턴 3 에서 단원 글을 찾지 못했다")
    return [m.group(1), m.group(2)]


def judge(n: int, tool_starts: list[str], answer: str, unit_texts: list[str]) -> str:
    if n == 1:
        ok = not tool_starts and bool(answer)
    elif n == 2:
        ok = any(line.startswith("user_class_tool_start") for line in tool_starts)
    else:
        plain = answer.replace("**", "")
        ok = any(line.startswith("class_progress_tool_start") for line in tool_starts) and all(
            u in plain for u in unit_texts
        )
    return "O" if ok else "X"


def worker(result_path: Path) -> None:
    # 그래프를 불러들이기 전에 이 프로세스 안에서만 자동 다시 보내기를 끈다 (파일은 그대로)
    import src.agents.llm as llm_mod

    llm_mod.ChatOpenAI = partial(llm_mod.ChatOpenAI, max_retries=0)

    from langchain_core.messages import AIMessage, HumanMessage

    from run_graph import run, turn

    signal.signal(signal.SIGALRM, on_alarm)
    unit_texts = units(turn(3)[1])
    model = os.environ["LLM_MODEL"]
    rows = []
    messages = []
    for n in TURNS:
        question, _ = turn(n)
        if rows and not rows[-1]["answer"]:
            # 앞 턴 답이 없으면 이어 붙일 말이 없으니 돌리지 않는다
            rows.append({
                "turn": n, "question": question, "nodes": [], "tool_starts": [], "answer": "",
                "sec": 0.0, "status": f"건너뜀: 턴 {n - 1} 답 없음", "verdict": "X",
            })
        else:
            messages.append(HumanMessage(question))
            signal.alarm(TURN_LIMIT_SEC)
            try:
                steps, _, status, total, tool_starts = run(list(messages))
            finally:
                signal.alarm(0)
            answers = [text for node, text, _ in steps if node in ANSWER_NODES and text != "-"]
            answer = answers[-1] if answers else ""
            rows.append({
                "turn": n, "question": question, "nodes": [s[0] for s in steps],
                "tool_starts": tool_starts, "answer": answer, "sec": total, "status": status,
                "verdict": judge(n, tool_starts, answer, unit_texts),
            })
            # 다음 턴 앞 챗봇 말은 이 모델이 실제로 낸 답
            messages.append(AIMessage(answer))
        # 도중에 프로세스가 죽어도 앞 턴은 남게 턴마다 쓴다
        result_path.write_text(json.dumps({"model": model, "rows": rows}, ensure_ascii=False), encoding="utf-8")


# ---------- 부모: 세 모델 동시에 ----------

def launch(model: str, result_path: Path) -> dict:
    env = {**os.environ, "LLM_MODEL": model}
    cmd = [sys.executable, __file__, "--worker", str(result_path)]
    try:
        p = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=PROCESS_LIMIT_SEC)
        out, err, error = p.stdout, p.stderr, "" if p.returncode == 0 else f"오류: 종료 코드 {p.returncode}"
    except subprocess.TimeoutExpired as e:
        out = e.stdout.decode() if isinstance(e.stdout, bytes) else (e.stdout or "")
        err = e.stderr.decode() if isinstance(e.stderr, bytes) else (e.stderr or "")
        error = f"오류: 프로세스 {PROCESS_LIMIT_SEC}초 초과"
    print(f"\n########## {model} ##########\n{out}{err}", flush=True)
    rows = []
    if result_path.exists():
        rows = json.loads(result_path.read_text(encoding="utf-8"))["rows"]
    if len(rows) < len(TURNS):
        # 자식이 못 남긴 턴은 오류 원문으로 채운다
        tail = err.strip().splitlines()[-1] if err.strip() else ""
        status = f"{error or '오류: 결과 없음'} · {tail}"
        from run_graph import turn

        for n in TURNS[len(rows):]:
            rows.append({
                "turn": n, "question": turn(n)[0], "nodes": [], "tool_starts": [], "answer": "",
                "sec": 0.0, "status": status, "verdict": "X",
            })
    return {"model": model, "rows": rows}


def write_table(results: list[dict]) -> None:
    lines = [
        "# 모델 견주기: 대본 세 턴 한 묶음씩",
        "",
        "모델: " + " · ".join(f"{label} {m}" for label, m in zip(LABELS, MODELS)),
        "",
        f"모델마다 새 프로세스(LLM_MODEL 만 다름)로 동시에 돌렸다 · 걸음 한도 5 · 턴 한도 {TURN_LIMIT_SEC}초 · 다시 보내기 없음",
        "",
        "턴 2 · 3 의 앞 챗봇 말은 대본 글이 아니라 그 모델이 앞 턴에 낸 답이다. 확정 모델을 화면에서 돌린 표는 섹션 3-7(backend/out/chat_run.md)",
        "",
        "판정: 턴 1 은 도구 시작 줄 없이 답이 있으면 O · 턴 2 는 user_class_tool 시작 줄이 있으면 O · "
        "턴 3 은 class_progress_tool 시작 줄이 있고 답에 대본 턴 3 의 지난달 · 이번달 단원 글이 있으면 O · 그 밖 X",
        "",
        "| 묶음 | 모델 | 턴 | 고객 말 | 지나간 칸 | 도구 시작 줄 | 답 앞 80자 | 걸린 초 | 판정 |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for b, r in enumerate(results, 1):
        for row in r["rows"]:
            nodes = " → ".join(row["nodes"]) or "-"
            tools = "<br>".join(cell(t) for t in row["tool_starts"]) or "(없음)"
            head = cell(row["answer"][:PREVIEW_LEN]) if row["answer"] else "(답 없음)"
            lines.append(
                f"| {b} | {r['model']} | {row['turn']} | {cell(row['question'])} | {nodes} | {tools} "
                f"| {head} | {row['sec']:.1f} | {row['verdict']} |"
            )

    lines += ["", "## 상태 원문 (완료가 아닌 턴)", ""]
    bad = [(r["model"], row) for r in results for row in r["rows"] if row["status"] != "완료"]
    lines += [f"- {m} · 턴 {row['turn']}: {cell(row['status'])}" for m, row in bad] or ["(모두 완료)"]

    lines += ["", "## 답 전문", ""]
    for r in results:
        for row in r["rows"]:
            lines += [f"### {r['model']} · 턴 {row['turn']}", "", "~~~text", row["answer"] or "(답 없음)", "~~~", ""]

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text("\n".join(lines), encoding="utf-8")
    print(f"표 저장: {OUT_PATH}")


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        paths = [Path(tmp) / f"model{i}.json" for i in range(len(MODELS))]
        with ThreadPoolExecutor(len(MODELS)) as pool:
            results = list(pool.map(launch, MODELS, paths))
    write_table(results)


if __name__ == "__main__":
    if sys.argv[1:2] == ["--worker"]:
        worker(Path(sys.argv[2]))
    else:
        main()
