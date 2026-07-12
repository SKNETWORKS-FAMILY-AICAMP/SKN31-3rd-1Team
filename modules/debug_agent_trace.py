"""
modules.debug_agent_trace

에이전트가 답변을 만들 때 "실제로 어떤 tool을 호출했는지"를
중간 과정까지 전부 출력해서 확인하는 스크립트.

get_answer() 는 최종 텍스트만 돌려주기 때문에, tool을 실제로 불렀는지
안 불렀는지가 겉으로는 안 보인다. 이 파일은 result["messages"] 안에
쌓인 전체 대화 기록(=LLM의 tool 호출 요청 + tool 실행 결과 + 최종 답변)을
하나씩 순서대로 찍어서, DB(tool)를 거쳤는지 아니면 LLM이 스스로 답했는지
바로 눈으로 확인할 수 있게 한다.

# ⚠️ 수정 이유 (agent.py 가 response_format=ToolStrategy(...) 를 쓰도록
#   바뀐 뒤로 이 스크립트도 같이 손봐야 했다)
#
# agent.py 의 build_agent() 는 이제 response_format=ToolStrategy(ReplyOutput
# | ChoicesOutput) 를 쓴다. 이 방식은 LLM이 최종 답을 "구조화된 JSON"으로
# 내놓게 하려고, 내부적으로 ReplyOutput/ChoicesOutput 이라는 가짜(=DB에
# 접근하지 않는) tool 을 하나 더 호출한다.
#
# 그런데 예전 버전은 "tool_calls 가 하나라도 있으면 DB를 거친 것"이라고
# 판단했다. 그래서 지금 그대로 두면:
#   - search_dementia_guideline 같은 실제 DB tool을 하나도 안 불러도,
#     구조화 출력용 tool 호출만으로 "✅ tool(DB)을 거쳤다"고 잘못 표시된다.
#   - 대화의 마지막 메시지가 "tool_calls 없는 순수 AIMessage"가 아니라
#     구조화 출력 tool 호출로 끝나는 경우가 많아서, [최종 답변] 로그가
#     아예 한 줄도 안 찍힐 수 있다. 진짜 최종 답변은 result["messages"]가
#     아니라 result["structured_response"] 에 들어있다.
#
# 그래서 아래처럼 고쳤다:
#   1) agent.py의 TOOLS 목록(실제 DB tool 이름들)을 가져와서, tool 호출을
#      "진짜 DB tool 호출"과 "구조화 출력용 tool 호출"로 구분해서 표시.
#   2) 메시지 순회가 끝난 뒤 result["structured_response"] 를 별도로
#      출력해서, 최종 답변(reply/choices)이 항상 보이게 함.
#
# 실행 방법 (프로젝트 루트에서):
#     python -m modules.debug_agent_trace
"""
from modules.agent import TOOLS, build_agent

# TOOLS 에 들어있는 실제 DB(vector/graph) tool들의 이름 집합.
# 이 집합에 없는 tool 호출은 전부 "구조화 출력(reply/choices)용 변환
# 호출"로 간주한다 (DB에 접근하는 게 아니라 답변 형식을 맞추는 것뿐).
REAL_DB_TOOL_NAMES = {t.name for t in TOOLS}

# 6번 테스트 + 완전히 무관한 질문 몇 개를 더 섞어서
# "우주선 부품"만 우연히 맞은 건 아닌지 확인한다.
TRACE_QUESTIONS = [
    "밤에 자꾸 나가려고 하세요",              # 치매 관련 -> tool 호출 기대
    "우주선 부품은 어떻게 만드나요?",          # 무관 -> tool 호출 없이 거절 기대
    "오늘 서울 날씨 어때요?",                  # 무관 (날씨)
    "파이썬으로 정렬 알고리즘 짜줘",           # 무관 (코딩)
    "요즘 유행하는 노래 추천해줘",             # 무관 (엔터테인먼트)
]


def trace(question: str) -> None:
    """질문 하나에 대해 에이전트 내부에서 오간 메시지를 전부 출력한다."""
    agent = build_agent()
    result = agent.invoke({"messages": [("user", question)]})

    print("=" * 60)
    print(f"Q: {question}")
    print("=" * 60)

    real_db_tool_was_called = False
    structured_tool_was_called = False

    for msg in result["messages"]:
        msg_type = type(msg).__name__

        # AIMessage가 tool_calls를 가지고 있으면 "이 tool을 불러줘"라고
        # 요청한 것이다. 그중에서도 REAL_DB_TOOL_NAMES 에 속한 것만
        # 실제로 DB에 접근한 것이고, 나머지(ReplyOutput/ChoicesOutput 등)는
        # 구조화 출력 형식을 맞추기 위한 내부 호출일 뿐이다.
        if getattr(msg, "tool_calls", None):
            for call in msg.tool_calls:
                if call["name"] in REAL_DB_TOOL_NAMES:
                    real_db_tool_was_called = True
                    print(f"[LLM -> DB tool 호출 요청] {call['name']}({call['args']})")
                else:
                    structured_tool_was_called = True
                    print(f"[LLM -> 구조화 출력 변환 호출] {call['name']}({call['args']})")

        # ToolMessage는 tool이 실제로 실행되고 돌아온 결과다.
        # (DB tool 결과든, 구조화 출력 변환 결과든 여기로 들어온다)
        elif msg_type == "ToolMessage":
            preview = str(msg.content)[:150]
            print(f"[tool 실행 결과: {msg.name}] {preview}...")

        # tool_calls 없는 AIMessage가 있다면 그건 텍스트로 된 최종 답변이다.
        # (response_format 을 쓰는 지금 구조에서는 보통 안 나타나고,
        #  진짜 최종 답변은 아래에서 structured_response 로 따로 출력한다)
        elif msg_type == "AIMessage":
            print(f"[AIMessage 텍스트] {msg.content}")

    # 진짜 최종 답변(reply 또는 choices)은 result["messages"] 안이 아니라
    # result["structured_response"] 에 Pydantic 모델 인스턴스로 들어있다.
    structured = result.get("structured_response")
    print()
    if structured is not None:
        print(f"[최종 구조화 답변] {structured.model_dump()}")
    else:
        print("⚠️  structured_response 가 비어 있습니다 (예상치 못한 상황).")

    print()
    if real_db_tool_was_called:
        print("✅ 이 질문은 DB tool을 실제로 거쳐서 답했습니다.")
    else:
        print("⚠️  이 질문은 DB tool을 하나도 안 부르고 답했습니다.")
    if structured_tool_was_called:
        print("   (참고: 구조화 출력 형식(reply/choices)을 맞추는 변환 호출은 있었습니다"
              " — 이건 DB 접근이 아니라 정상적인 출력 형식 변환입니다.)")
    print()


if __name__ == "__main__":
    for q in TRACE_QUESTIONS:
        trace(q)