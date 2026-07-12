"""
modules.db_qa

test.ipynb 에서 검증한 방식 그대로 GraphDB(Neo4j) / VectorDB(Qdrant)에
연결해서, 질문을 넣으면 실제 DB 데이터를 근거로 답변이 나오는지 확인하는 파일.

지금은 "페르소나/가드레일 프롬프트"는 넣지 않았다.
(프롬프트 규격 문서 내용이 바뀔 예정이라, 그 부분과 무관하게
 DB 연결 자체가 잘 되는지만 먼저 확인하기 위함)

나중에 정식 규격이 나오면, 여기 있는 get_graph_chain() / get_vector_chain()
두 함수는 그대로 재사용하고, 답변 생성 부분(프롬프트)만 responder.py 로
옮겨서 다듬으면 된다.

실행 방법 (프로젝트 루트에서):
    python -m modules.db_qa
"""
import os

from dotenv import load_dotenv
from langchain_core.prompts import PromptTemplate
from langchain_neo4j import GraphCypherQAChain, Neo4jGraph
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_qdrant import QdrantVectorStore
from qdrant_client import QdrantClient

# override=True: OS에 같은 이름의 환경변수가 이미 있어도 .env 값으로 덮어쓴다.
# (테스트 중 예전 값이 남아있어서 헷갈리는 걸 방지)
load_dotenv(override=True)

_MODEL_NAME = "gpt-5.4-mini"
_EMBEDDING_MODEL = "text-embedding-3-small"

# Qdrant 컬렉션 이름 — 영선님이 실제로 적재한 컬렉션 이름과 같아야 한다.
# 다르면 .env 에 QDRANT_COLLECTION_NAME 값을 실제 이름으로 넣어줄 것.
_QDRANT_COLLECTION_NAME = os.getenv("QDRANT_COLLECTION_NAME", "dementia_guides")


# =========================================================
# 1. GraphDB(Neo4j) 연결 — test.ipynb 검증 코드 그대로
# =========================================================

def get_graph_chain() -> GraphCypherQAChain:
    """
    Neo4j에 연결해서 "자연어 질문 -> Cypher 쿼리 -> 조회 -> 자연어 답변"까지
    한 번에 처리해주는 체인을 만든다.

    test.ipynb 에서 5개 질문 중 4개가 정상 조회되는 것을 이미 확인한 코드다.
    """
    # 1) Neo4j 접속
    graph = Neo4jGraph(
        url=os.getenv("NEO4J_URI"),
        username=os.getenv("NEO4J_USERNAME"),
        password=os.getenv("NEO4J_PASSWORD"),
        database=os.getenv("NEO4J_DATABASE"),
    )

    llm = ChatOpenAI(model=_MODEL_NAME)

    # 2) "질문 -> Cypher" 변환 규칙.
    #    CLAUDE.md 의 관계 방향 규칙을 명시하지 않으면 LLM이 방향을 반대로 짜서
    #    쿼리가 항상 빈 결과([])를 내는 문제가 있었다 (방향 규칙을 넣은 뒤 해결됨).
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

    return GraphCypherQAChain.from_llm(
        llm=llm,
        graph=graph,
        cypher_prompt=cypher_prompt,
        verbose=True,  # 생성된 Cypher 쿼리를 콘솔에 같이 보여줘서 디버깅하기 좋다.
        allow_dangerous_requests=True,  # 실제로 DB에 쿼리를 날리는 체인이라 명시적으로 켜야 함.
    )


# =========================================================
# 2. VectorDB(Qdrant) 연결
# =========================================================

def get_vector_chain(top_k: int = 3):
    """
    Qdrant에 연결해서 "질문 -> 관련 문서 검색 -> 그 문서를 근거로 답변"까지
    처리해주는 함수를 만든다.

    (참고: langchain.chains.RetrievalQA는 최신 langchain에서 제거된
     legacy chain이라, GraphDB 체인과 동일한 방식으로 직접 만들었다.
     retriever + LLM 조합이라 오히려 동작 방식이 눈에 더 잘 보인다.)

    반환값은 함수(vector_qa)이고, graph_chain과 호출 방식을 맞추기 위해
    vector_qa({"query": "질문"}) -> {"result": "답변"} 형태로 쓸 수 있게 했다.
    """
    # 1) Qdrant 서버 접속
    client = QdrantClient(
        url=os.getenv("QDRANT_URL"),
        api_key=os.getenv("QDRANT_API_KEY"),
    )

    # 2) 질문/문서를 같은 벡터 공간으로 바꿔줄 임베딩 모델.
    #    문서를 Qdrant에 넣을 때 쓴 모델과 반드시 같아야 검색이 정확하다.
    embeddings = OpenAIEmbeddings(model="text-embedding-3-small", dimensions=1024)

    # 3) 이미 만들어진 컬렉션에 연결 (새로 만드는 게 아니라 기존 것 사용)
    vector_store = QdrantVectorStore(
        client=client,
        collection_name=_QDRANT_COLLECTION_NAME,
        embedding=embeddings,
        content_payload_key="text",
    )
    retriever = vector_store.as_retriever(search_kwargs={"k": top_k})

    llm = ChatOpenAI(model=_MODEL_NAME, temperature=0)

    # 문서에 없는 내용을 지어내지 말라는 최소한의 규칙만 포함한 프롬프트.
    # (자세한 페르소나/금지어 규칙은 규격이 확정되면 별도로 추가)
    qa_prompt = PromptTemplate(
        input_variables=["context", "question"],
        template="""아래 [문서]에 있는 내용만 근거로 질문에 답하세요.
문서에 없는 내용은 지어내지 말고, "문서에서 관련 내용을 찾지 못했습니다"라고 답하세요.

[문서]
{context}

[질문]
{question}

[답변]""",
    )

    def vector_qa(inputs: dict) -> dict:
        """graph_chain.invoke({"query": ...}) 와 같은 방식으로 쓸 수 있게 만든 함수."""
        question = inputs["query"]

        # 1) 질문과 의미상 비슷한 문서 chunk를 top_k개 가져온다.
        docs = retriever.invoke(question)
        context = "\n\n".join(doc.page_content for doc in docs) if docs else "(검색된 문서 없음)"

        # 2) 문서 내용을 근거로 답변을 생성한다.
        prompt_text = qa_prompt.format(context=context, question=question)
        response = llm.invoke(prompt_text)

        return {"result": response.content, "source_documents": docs}

    return vector_qa


# =========================================================
# 3. 직접 실행하면 GraphDB / VectorDB 각각 테스트 질문을 돌려본다.
#    (test.ipynb 와 같은 형태: Q -> 생성된 쿼리/검색 로그 -> A 순서로 출력)
# =========================================================
if __name__ == "__main__":
    graph_chain = get_graph_chain()
    vector_chain = get_vector_chain()

    print("=" * 50)
    print("GraphDB 테스트")
    print("=" * 50)

    graph_test_queries = [
        "서울에 치매안심센터 몇 개야?",
        "제주도 치매안심센터 전화번호 알려줘",
    ]
    for query in graph_test_queries:
        print(f"\nQ: {query}")
        result = graph_chain.invoke({"query": query})
        print(f"A: {result['result']}")
        print("---")

    print("\n" + "=" * 50)
    print("VectorDB 테스트")
    print("=" * 50)

    vector_test_queries = [
        
        "치매 조기 검진은 비용은 얼마인가요?",
        
    ]
    for query in vector_test_queries:
        print(f"\nQ: {query}")
        result = vector_chain({"query": query})
        print(f"A: {result['result']}")
        print("---")
