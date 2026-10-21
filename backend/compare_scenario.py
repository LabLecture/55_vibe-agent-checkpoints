"""확정 · 예비 · 셋째 후보 모델로 대본 세 턴을 똑같이 돌려 한 표로 견준다.

python compare_scenario.py                  모델마다 새 프로세스를 띄워 동시에 돌리고 표를 쓴다
python compare_scenario.py --more           확정 · 예비만 묶음 2 · 3 을 더 돌려 표에 더하고 요약을 위에 둔다
python compare_scenario.py --worker 경로    (부모가 부름) LLM_MODEL 모델로 세 턴을 돌려 경로에 json 을 남긴다
"""
import json
import os
import re
import signal
import statistics
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


def row_line(b: int, model: str, row: dict) -> str:
    # 묶음 표 한 줄
    nodes = " → ".join(row["nodes"]) or "-"
    tools = "<br>".join(cell(t) for t in row["tool_starts"]) or "(없음)"
    head = cell(row["answer"][:PREVIEW_LEN]) if row["answer"] else "(답 없음)"
    return (
        f"| {b} | {model} | {row['turn']} | {cell(row['question'])} | {nodes} | {tools} "
        f"| {head} | {row['sec']:.1f} | {row['verdict']} |"
    )


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
    # 모델마다 한 묶음씩이므로 묶음 번호는 모두 1
    for r in results:
        lines += [row_line(1, r["model"], row) for row in r["rows"]]

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


# ---------- --more: 확정 · 예비만 묶음 더 ----------

MORE_MODELS = MODELS[:2]  # 셋째 후보는 무료 요청 수를 아끼려 묶음 1 하나로 둔다
MORE_BUNDLES = [2, 3]
ROW_RE = re.compile(r"^\| \d+ \| ")  # 묶음 표 줄
STATUS_RE = re.compile(r"^- (?:묶음 (\d+) · )?(.+?) · 턴 (\d+): (.*)$")  # 묶음 표시가 없으면 묶음 1


def split_row(line: str) -> list[str]:
    # 이스케이프된 \| 는 칸 나눔으로 보지 않는다
    return [c.strip() for c in re.split(r"(?<!\\)\|", line)[1:-1]]


def median_text(values: list[float]) -> str:
    return f"{statistics.median(values):.1f}" if values else "-"


def summary_lines(lines: list[str]) -> list[str]:
    # 묶음 표 줄과 상태 원문 줄을 다시 읽어 모델마다 센다
    rows = [split_row(l) for l in lines if ROW_RE.match(l)]
    statuses = {}
    for l in lines:
        m = STATUS_RE.match(l)
        if m:
            statuses[(int(m.group(1) or 1), m.group(2), int(m.group(3)))] = m.group(4)
    out = [
        "## 요약",
        "",
        "진도까지 = 턴 3 O. 초는 실제로 돈 턴만 셈(건너뜀 0.0초는 뺌, 오류 난 턴의 초는 넣음). "
        "같은 확정 모델도 서버만 불렀을 때 턴 3 이 판마다 갈렸다(섹션 3-7 backend/out/chat_api.md)",
        "",
        "| 모델 | 돌린 묶음 | 턴 2 O | 턴 3 O (진도까지) | 턴 1 가운데 초 | 턴 2 가운데 초 | 턴 3 가운데 초 | 가장 오래 걸린 초 | 끊기거나 오류 난 턴 |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for model in MODELS:
        mine = [r for r in rows if r[1] == model]
        bundles = len({r[0] for r in mine})
        ok = lambda n: sum(1 for r in mine if r[2] == str(n) and r[8] == "O")
        ran = [r for r in mine if not statuses.get((int(r[0]), model, int(r[2])), "").startswith("건너뜀")]
        secs = {n: [float(r[7]) for r in ran if r[2] == str(n)] for n in TURNS}
        longest = f"{max(float(r[7]) for r in ran):.1f}" if ran else "-"
        mine_status = [s for (b, m, _), s in statuses.items() if m == model]
        skipped = sum(1 for s in mine_status if s.startswith("건너뜀"))
        bad = len(mine_status) - skipped
        out.append(
            f"| {model} | {bundles} | {ok(2)}/{bundles} | {ok(3)}/{bundles} | "
            + " | ".join(median_text(secs[n]) for n in TURNS)
            + f" | {longest} | {bad} (건너뜀 {skipped}) |"
        )
    out += [
        "",
        "## 사람이 채울 칸",
        "",
        "| 확인 | 결과 |",
        "|---|---|",
        "| 턴 3 X 판 하나의 답이 진도를 지어냈는가 (묶음 · 모델 적기) |  |",
        "| 이 챗봇에 쓸 모델과 까닭 한 줄 |  |",
        "",
        "## 묶음별 표",
        "",
    ]
    return out


def more() -> None:
    lines = OUT_PATH.read_text(encoding="utf-8").splitlines()
    if any(l.startswith("| 2 | ") for l in lines):
        sys.exit("표에 이미 묶음 2 가 있다. 다시 돌리지 않는다.")
    added = []  # (묶음, 결과)
    for b in MORE_BUNDLES:
        # 묶음 1 과 같은 조건: 한 묶음 안에서 모델들을 동시에
        with tempfile.TemporaryDirectory() as tmp:
            paths = [Path(tmp) / f"b{b}_model{i}.json" for i in range(len(MORE_MODELS))]
            with ThreadPoolExecutor(len(MORE_MODELS)) as pool:
                added += [(b, r) for r in pool.map(launch, MORE_MODELS, paths)]

    # 묶음 줄은 본 표 마지막 줄 뒤에 끼운다
    last_row = max(i for i, l in enumerate(lines) if ROW_RE.match(l))
    new_rows = [row_line(b, r["model"], row) for b, r in added for row in r["rows"]]
    lines[last_row + 1:last_row + 1] = new_rows

    # 상태 원문은 그 목록 끝에 더한다
    new_status = [
        f"- 묶음 {b} · {r['model']} · 턴 {row['turn']}: {cell(row['status'])}"
        for b, r in added for row in r["rows"] if row["status"] != "완료"
    ]
    start = lines.index("## 상태 원문 (완료가 아닌 턴)")
    end = lines.index("## 답 전문")
    if "(모두 완료)" in lines[start:end] and new_status:
        lines.remove("(모두 완료)")
        end -= 1
    last_status = max([i for i in range(start, end) if lines[i].startswith("- ")], default=start + 1)
    lines[last_status + 1:last_status + 1] = new_status

    # 답 전문은 끝에 더한다
    for b, r in added:
        for row in r["rows"]:
            lines += [f"### 묶음 {b} · {r['model']} · 턴 {row['turn']}", "", "~~~text", row["answer"] or "(답 없음)", "~~~", ""]

    # 요약은 본 표 머리 바로 위에 둔다
    head = lines.index(next(l for l in lines if l.startswith("| 묶음 | 모델 |")))
    lines[head:head] = summary_lines(lines)

    OUT_PATH.write_text("\n".join(lines), encoding="utf-8")
    print(f"표에 묶음 {MORE_BUNDLES} · 요약을 더함: {OUT_PATH}")


if __name__ == "__main__":
    if sys.argv[1:2] == ["--worker"]:
        worker(Path(sys.argv[2]))
    elif sys.argv[1:] == ["--more"]:
        more()
    else:
        main()
