"""학습지 고객센터 질문을 의도 다섯 가운데 하나로 나누고, 결과를 표로 남긴다."""
import os
import sys
import time
from pathlib import Path

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

BASE_URL = "https://openrouter.ai/api/v1"
TIMEOUT_SEC = 60  # 시도당 제한 시간
RETRY_WAIT_SEC = 5  # 재시도 전 대기
OUT_PATH = Path("/app/out/intent_classify.md")

INTENTS = [
    "MEMBERSHIP",
    "LEARNING_SUPPORT",
    "TEACHER_RECRUITMENT",
    "EMPLOYEE_RECRUITMENT",
    "GENERAL_INQUIRIES",
]

QUESTIONS = [
    # 섹션 1-6 표의 질문 셋
    "교재는 언제 배송되나요?",
    "아이 공부가 어디까지 됐나요?",
    "내일 서울 날씨는 어때요?",
    "초등학교 딸 수업진도를 체크할 수 있나요?",
    "쌍문초등학교 6학년 송혜교",
    "1",
    # 두 의도(교사채용 · 직원채용)에 함께 든 예시
    "신입채용에 지원하고 싶습니다.",
    "귀사에 입사하고 싶은 지원자 입니다.",
]

TEMPLATE = """당신은 학습지 서비스의 고객 지원 챗봇입니다. 고객의 질문을 분석하여 다음 다섯 가지 주제 중 하나로 분류해주세요:

1. MEMBERSHIP(회원관련)
- 홈페이지 회원 가입 후 이용권한이 없다고 나옵니다.
- 휴면계정 삭제 안내 메일이 왔습니다. 어떻게 해야 하나요?
- 휴면계정이란 무엇인가요?
- 회원가입이나 ID/PW찾기 인증이 안됩니다.
- 개인정보 변경은 어떻게 하나요?
- 회비입금을 카드 자동이체(계좌 변경)로 바꾸고 싶어요.
- 이름, 전화번호 등 회원정보를 변경하고 싶은데요.

2. LEARNING_SUPPORT(학습 지원)
- 아이의 학습 상태를 체크할 수 있나요?
- 수업 시간 조정 가능할까요?
- 수업진도를 체크할 수 있나요?
- 선생님과 상담을 하고 싶은데 어떻게 하나요?
- 아이가 수업을 못 들었을 때 보충수업이 가능한가요?

3. TEACHER_RECRUITMENT(교사채용)
- 상담교사 채용에 대해 문의합니다.
- 신입채용에 지원하고 싶습니다.
- 귀사에 입사하고 싶은 지원자 입니다.
- 입사지원을 완료하였습니다.
- 상담교사의 비젼을 알고 싶습니다.

4. EMPLOYEE_RECRUITMENT(직원채용)
- 신입채용에 지원하고 싶습니다.
- 귀사에 입사하고 싶은 지원자 입니다.
- 편집개발직무를 지원하였는데 실기전형은 무엇인가요?
- 입사지원할 때 전공지식이 많이 필요한가요?
- 입사지원을 완료하였습니다. 제대로 접수되었는지 어떻게 확인 할 수 있나요?

5. GENERAL_INQUIRIES(일반 문의)
- 귀사의 학습지에 대해 알려주세요
- 학습지 종류가 몇 가지인가요?
- 수업은 어디서 하나요?
- '보호필름'은 어디서 구입 할 수 있나요 ?
- 화면을 캡쳐 할 수 없나요?

고객 질문: {question}
위 주제를 참고하여, 고객의 질문이 어떤 카테고리에 속하는지 판단해주세요.
답변은 위의 다섯 가지 중 하나만 대문자로 출력해주세요. (MEMBERSHIP,LEARNING_SUPPORT, TEACHER_RECRUITMENT, EMPLOYEE_RECRUITMENT, GENERAL_INQUIRIES)"""


def build_chain():
    # 모델 이름과 키는 환경 변수로만 읽는다. 자동 재시도는 끈다 (max_retries=0)
    llm = ChatOpenAI(
        model=os.environ["LLM_MODEL"],
        base_url=BASE_URL,
        api_key=os.environ["OPENROUTER_API_KEY"],
        timeout=TIMEOUT_SEC,
        max_retries=0,
    )
    return ChatPromptTemplate.from_template(TEMPLATE) | llm | StrOutputParser()


def ask(chain, question: str) -> tuple[str | None, str]:
    """모델 답 원문과 오류 원문을 돌려준다. 실패하면 한 번만 다시 보낸다."""
    error = ""
    for attempt in range(2):
        try:
            return chain.invoke({"question": question}), ""
        except Exception as e:  # 받은 오류 원문을 그대로 남긴다
            error = f"{type(e).__name__}: {e}"
        if attempt == 0:
            time.sleep(RETRY_WAIT_SEC)
    return None, error


def to_intent(raw: str | None) -> str | None:
    # 앞뒤 공백을 떼고, 다섯 이름 가운데 하나가 아니면 None
    answer = (raw or "").strip()
    return answer if answer in INTENTS else None


def classify(chain, question: str) -> str | None:
    """질문 하나를 받아 의도 이름 하나(또는 None)를 돌려준다."""
    return to_intent(ask(chain, question)[0])


def cell(text: str) -> str:
    # 표가 깨지지 않게 | 와 줄바꿈을 바꾼다
    return str(text).replace("|", "\\|").replace("\r", " ").replace("\n", " ")


def main() -> None:
    if not os.environ.get("LLM_MODEL"):
        sys.exit("환경 변수 LLM_MODEL 이 없습니다.")
    if not os.environ.get("OPENROUTER_API_KEY"):
        sys.exit("환경 변수 OPENROUTER_API_KEY 가 없습니다.")

    # 답 고르기 자기 점검: 공백은 떼고, 소문자는 받지 않는다
    assert to_intent(" MEMBERSHIP\n") == "MEMBERSHIP"
    assert to_intent("membership") is None

    chain = build_chain()
    lines = [
        "# 의도 분류 확인",
        "",
        f"모델: {os.environ['LLM_MODEL']}",
        "",
        "| 질문 | 모델 답 원문 | 고른 의도 | 걸린 초 | 내가 기대한 의도 | 맞았나 |",
        "|---|---|---|---|---|---|",
    ]

    for q in QUESTIONS:
        start = time.monotonic()
        raw, error = ask(chain, q)
        sec = time.monotonic() - start
        intent = to_intent(raw)
        shown = raw if raw is not None else f"(호출 실패) {error}"

        print(f"=== {q} ({sec:.1f}초) {intent}: {shown!r}")
        lines.append(f"| {cell(q)} | {cell(shown)} | {intent} | {sec:.1f} |  |  |")

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"표 저장: {OUT_PATH}")


if __name__ == "__main__":
    main()
