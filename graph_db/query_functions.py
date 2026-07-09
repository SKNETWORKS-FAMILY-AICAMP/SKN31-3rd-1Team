import requests
import os
from dotenv import load_dotenv

load_dotenv()

# HTTP Query API 사용 (Bolt 포트 대신 HTTPS 443 포트 사용)
QUERY_URL = os.getenv('NEO4J_QUERY_URL')
AUTH = (os.getenv('NEO4J_USERNAME'), os.getenv('NEO4J_PASSWORD'))


def run_query(statement: str, parameters: dict = {}) -> list[dict]:
    """Neo4j Cypher 쿼리 실행 후 결과 반환"""
    response = requests.post(
        QUERY_URL,
        auth=AUTH,
        json={"statement": statement, "parameters": parameters}
    )
    data = response.json()
    fields = data['data']['fields']
    values = data['data']['values']
    return [dict(zip(fields, row)) for row in values]


def get_centers_by_sido(sido: str) -> list[dict]:
    """시도명으로 치매안심센터 목록 조회"""
    return run_query("""
        MATCH (c:치매안심센터)-[:LOCATED_IN]->(:시군구)-[:CONTAINS]->(:시도 {시도명: $시도})
        RETURN c.센터명 AS 센터명, c.주소 AS 주소, c.전화번호 AS 전화번호
        ORDER BY c.센터명
    """, {"시도": sido})


def get_centers_by_sigungu(sido: str, sigungu: str) -> list[dict]:
    """시도 + 시군구로 치매안심센터 조회"""
    return run_query("""
        MATCH (c:치매안심센터)-[:LOCATED_IN]->(:시군구 {시군구명: $시군구})-[:CONTAINS]->(:시도 {시도명: $시도})
        RETURN c.센터명 AS 센터명, c.주소 AS 주소, c.전화번호 AS 전화번호, c.팩스번호 AS 팩스번호
    """, {"시도": sido, "시군구": sigungu})


def get_sido_list() -> list[str]:
    """전체 시도 목록 조회"""
    result = run_query("MATCH (sd:시도) RETURN sd.시도명 AS 시도명 ORDER BY sd.시도명")
    return [r['시도명'] for r in result]


def get_sigungu_list(sido: str) -> list[str]:
    """특정 시도의 시군구 목록 조회"""
    result = run_query("""
        MATCH (sg:시군구)-[:CONTAINS]->(:시도 {시도명: $시도})
        RETURN sg.시군구명 AS 시군구명
        ORDER BY sg.시군구명
    """, {"시도": sido})
    return [r['시군구명'] for r in result]


def search_center_by_name(keyword: str) -> list[dict]:
    """센터명 키워드로 검색"""
    return run_query("""
        MATCH (c:치매안심센터)
        WHERE c.센터명 CONTAINS $keyword
        RETURN c.센터명 AS 센터명, c.주소 AS 주소, c.전화번호 AS 전화번호
    """, {"keyword": keyword})


if __name__ == "__main__":
    print("=== 시도 목록 ===")
    print(get_sido_list())

    print("\n=== 서울 센터 수 ===")
    result = get_centers_by_sido("서울특별시")
    print(f"{len(result)}개")

    print("\n=== 강남구 센터 ===")
    print(get_centers_by_sigungu("서울특별시", "강남구"))
