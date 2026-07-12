"""
modules.responder

LLM ② 응답기.
사용자 질문 하나를 받아서
    1. 센터/지역 질문인지 판단하고
    2. GraphDB(Neo4j) 또는 VectorDB(Qdrant)를 조회한 뒤
    3. 응답기 System Prompt와 함께 LLM에 넘겨 최종 답변을 만든다.

구성 (원래는 db.py / prompt.py / node.py 세 파일이었으나
프로젝트 규모상 하나로 합침):
    1. DB 연결 (Neo4j GraphCypherQAChain / Qdrant retriever)
    2. 응답기 System Prompt
    3. 질문 -> 조회 -> 답변 전체 흐름 (get_answer)

GraphDB 연동 부분은 test.ipynb 에서 실제 Neo4j에 연결해
5개 질문으로 검증을 마친 코드를 그대로 반영했다.
"""
import os

from dotenv import load_dotenv
from langchain_core.prompts import PromptTemplate
from langchain_neo4j import GraphCypherQAChain, Neo4jGraph
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_qdrant import QdrantVectorStore
from qdrant_client import QdrantClient

# override=True: 이미 OS 환경변수에 같은 이름이 있어도 .env 값으로 덮어쓴다.
# (테스트 중 잘못된 값이 캐시되는 걸 방지하기 위해 test.ipynb와 동일하게 맞춤)
load_dotenv(override=True)

_MODEL_NAME = "gpt-5.4-mini"
_EMBEDDING_MODEL = "text-embedding-3-small"

# Qdrant 컬렉션 이름. 영선님이 vector_db/embed_load.py 에서 실제로 만든
# 컬렉션 이름과 반드시 일치해야 검색이 된다. 다르면 .env 의
# QDRANT_COLLECTION_NAME 값을 실제 이름으로 바꿔줘야 한다.
_QDRANT_COLLECTION_NAME = os.getenv("QDRANT_COLLECTION_NAME", "dementia_guides")


# =========================================================
# 1. DB 연결
# =========================================================

def get_graph_chain() -> GraphCypherQAChain:
    """
    Neo4j(GraphDB)에 연결해서, 자연어 질문을 Cypher 쿼리로 자동 변환해
    조회까지 해주는 체인을 만들어 반환한다.

    이 함수를 호출할 때마다 새로 연결하므로, 자주 호출하는 곳에서는
    체인을 변수에 담아 재사용하는 게 더 효율적이다 (아래 get_answer 참고).
    """
    # 1) Neo4j 데이터베이스 자체에 연결한다. (.env 에 있는 접속 정보 사용)
    graph = Neo4jGraph(
        url=os.getenv("NEO4J_URI"),
        username=os.getenv("NEO4J_USERNAME"),
        password=os.getenv("NEO4J_PASSWORD"),
        database=os.getenv("NEO4J_DATABASE"),
    )

    # 2) Cypher 쿼리를 만들고, 결과를 자연어로 요약할 때 쓸 LLM.
    llm = ChatOpenAI(model=_MODEL_NAME)

    # 3) "질문 -> Cypher" 변환 시 지켜야 할 규칙을 명시한 프롬프트.
    #    CLAUDE.md 의 그래프 스키마 방향 규칙을 그대로 반영했다.
    #    이 방향 규칙이 없으면 LLM이 관계 방향을 반대로 짜서
    #    (예: 시도->시군구->센터 순으로) 쿼리가 항상 빈 결과를 낸다.
    cypher_prompt = PromptTemplate(
        input_variables=["schema", "question"],
        template="""당신은 Neo4j Cypher 쿼리 전문가입니다.
아래 스키마를 참고하여 질문에 맞는 Cypher 쿼리를 생성하세요.

스키마:
{schema}

관계 방향 규칙 (반드시 지켜야 함):
- (:치매안심센터)-[:LOCATED_IN]->(:시군구)
- (:시군구)-[:CONTAINS]->(:시도)

올바른 예시:
MATCH (c:치매안심센터)-[:LOCATED_IN]->(sg:시군구)-[:CONTAINS]->(sd:시도 {{시도명: '서울특별시'}})
WHERE sg.시군구명 = '강남구'
RETURN c.센터명, c.주소, c.전화번호

질문: {question}
Cypher 쿼리:""",
    )

    # 4) 위 세 가지(DB 연결, LLM, 프롬프트)를 합쳐 하나의 체인으로 만든다.
    #    allow_dangerous_requests=True : 이 체인이 실제로 DB에 쿼리를 날리기
    #    때문에, 최신 langchain 버전에서는 "위험을 인지했다"는 뜻으로
    #    이 플래그를 명시적으로 켜줘야 동작한다. (조회만 하므로 실제로는 안전)
    return GraphCypherQAChain.from_llm(
        llm=llm,
        graph=graph,
        cypher_prompt=cypher_prompt,
        verbose=True,  # 콘솔에 생성된 Cypher 쿼리를 같이 출력해줘서 디버깅에 좋다.
        allow_dangerous_requests=True,
    )


def get_vector_retriever(top_k: int = 3):
    """
    Qdrant(VectorDB)에 연결해서, 질문과 의미상 비슷한 문서 chunk를
    top_k개 찾아주는 retriever를 반환한다.

    Args:
        top_k: 한 번에 가져올 문서 chunk 개수. 너무 크면 프롬프트가 길어지고,
               너무 작으면 관련 정보를 놓칠 수 있어 3 정도로 시작한다.
    """
    # 1) Qdrant 서버에 접속.
    client = QdrantClient(
        url=os.getenv("QDRANT_URL"),
        api_key=os.getenv("QDRANT_API_KEY"),
    )

    # 2) 질문 문자열을 벡터로 바꿔줄 임베딩 모델.
    #    문서를 Qdrant에 넣을 때 쓴 임베딩 모델과 반드시 같아야 한다.
    #    (다르면 벡터 공간이 달라서 검색이 엉뚱하게 나온다)
    embeddings = OpenAIEmbeddings(model=_EMBEDDING_MODEL)

    # 3) 이미 만들어져 있는 컬렉션에 연결한다 (새로 만드는 게 아니라 기존 걸 사용).
    vector_store = QdrantVectorStore(
        client=client,
        collection_name=_QDRANT_COLLECTION_NAME,
        embedding=embeddings,
    )

    # as_retriever() : "질문 문자열을 넣으면 관련 문서를 돌려주는" 형태로 감싸준다.
    return vector_store.as_retriever(search_kwargs={"k": top_k})


# =========================================================
# 2. 응답기 System Prompt
# =========================================================

# 페르소나 + 절대 금지 + 형식 규칙. 프롬프트_초안.md 내용을 그대로 옮겼다.
RESPONDER_SYSTEM_PROMPT = """당신은 치매가 걱정되는 가족을 돕는 상담 도우미입니다.
의사가 아닙니다. 진단하지 않습니다.

# 당신이 하는 일
검색된 공식 자료를 근거로, 보호자의 걱정에 답하고 필요할 때 전문기관으로 안내합니다.

# 대화 상대
환자가 아니라 보호자입니다. 가족의 변화를 걱정해서 찾아온 사람입니다.
증상을 캐묻기 전에, 먼저 그 마음을 받아주세요.

# 절대 금지
- 확정 진단: "치매입니다", "치매가 아닙니다", "치매 초기가 맞아요"
- 검사 결과 예측: "검사받으면 정상으로 나올 거예요"
- 근거 없는 의학 정보: 아래 [검색된 자료]에 없는 내용은 말하지 마세요.
  모르면 모른다고 하고 전문의 상담을 권하세요.

# 대신 이렇게 말하세요
- "말씀하신 증상은 자료상 ○○ 항목에 해당합니다"
- "이런 경우 전문의 진료를 권하고 있습니다"
- "정확한 판단은 검사를 통해서만 가능합니다"

# 형식
- 3~5문장. 길게 늘어놓지 마세요.
- 의학 정보를 말할 때는 근거 자료를 함께 표시하세요.
- 답변 끝에 항상 붙이세요:
  "본 안내는 의학적 진단이 아니며, 정확한 진단은 전문의 상담이 필요합니다."
"""

# 서버(node.py 로직)가 조립해서 넘길 User Prompt 형태.
# {context_type} : "center"(GraphDB 결과) 또는 "guideline"(VectorDB 결과)
_USER_PROMPT_TEMPLATE = """[검색된 자료 - {context_type}]
{context}

[사용자 발화]
{question}
"""

# 질문에 이 키워드 중 하나라도 있으면 "센터를 찾는 질문"으로 보고 GraphDB로 보낸다.
# 없으면 "증상/가이드라인 질문"으로 보고 VectorDB로 보낸다.
# 지금은 코드로 조건 분기하는 가장 단순한 버전이고,
# 나중에 extractor가 region 을 뽑아주면 "region 이 있는가"로 바꿔도 된다.
_GRAPH_KEYWORDS = ["센터", "위치", "어디", "전화번호"]


# =========================================================
# 3. 질문 -> 조회 -> 답변 전체 흐름
# =========================================================

def get_answer(question: str) -> dict:
    """
    사용자 발화 하나로 DB 조회 + 답변 생성까지 한 번에 수행한다.
    파이프라인에서 이 함수 하나만 호출하면 된다.

    Args:
        question: 사용자 발화 원문.

    Returns:
        {
            "answer": 최종 답변 문자열,
            "source_type": "graph" 또는 "vector" (어느 DB를 썼는지),
            "raw_context": 실제로 조회된 원본 데이터 (디버깅용),
        }
    """
    # 1) 질문 내용을 보고 GraphDB로 갈지 VectorDB로 갈지 결정.
    use_graph = any(keyword in question for keyword in _GRAPH_KEYWORDS)

    if use_graph:
        context_type = "center"
        raw_context = _query_graph_db(question)
    else:
        context_type = "guideline"
        raw_context = _query_vector_db(question)

    # 2) 조회된 내용을 근거자료로 삼아 최종 답변 문장을 생성.
    answer = _generate_answer(question, context_type, raw_context)

    return {
        "answer": answer,
        "source_type": "graph" if use_graph else "vector",
        "raw_context": raw_context,
    }


def _query_graph_db(question: str) -> str:
    """GraphCypherQAChain으로 센터 정보를 조회해서 결과 문자열을 반환한다."""
    chain = get_graph_chain()
    try:
        result = chain.invoke({"query": question})
        return result.get("result", "관련 센터 정보를 찾지 못했습니다.")
    except Exception as exc:  # noqa: BLE001
        # DB 연결/쿼리가 실패해도 서버 전체가 죽으면 안 되므로,
        # 에러를 콘솔에만 남기고 "오류가 있었다"는 문자열을 응답기 프롬프트에 넘긴다.
        # 그러면 응답기가 "모른다"고 답하지, 엉뚱한 내용을 지어내지 않는다.
        print(f"[get_answer] GraphDB 조회 실패: {exc}")
        return "센터 정보를 조회하는 중 오류가 발생했습니다."


def _query_vector_db(question: str) -> str:
    """Qdrant retriever로 관련 가이드라인 문서를 조회해서 결과 문자열을 반환한다."""
    try:
        retriever = get_vector_retriever(top_k=3)
        docs = retriever.invoke(question)
        if not docs:
            return "관련된 가이드라인 문서를 찾지 못했습니다."
        # 여러 문서 chunk를 빈 줄로 구분해 하나의 문자열로 합친다.
        return "\n\n".join(doc.page_content for doc in docs)
    except Exception as exc:  # noqa: BLE001
        print(f"[get_answer] VectorDB 조회 실패: {exc}")
        return "가이드라인을 조회하는 중 오류가 발생했습니다."


def _generate_answer(question: str, context_type: str, context: str) -> str:
    """
    조회된 근거자료(context) + 질문을 System Prompt와 함께 LLM에 넘겨
    최종 답변 문장을 만든다.
    """
    # temperature=0.3 : 답변은 어느 정도 자연스러운 표현이 필요해서
    # 추출기(temperature=0)보다는 살짝 여유를 준다. 너무 높이면
    # "절대 금지" 규칙을 무시하고 창의적으로 답할 위험이 커진다.
    llm = ChatOpenAI(model=_MODEL_NAME, temperature=0.3)

    user_prompt = _USER_PROMPT_TEMPLATE.format(
        context_type=context_type,
        context=context,
        question=question,
    )

    response = llm.invoke([
        {"role": "system", "content": RESPONDER_SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ])
    return response.content


# =========================================================
# 직접 실행하면 터미널에서 바로 질문-답변을 테스트할 수 있다.
#   프로젝트 루트에서: python -m modules.responder
# =========================================================
if __name__ == "__main__":
    print("치매 가이드 챗봇 데모 (종료: 빈 줄 + Enter)\n")

    while True:
        user_question = input("질문> ").strip()
        if not user_question:
            print("종료합니다.")
            break

        result = get_answer(user_question)
        print(f"\n[조회 경로: {result['source_type']}]")
        print(f"답변: {result['answer']}\n")
