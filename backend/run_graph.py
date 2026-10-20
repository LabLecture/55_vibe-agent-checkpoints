"""대본 고객 말을 학습지 챗봇 그래프에 넣어 한 걸음씩 돌리고 표로 남긴다.

python run_graph.py     턴 1 만 넣어 표를 새로 쓴다
python run_graph.py 2   턴 1 고객 말 · 턴 1 기대 답 · 턴 2 고객 말을 넣어 표 끝에 줄을 더한다
python run_graph.py 3   턴 1 · 2 고객 말 · 기대 답과 턴 3 고객 말을 넣어 표 끝에 줄을 더한다
"""
import io
import os
import sys
import time
from pathlib import Path

from langchain_core.messages import AIMessage, HumanMessage
from langgraph.errors import GraphRecursionError

from src.config.agents import TEAM_MEMBERS
from src.graph.builder import build_graph

SCENARIO_PATH = Path("/app/scenario.md")
OUT_PATH = Path("/app/out/manus_run.md")
RECURSION_LIMIT = 5  # 예전 과정 값


def cell(text: str) -> str:
    # 표가 깨지지 않게 | 와 줄바꿈을 바꾼다
    return str(text).replace("|", "\\|").replace("\r", " ").replace("\n", " ")


def turn(n: int) -> tuple[str, str]:
    # 대본 표에서 「| n |」 로 시작하는 줄의 (고객 말, 챗봇 기대 답) 칸을 꺼낸다
    for line in SCENARIO_PATH.read_text(encoding="utf-8").splitlines():
        if line.startswith(f"| {n} |"):
            cols = line.split("|")
            return cols[2].strip(), cols[3].strip()
    raise ValueError(f"대본에 턴 {n} 이 없다")


def left_text(update: dict | None) -> str:
    # 칸이 기록지에 남긴 글: messages 가 있으면 그 글, 없으면 나머지 값
    if not update:
        return "-"
    if update.get("messages"):
        return update["messages"][-1].content
    return ", ".join(f"{k}={v}" for k, v in update.items())


class Tee(io.StringIO):
    # 화면에도 그대로 찍고, 찍힌 글은 모아 둔다
    def write(self, s):
        sys.__stdout__.write(s)
        return super().write(s)

    def flush(self):
        sys.__stdout__.flush()


def run(messages: list) -> tuple[list, str | None, str, float, list[str]]:
    # 그래프를 한 걸음씩 돌려 (걸음 목록, 계획, 상태, 걸린 초, 도구 시작 줄) 을 돌려준다
    graph = build_graph()
    steps = []  # (칸 이름, 남긴 글, 걸린 초)
    plan = None
    status = "완료"
    tee = Tee()
    sys.stdout = tee  # 일꾼 안 도구 칸이 다른 스레드에서 찍어도 잡히게 전역으로 바꾼다
    start = last = time.monotonic()
    try:
        for chunk in graph.stream(
            {"messages": messages, "TEAM_MEMBERS": TEAM_MEMBERS},
            {"recursion_limit": RECURSION_LIMIT},
            stream_mode="updates",
        ):
            now = time.monotonic()
            for node, update in chunk.items():
                steps.append((node, left_text(update), now - last))
                if node == "planner" and update:
                    plan = update["full_plan"]
                print(f"=== {node} ({now - last:.1f}초) -> {left_text(update)[:80]}")
            last = now
    except GraphRecursionError as e:
        status = f"한도에 걸림: {e!r}"
    except Exception as e:
        status = f"오류: {e!r}"
    finally:
        sys.stdout = sys.__stdout__
    total = time.monotonic() - start
    print(f"상태: {status} · 걸린 초: {total:.1f}")
    tool_starts = [line for line in tee.getvalue().splitlines() if "_tool_start" in line]
    return steps, plan, status, total, tool_starts


def step_rows(steps: list, status: str) -> list[str]:
    # 다음 칸 = 바로 뒤에 실제로 돈 칸, 마지막 칸은 끝(완료일 때만)
    names = [s[0] for s in steps]
    nexts = names[1:] + ["__end__" if status == "완료" else "-"]
    lines = [
        "| 걸음 | 칸 | 고른 다음 칸 | 남긴 글 앞 80자 | 걸린 초 |",
        "|---|---|---|---|---|",
    ]
    lines += [
        f"| {i} | {node} | {nxt} | {cell(text[:80])} | {sec:.1f} |"
        for i, ((node, text, sec), nxt) in enumerate(zip(steps, nexts), 1)
    ]
    return lines


def tool_lines(tool_starts: list[str]) -> list[str]:
    lines = ["", "## 도구 시작 줄 (원문)", ""]
    lines += ["```", *tool_starts, "```"] if tool_starts else ["(도구 시작 줄 없음)"]
    return lines


def plan_lines(plan: str | None) -> list[str]:
    lines = ["", "## planner 계획 JSON (원문)", ""]
    lines += ["```json", plan, "```"] if plan else ["(planner 가 계획을 남기지 않음)"]
    return lines


def main_turn_one() -> None:
    question, _ = turn(1)
    steps, plan, status, total, tool_starts = run([HumanMessage(question)])
    lines = [
        "# 학습지 챗봇 그래프 한 걸음씩 (대본 턴 1)",
        "",
        f"모델: {os.environ['LLM_MODEL']} · 걸음 한도: {RECURSION_LIMIT} · 걸린 초: {total:.1f} · 상태: {cell(status)}",
        "",
        f"고객 말: {question}",
        "",
    ]
    lines += step_rows(steps, status) + tool_lines(tool_starts) + plan_lines(plan)
    # 일꾼 칸이 남긴 마지막 답 원문
    answers = [text for node, text, _ in steps if node in TEAM_MEMBERS]
    lines += ["", "## 일꾼이 남긴 답 (원문)", ""]
    lines += [answers[-1]] if answers else ["(일꾼이 답을 남기지 않음)"]
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"표 저장: {OUT_PATH}")


def main_turn_two() -> None:
    q1, a1 = turn(1)
    q2, expected = turn(2)
    steps, plan, status, total, tool_starts = run([HumanMessage(q1), AIMessage(a1), HumanMessage(q2)])
    # 일꾼 칸이 남긴 마지막 답 원문
    answers = [text for node, text, _ in steps if node in TEAM_MEMBERS]
    lines = [
        "",
        "# 대본 턴 2 (앞 말과 함께)",
        "",
        f"모델: {os.environ['LLM_MODEL']} · 걸음 한도: {RECURSION_LIMIT} · 걸린 초: {total:.1f} · 상태: {cell(status)}",
        "",
        "| 넣은 말 | 역할 | 글 |",
        "|---|---|---|",
        f"| 1 | 고객 (턴 1) | {cell(q1)} |",
        f"| 2 | 챗봇 기대 답 (턴 1) | {cell(a1)} |",
        f"| 3 | 고객 (턴 2) | {cell(q2)} |",
        "",
    ]
    lines += step_rows(steps, status) + tool_lines(tool_starts) + plan_lines(plan)
    lines += ["", "## 일꾼이 남긴 답 (원문)", ""]
    lines += [answers[-1]] if answers else ["(일꾼이 답을 남기지 않음)"]
    lines += [
        "",
        "## 사람이 채울 칸",
        "",
        f"대본 턴 2 기대 답: {expected}",
        "",
        "| 확인 | 결과 |",
        "|---|---|",
        "| 턴 2 에 도구 시작 줄이 있는가 |  |",
        "| 턴 2 답의 수업 이름이 섹션 3-3(db/init.sql) 표와 같은가 |  |",
        "| 턴 2 답이 대본 턴 2 처럼 번호로 셋을 늘어놓는가 |  |",
    ]
    # 턴 1 줄은 그대로 두고 끝에 더한다
    with OUT_PATH.open("a", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(f"표에 더함: {OUT_PATH}")


def main_turn_three() -> None:
    q1, a1 = turn(1)
    q2, a2 = turn(2)
    q3, expected = turn(3)
    steps, plan, status, total, tool_starts = run(
        [HumanMessage(q1), AIMessage(a1), HumanMessage(q2), AIMessage(a2), HumanMessage(q3)]
    )
    # 일꾼 칸이 남긴 마지막 답 원문
    answers = [text for node, text, _ in steps if node in TEAM_MEMBERS]
    lines = [
        "",
        "# 대본 턴 3 (앞 말과 함께)",
        "",
        f"모델: {os.environ['LLM_MODEL']} · 걸음 한도: {RECURSION_LIMIT} · 걸린 초: {total:.1f} · 상태: {cell(status)}",
        "",
        "| 넣은 말 | 역할 | 글 |",
        "|---|---|---|",
        f"| 1 | 고객 (턴 1) | {cell(q1)} |",
        f"| 2 | 챗봇 기대 답 (턴 1) | {cell(a1)} |",
        f"| 3 | 고객 (턴 2) | {cell(q2)} |",
        f"| 4 | 챗봇 기대 답 (턴 2) | {cell(a2)} |",
        f"| 5 | 고객 (턴 3) | {cell(q3)} |",
        "",
    ]
    lines += step_rows(steps, status) + tool_lines(tool_starts) + plan_lines(plan)
    lines += ["", "## 일꾼이 남긴 답 (원문)", ""]
    lines += [answers[-1]] if answers else ["(일꾼이 답을 남기지 않음)"]
    lines += [
        "",
        "## 사람이 채울 칸",
        "",
        f"대본 턴 3 기대 답: {expected}",
        "",
        "| 확인 | 결과 |",
        "|---|---|",
        "| supervisor 가 class_progress 를 골랐는가 |  |",
        "| 도구 시작 줄의 수업 이름 · 번호 |  |",
        "| 답의 지난달 · 이번달 진도가 대본 턴 3 글과 같은가 |  |",
    ]
    # 앞 턴 줄은 그대로 두고 끝에 더한다
    with OUT_PATH.open("a", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(f"표에 더함: {OUT_PATH}")


if __name__ == "__main__":
    if sys.argv[1:] == ["3"]:
        main_turn_three()
    else:
        main_turn_two() if sys.argv[1:] == ["2"] else main_turn_one()
