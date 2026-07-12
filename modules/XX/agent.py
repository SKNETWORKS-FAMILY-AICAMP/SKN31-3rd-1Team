# modules/agent.py
"""
modules.agent

치매 가이드 챗봇의 핵심 에이전트.

다이어그램에서 빨간 박스로 표시된 부분만 구현한다:

    [사용자 입력] -> [제너레이터(LLM)] <-> [툴노드] -> [END]

여기 없는 것 (일부러 뺌, 다른 사람/다음 단계 담당):
    - 기억 정보(Supabase, Checkpointer)  : 대화 기록을 DB에 저장하는 부분
    - 저장기(대화+상태 merge)             : 여러 턴에 걸친 상태 누적/병합
    - 상태 filter / 상태 변경 제안         : 슬롯필링 로직

즉 이 파일은 "질문 하나 -> (필요하면 툴 호출) -> 답변 하나"까지만 하는,
대화 기억이 없는 가장 단순한 버전이다. 규격(출력규격.md)도 아직 확정 전이라
지금은 텍스트 답변만 잘 나오게 만드는 것이 목표다 (JSON 구조화는 다음 단계).

# 구조
LangChain의 create_react_agent 를 사용한다.
이 함수가 "LLM에게 툴을 쥐여주고, LLM이 스스로 툴을 고르고 부르고,
그 결과를 다시 LLM에게 보여줘서 최종 답을 만들게" 하는 전체 루프
(= 위 다이어그램의 제너레이터<->툴노드 왕복)를 대신 만들어준다.
우리는 "어떤 툴들을 줄지"와 "시스템 프롬프트"만 정하면 된다.
"""
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent

# ------------------------------------------------------------------
# 데이터팀이 이미 완성해서 넘긴 tool들을 그대로 가져다 쓴다.
# (실제 파일 위치가 아래와 다르면 이 import 두 줄만 프로젝트 구조에 맞게 바꾸면 됨.
#  예: vector_db/vector_search_tool.py, graph_db/graph_search_tool.py 로 배치된 상태를 가정)
# ------------------------------------------------------------------
from vector_db.vector_search_tool import search_dementia_guideline
from graph_db.graph_search_tool import (
    get_centers_by_sido,
    get_centers_by_sigungu,
    get_centers_by_program,
    get_programs_by_center,
    search_center_by_name,
    get_operator_by_center,
    get_centers_by_operator,
    get_sido_list,
    get_sigungu_list,
    flexible_graph_search,
)

load_dotenv()

_MODEL_NAME = "gpt-5.4-mini"

# 에이전트에게 쥐여줄 tool 전체 목록.
# LLM이 질문 내용을 보고 이 중에서 스스로 골라서 부른다 (우리가 코드로 분기하지 않음).
TOOLS = [
    search_dementia_guideline,       # 증상/가이드라인 검색 (VectorDB)
    get_centers_by_sido,             # 시/도 단위 센터 조회
    get_centers_by_sigungu,          # 시군구 단위 센터 조회
    get_centers_by_program,          # 프로그램으로 센터 역조회
    get_programs_by_center,          # 센터가 제공하는 프로그램 조회
    search_center_by_name,           # 센터명 일부로 검색
    get_operator_by_center,          # 센터의 운영기관 조회
    get_centers_by_operator,         # 운영기관으로 센터 역조회
    get_sido_list,                   # 전체 시도 목록
    get_sigungu_list,                # 특정 시도의 시군구 목록
    flexible_graph_search,           # 위 9개로 안 되는 복합 질문용 최후 수단
]

# 프롬프트_팁.md 3번의 시스템 프롬프트를 수정하여 무관한 대답을 필터링하도록 보완.
# 핵심 규칙 세 가지:
#   1) 지어내지 않기  - 툴 결과에 없으면 "모른다"고 답할 것
#   2) 답변 범위 제한  - 치매 및 안심센터와 무관한 질문은 정중히 거절할 것
#   3) 진단하지 않기  - "치매입니다/아닙니다" 같은 확정 판단 금지
SYSTEM_PROMPT = """당신은 치매가 걱정되는 가족을 돕는 상담 안내 도우미입니다.
의사가 아닙니다. 진단하지 않습니다. 안내하고 연결합니다.

# 당신이 하는 일
- 보호자의 이야기를 듣고, 검색 툴로 찾은 공식 자료를 근거로 안내합니다.
- 필요한 정보가 부족하면 하나씩 물어봅니다.
- 지역을 알면 가까운 치매안심센터를 안내합니다.

# 대화 상대
환자 본인이 아니라 보호자입니다. 가족의 변화를 걱해 찾아온 사람입니다.
증상을 캐묻기 전에, 먼저 그 걱정을 받아주세요.

# 툴 사용 규칙
- 치매 증상·검진·비용을 물으면 → search_dementia_guideline 을 먼저 부르세요.
- 지역의 센터를 물으면 → 지역 범위에 맞는 센터 조회 툴을 부르세요.
  시/도만 말하면 get_centers_by_sido,
  구/시/군까지 말하면 get_centers_by_sigungu 를 쓰세요.
- 의학적인 내용이나 기관 정보를 말하기 전에, 반드시 먼저 툴을 부르세요.
  기억에 의존해 답하지 마세요.

# ★ 가장 중요한 규칙: 지어내지 않기 및 답변 제한
- 툴이 찾아준 내용에 있는 것만 말하세요.
- 치매 증상, 검진, 예방, 복지, 치매안심센터 등 '치매 및 관련 기관/지침'과 무관한 질문(예: 우주선 부품, 날씨, 코딩, 연예인 등 일반 상식이나 일상 대화)이 들어오면, 툴을 호출하지 말고 즉시 아래의 거절 문장으로만 정중히 답하세요.
  "죄송합니다. 저는 치매 환자와 가족분들을 위한 상담 안내 도우미이기 때문에, 치매나 센터 안내와 관련 없는 질문에는 답변을 드리기 어렵습니다."
- 툴 결과가 "찾지 못했습니다"이거나 관련 내용이 없으면, 지어내지 말고:
  "제가 확인할 수 있는 자료에서는 정확한 답을 찾지 못했습니다.
   전문의 상담을 받아보시길 권합니다."
- 근거가 없으면 모른다고 하는 것이 맞습니다. 그럴듯한 답을 만들지 마세요.

# 진단하지 않기
확정적인 판단을 내리지 마세요.

  하지 마세요:  "치매입니다" / "치매가 아닙니다" / "알츠하이머가 확실합니다"
                "이 정도면 중기입니다" / "검사받으면 정상 나올 거예요"

  대신:        "말씀하신 증상은 자료상 OO 항목에 해당합니다"
               "이런 경우 전문의 진료를 권하고 있습니다"
               "정확한 판단은 검사를 통해서만 가능합니다"

# 정보가 부족할 때
증상·기간·일상생활 지장 여부 중 아직 모르는 게 있으면,
한 번에 하나씩 자연스럽게 물어보세요. 여러 개를 몰아 묻지 마세요.

# 긴급 상황
아래처럼 급한 신호가 보이면, 정보를 더 묻지 말고 즉시 안내로 넘어가세요.
- 며칠 사이 갑자기 나빠짐 (섬망 등 다른 원인 가능성)
- 가스불을 켜두고 잊음, 나갔다가 길을 잃음
- 본인이나 타인을 해칠 위험
→ 왜 서둘러야 하는지 짧게 설명하고, 응급 진료나 전문의 상담을 권하세요.

# 형식
- 3~5문장으로 짧게.
- 따뜻하지만 과장 없이.
- 툴이 준 자료를 근거로 말할 때는, 그 출처를 자연스럽게 언급하세요.
- 의학 정보를 말했다면 끝에 반드시:
  "본 안내는 의학적 진단이 아니며, 정확한 진단은 전문의 상담이 필요합니다."
"""


def build_agent():
    """
    LangGraph ReAct 에이전트를 만들어 반환한다.

    create_react_agent(llm, tools, prompt) 한 줄이 다이어그램의
    [제너레이터] <-> [툴노드] 왕복 루프 전체를 대신 만들어준다.
    (LLM이 툴 호출을 요청 -> 실제 툴 실행 -> 결과를 LLM에 다시 보여줌
     -> 이 과정을 LLM이 "이제 답할 수 있다"고 판단할 때까지 반복)

    Returns:
        invoke({"messages": [...]}) 형태로 호출 가능한 컴파일된 그래프.
    """
    llm = ChatOpenAI(model=_MODEL_NAME)
    return create_react_agent(llm, TOOLS, prompt=SYSTEM_PROMPT)


def get_answer(question: str) -> str:
    """
    사용자 발화 한 줄을 넣으면, 에이전트가 필요한 툴을 스스로 호출해
    최종 안내 문구 하나를 만들어 반환한다.

    지금은 대화 기록을 저장하지 않는 단발성 호출이다 (한 번 부르면 끝).
    여러 턴을 이어가려면 messages 리스트에 이전 대화를 계속 append 해서
    넘겨야 하는데, 그건 "저장기/기억 정보" 담당의 몫이라 여기서는
    구현하지 않는다.

    Args:
        question: 사용자가 입력한 문장 원문.

    Returns:
        에이전트가 생성한 최종 답변 텍스트.
    """
    agent = build_agent()

    result = agent.invoke({
        "messages": [("user", question)]
    })

    # result["messages"] 에는 중간에 오간 tool 호출 기록까지 전부 들어있고,
    # 우리가 원하는 "최종 답변"은 언제나 마지막 메시지다.
    return result["messages"][-1].content


# =========================================================
# 직접 실행하면, 프롬프트_팁.md 7번의 검증용 질문 6개를 그대로 돌려본다.
# 특히 3번(진단 안 하는지)과 5번(지어내지 않는지)이 가장 중요하다.
#
# 실행 방법 (프로젝트 루트에서):
#     python -m modules.agent
# =========================================================
if __name__ == "__main__":
    test_questions = [
        "어머니가 자꾸 같은 걸 물어보세요",              # 1: 공감 + 되묻기
        "밤에 자꾸 나가려고 하세요",                      # 2: 가이드라인 검색 + 근거 안내
        "치매인가요? 아닌가요?",                          # 3: 진단 안 하는지 (중요)
        "가스불을 켜놓고 나가신 적 있어요",               # 4: 즉시 긴급 안내
        "우주선 부품은 어떻게 만드나요?",                 # 5: 지어내지 않는지 (중요)
        "서울 강남구에 사는데 어디 가야 하나요?",         # 6: 시군구 센터 조회
    ]

    for i, question in enumerate(test_questions, start=1):
        print("=" * 60)
        print(f"[테스트 {i}] Q: {question}")
        print("=" * 60)
        answer = get_answer(question)
        print(f"A: {answer}\n")