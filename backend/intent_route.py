"""실습1 의도 분류 위에 하위 의도 · 답을 만드는 길 고르기 · 대화 상태를 얹고, 결과를 표로 남긴다."""
import os
import sys
import time
from pathlib import Path

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

# 실습1의 분류 함수 두 반쪽(ask · to_intent)과 표 칸 다듬기를 그대로 쓴다
from classify_intent import BASE_URL, TIMEOUT_SEC, ask, build_chain, cell, to_intent

OUT_PATH = Path("/app/out/intent_route.md")

SUB_INTENTS = [
    "STUDY_STATUS",
    "CLASS_SCHEDULE",
    "CLASS_PROGRESS",
    "TEACHER_CONSULT",
    "MAKEUP_CLASS",
]

SUB_TEMPLATE = """당신은 학습지 서비스의 고객 지원 챗봇입니다. 학습 지원에 관한 고객의 질문을 분석하여 다음 다섯 가지 세부 주제 중 하나로 분류해주세요:

1. STUDY_STATUS(학습 상태 체크)
- 아이의 학습 상태를 체크할 수 있나요?

2. CLASS_SCHEDULE(수업 시간 조정)
- 수업 시간 조정 가능할까요?

3. CLASS_PROGRESS(수업진도 체크)
- 수업진도를 체크할 수 있나요?

4. TEACHER_CONSULT(선생님 상담)
- 선생님과 상담을 하고 싶은데 어떻게 하나요?

5. MAKEUP_CLASS(보충수업)
- 아이가 수업을 못 들었을 때 보충수업이 가능한가요?

고객 질문: {question}
위 주제를 참고하여, 고객의 질문이 어떤 카테고리에 속하는지 판단해주세요.
답변은 위의 다섯 가지 중 하나만 대문자로 출력해주세요. (STUDY_STATUS, CLASS_SCHEDULE, CLASS_PROGRESS, TEACHER_CONSULT, MAKEUP_CLASS)"""

ASK_RECRUIT = "채용에 관련된 문의를 주셨네요. 우선 1) 선생님으로 입사하려는 건지요? 2) 회사에 입사하려는 건지요?"
SORRY = "죄송합니다. 질문을 이해하지 못했습니다. 이전 문의하신 내용을 계속 진행하시겠습니까?"
GREETING = (
    "안녕하세요! 새싹배움 고객센터입니다. 어떤 도움이 필요하신가요? "
    "다음 서비스를 제공해드릴 수 있습니다: 1.회원관련 2.학습 지원 3.교사채용 4.직원채용 5.일반 문의"
)

RECRUIT_WORDS = ["교사", "선생님", "직원", "직무"]

# 의도(하위가 있으면 하위)별 단계. 없는 의도는 한 단계로 끝난다
STEPS = {"CLASS_PROGRESS": ["학생 정보 묻기", "수업 고르기", "진도 답하기"]}
DEFAULT_STEPS = ["답하기"]

DIALOGUE = [
    "초등학교 딸 수업진도를 체크할 수 있나요?",
    "쌍문초등학교 6학년 송혜교",
    "1",
]

SINGLES = [
    # 섹션 1-6 표의 질문 셋
    "교재는 언제 배송되나요?",
    "아이 공부가 어디까지 됐나요?",
    "내일 서울 날씨는 어때요?",
    # 두 채용 의도에 함께 든 예시 둘
    "신입채용에 지원하고 싶습니다.",
    "귀사에 입사하고 싶은 지원자 입니다.",
]


def build_sub_chain():
    # 모델 줄은 실습1 · main.py 와 같은 꼴. 자동 재시도는 끈다 (max_retries=0)
    llm = ChatOpenAI(
        model=os.environ["LLM_MODEL"],
        base_url=BASE_URL,
        api_key=os.environ["OPENROUTER_API_KEY"],
        timeout=TIMEOUT_SEC,
        max_retries=0,
    )
    return ChatPromptTemplate.from_template(SUB_TEMPLATE) | llm | StrOutputParser()


def to_sub(raw: str | None) -> str | None:
    # 앞뒤 공백을 떼고, 하위 다섯 이름 가운데 하나가 아니면 None
    answer = (raw or "").strip()
    return answer if answer in SUB_INTENTS else None


def pick_route(intent: str | None, sub: str | None, text: str) -> tuple[str, str | None]:
    """(길, 정해 둔 답)을 돌려준다. 정해 둔 답이 None 이면 의도를 모르는 경우다."""
    if intent == "GENERAL_INQUIRIES":
        return "RAG", ""
    if intent == "MEMBERSHIP":
        return "PROMPT", ""
    if intent in ("TEACHER_RECRUITMENT", "EMPLOYEE_RECRUITMENT"):
        # 교사인지 직원인지 가를 낱말이 없으면 되묻는다
        if any(w in text for w in RECRUIT_WORDS):
            return "RAG", ""
        return "NO_LLM", ASK_RECRUIT
    if intent == "LEARNING_SUPPORT":
        if sub in ("CLASS_PROGRESS", "STUDY_STATUS"):
            return "DB", ""
        if sub in SUB_INTENTS:
            return "RAG", ""
    # 상위 None 이거나 하위가 다섯 밖
    return "NO_LLM", None


def new_state() -> dict:
    return {"intent": None, "sub": None, "chain_type": None, "step": 0, "prev": None}


def none_answer(state: dict) -> tuple[str, str]:
    """의도를 모를 때의 (정해 둔 답, 상태 글). 앞 대화의 의도가 있으면 그것을 되돌린다."""
    prev = state["prev"]
    if prev is None:
        return GREETING, "의도 없음"
    state["intent"], state["sub"], state["chain_type"] = prev
    state["step"] = 0  # 다음 말부터 되돌린 의도의 첫 단계로 잇는다
    return SORRY, f"이전 의도 되돌림({prev[1] or prev[0]})"


def turn(chain, sub_chain, state: dict, text: str) -> dict:
    """한 턴을 처리하고 표 한 줄에 쓸 값을 돌려준다. state 는 제자리에서 바뀐다."""
    errors = []
    if state["intent"] is not None:
        # 의도가 이미 있으면 다시 분류하지 않고 의도 · 길을 잇는다
        intent, sub, chain_type = state["intent"], state["sub"], state["chain_type"]
        answer, note = "", "이어감"
        state["step"] += 1
    else:
        raw, err = ask(chain, text)
        if err:
            errors.append(err)
        intent, sub = to_intent(raw), None
        if intent == "LEARNING_SUPPORT":
            raw, err = ask(sub_chain, text)
            if err:
                errors.append(err)
            sub = to_sub(raw)
        chain_type, answer = pick_route(intent, sub, text)
        note = "분류함"
        if answer is None:
            answer, why = none_answer(state)
            return row(intent, sub, chain_type, answer, f"{note} · {why}", errors)
        state.update(intent=intent, sub=sub, chain_type=chain_type, step=1)

    steps = STEPS.get(sub or intent, DEFAULT_STEPS)
    step = state["step"]
    note += f" · {step}/{len(steps)} {steps[step - 1]}"
    if step >= len(steps):
        # 단계를 다 쓰면 이 의도를 앞 대화의 의도로 옮기고 비운다
        state["prev"] = (intent, sub, chain_type)
        state.update(intent=None, sub=None, chain_type=None, step=0)
        note += " · 끝"
    return row(intent, sub, chain_type, answer, note, errors)


def row(intent, sub, chain_type, answer, note, errors) -> dict:
    if errors:
        note += " · (호출 실패) " + " / ".join(errors)
    return {
        "intent": str(intent),
        # 하위는 LEARNING_SUPPORT 일 때만 적는다
        "sub": str(sub) if intent == "LEARNING_SUPPORT" else "",
        "chain_type": chain_type,
        "answer": answer,
        "note": note,
    }


def self_check() -> None:
    # 모델 없이 길 고르기와 None 갈래를 점검한다
    assert pick_route("MEMBERSHIP", None, "x") == ("PROMPT", "")
    assert pick_route("GENERAL_INQUIRIES", None, "x") == ("RAG", "")
    assert pick_route("EMPLOYEE_RECRUITMENT", None, "편집개발직무 지원") == ("RAG", "")
    assert pick_route("TEACHER_RECRUITMENT", None, "신입채용 지원") == ("NO_LLM", ASK_RECRUIT)
    assert pick_route("LEARNING_SUPPORT", "CLASS_PROGRESS", "x") == ("DB", "")
    assert pick_route("LEARNING_SUPPORT", "MAKEUP_CLASS", "x") == ("RAG", "")
    assert pick_route("LEARNING_SUPPORT", None, "x") == ("NO_LLM", None)
    assert pick_route(None, None, "x") == ("NO_LLM", None)
    s = new_state()
    assert none_answer(s)[0] == GREETING and s["intent"] is None
    s["prev"] = ("LEARNING_SUPPORT", "CLASS_PROGRESS", "DB")
    assert none_answer(s)[0] == SORRY and s["sub"] == "CLASS_PROGRESS"


def main() -> None:
    if not os.environ.get("LLM_MODEL"):
        sys.exit("환경 변수 LLM_MODEL 이 없습니다.")
    if not os.environ.get("OPENROUTER_API_KEY"):
        sys.exit("환경 변수 OPENROUTER_API_KEY 가 없습니다.")
    self_check()

    chain, sub_chain = build_chain(), build_sub_chain()
    lines = [
        "# 의도 갈래 · 길 고르기 확인",
        "",
        f"모델: {os.environ['LLM_MODEL']}",
        "",
        "| 판 | 턴 | 말 | 상위 | 하위 | 길 | 정해 둔 답 | 상태 | 걸린 초 | 대본과 같은 길인가 |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]

    # (판 이름, 말 목록, 상태를 이어 쓰는가)
    runs = [
        ("기억 없이", DIALOGUE, False),
        ("기억하게", DIALOGUE, True),
        ("한 번씩", SINGLES, False),
    ]
    for name, texts, remember in runs:
        state = new_state()
        for i, text in enumerate(texts, 1):
            if not remember:
                state = new_state()
            start = time.monotonic()
            r = turn(chain, sub_chain, state, text)
            sec = time.monotonic() - start

            print(f"=== [{name} {i}] {text} ({sec:.1f}초) {r['intent']}/{r['sub']} {r['chain_type']} · {r['note']}")
            lines.append(
                f"| {name} | {i} | {cell(text)} | {r['intent']} | {r['sub']} | {r['chain_type']} "
                f"| {cell(r['answer'])} | {cell(r['note'])} | {sec:.1f} |  |"
            )

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"표 저장: {OUT_PATH}")


if __name__ == "__main__":
    main()
