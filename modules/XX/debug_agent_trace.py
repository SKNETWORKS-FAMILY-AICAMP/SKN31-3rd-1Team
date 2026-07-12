"""
modules.debug_agent_trace

에이전트가 답변을 만들 때 "실제로 어떤 tool을 호출했는지"를
중간 과정까지 전부 출력해서 확인하는 스크립트.

get_answer() 는 최종 텍스트만 돌려주기 때문에, tool을 실제로 불렀는지
안 불렀는지가 겉으로는 안 보인다. 이 파일은 result["messages"] 안에
쌓인 전체 대화 기록(=LLM의 tool 호출 요청 + tool 실행 결과 + 최종 답변)을
하나씩 순서대로 찍어서, DB(tool)를 거쳤는지 아니면 LLM이 스스로 답했는지
바로 눈으로 확인할 수 있게 한다.

실행 방법 (프로젝트 루트에서):
    python -m modules.debug_agent_trace
"""
from modules.agent import build_agent

# 6번 테스트 + 완전히 무관한 질문 몇 개를 더 섞어서
# "우주선 부품"만 우연히 맞은 건 아닌지 확인한다.
TRACE_QUESTIONS = [
    "밤에 자꾸 나가려고 하세요",              # 치매 관련 -> tool 호출 기대
    "우주선 부품은 어떻게 만드나요?",          # 무관 -> tool 호출 + 거절 기대
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

    tool_was_called = False

    for msg in result["messages"]:
        msg_type = type(msg).__name__

        # AIMessage가 tool_calls를 가지고 있으면 "이 tool을 불러줘"라고
        # 요청한 것이다. 이게 있어야 실제로 DB에 접근한 것이다.
        if getattr(msg, "tool_calls", None):
            tool_was_called = True
            for call in msg.tool_calls:
                print(f"[LLM -> tool 호출 요청] {call['name']}({call['args']})")

        # ToolMessage는 tool이 실제로 실행되고 돌아온 결과다.
        elif msg_type == "ToolMessage":
            preview = str(msg.content)[:150]
            print(f"[tool 실행 결과: {msg.name}] {preview}...")

        # 마지막 AIMessage(=tool_calls 없는 것)가 최종 답변이다.
        elif msg_type == "AIMessage":
            print(f"[최종 답변] {msg.content}")

    print()
    if tool_was_called:
        print("✅ 이 질문은 tool(DB)을 실제로 거쳐서 답했습니다.")
    else:
        print("⚠️  이 질문은 tool을 하나도 안 부르고, LLM이 스스로 답했습니다.")
    print()


if __name__ == "__main__":
    for q in TRACE_QUESTIONS:
        trace(q)
