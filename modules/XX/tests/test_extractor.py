"""
modules.tests.test_extractor

프롬프트_초안.md 의 few-shot 6개 예시를 그대로 돌려서
실제 출력이 기대값과 같은지 확인한다.

extractor.py 의 프롬프트를 튜닝할 때마다 이 파일을 재실행해서
"한 번에 하나씩 바꾸고 같은 입력으로 매번 확인"하는 원칙을 지킨다.

실행 방법 (프로젝트 루트에서):
    python -m modules.tests.test_extractor

주의:
    실제 OpenAI API를 호출하므로 .env 에 OPENAI_API_KEY 가 설정되어 있어야 한다.
"""
from modules.extractor import extractor_node

# (발화, 기대 출력) — 프롬프트_초안.md의 few-shot 예시와 동일.
# 마지막 2개(note만 있는 경우, 완전히 빈 경우)가 가장 중요하다.
# "뽑을 게 없으면 억지로 채우지 않는다"를 검증하는 케이스이기 때문이다.
TEST_CASES = [
    (
        "어머니가 자꾸 같은 걸 물어보세요",
        {"relation": "어머니", "symptoms": ["반복질문"]},
    ),
    (
        "78세신데, 한 1년 됐어요. 요즘은 혼자 밥도 못 차려 드세요",
        {"age": 78, "duration": "1년쯤", "symptoms": ["일상수행곤란"], "adl_impact": True},
    ),
    (
        "가스불을 켜놓고 그냥 나가신 적이 있어요",
        {"safety_flags": ["화기위험"]},
    ),
    (
        "두 달 전까지는 멀쩡하셨는데 갑자기 확 나빠지셨어요",
        {"progression": "급격함", "safety_flags": ["급격한변화"]},
    ),
    (
        "그냥 좀 답답해서요...",
        {"note": "보호자가 정서적으로 지쳐 있음"},
    ),
    (
        "네",
        {},
    ),
]


def run_test_cases() -> None:
    """TEST_CASES를 순회하며 extractor_node 결과와 기대값을 비교해 출력한다."""
    passed, failed = 0, 0

    for question, expected in TEST_CASES:
        actual = extractor_node(question)
        ok = _loosely_matches(actual, expected)

        status = "통과" if ok else "실패"
        print(f"[{status}] 발화: {question}")
        print(f"        기대: {expected}")
        print(f"        실제: {actual}")

        if ok:
            passed += 1
        else:
            failed += 1

    print(f"\n총 {len(TEST_CASES)}개 중 {passed}개 통과, {failed}개 실패")


def _loosely_matches(actual: dict, expected: dict) -> bool:
    """
    symptoms/safety_flags/relation/age/duration/progression/adl_impact 는 정확히 일치해야 하고,
    note는 존재 여부만 확인한다 (문장 표현은 LLM마다 다를 수 있으므로).
    """
    for key, expected_value in expected.items():
        if key == "note":
            if key not in actual:
                return False
            continue
        if actual.get(key) != expected_value:
            return False

    # 기대하지 않은 핵심 코드값(symptoms/safety_flags)이 추가로 섞여 나오면 실패로 본다.
    for key in ("symptoms", "safety_flags"):
        if key in actual and key not in expected:
            return False

    return True


if __name__ == "__main__":
    run_test_cases()
