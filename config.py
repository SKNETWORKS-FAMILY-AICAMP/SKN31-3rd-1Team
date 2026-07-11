"""프로젝트 전역 설정 상수 모듈.

graph_db/, vector_db/, modules/(LangGraph 파이프라인)에서 공통으로 쓰는
모델명, 경로, DB 접속 정보 등을 모아둔다.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# --- 경로 설정 ---
BASE_DIR = Path(__file__).resolve().parent  # 프로젝트 root 경로
# Path(__file__).resolve().parent: config.py가 있는 폴더(=프로젝트 루트)

GRAPH_DB_DIR = BASE_DIR / "graph_db"
GRAPH_DATA_RAW_DIR = GRAPH_DB_DIR / "data" / "raw"
GRAPH_DATA_PROCESSED_DIR = GRAPH_DB_DIR / "data" / "processed"

VECTOR_DB_DIR = BASE_DIR / "vector_db"


# --- 모델 설정 ---
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-5.4-mini")
# flexible_graph_search(그래프 fallback tool) 전용 LLM. 기본은 LLM_MODEL과 동일하게 두되,
# 필요하면 .env에서 FALLBACK_LLM_MODEL만 따로 override 할 수 있다.
FALLBACK_LLM_MODEL = os.getenv("FALLBACK_LLM_MODEL", LLM_MODEL)
# 벡터DB 임베딩 모델. Qdrant 적재 때 쓴 모델과 반드시 동일해야 검색이 정상 작동한다.
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "BAAI/bge-m3")
EMBEDDING_DIMS = 1024


# --- Neo4j (GraphDB) 설정 ---
NEO4J_URI = os.getenv("NEO4J_URI")
NEO4J_USERNAME = os.getenv("NEO4J_USERNAME")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")
NEO4J_DATABASE = os.getenv("NEO4J_DATABASE")
# --- GraphDB 조회 결과 상한 ---
RESULT_LIMIT_DEFAULT = 200


# --- Qdrant (VectorDB) 설정 ---
QDRANT_URL = os.getenv("QDRANT_URL")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")
VECTOR_COLLECTION_NAME = "dementia_guideline"
VECTOR_TOP_K_DEFAULT = 4
VECTOR_SCORE_THRESHOLD = 0.4  # 코사인 유사도 기준, 너무 낮은 관련도 결과는 제외


# --- Supabase (사용자 인증 / 대화 컨텍스트 보관) 설정 ---
# --- 장단기 메모리 Database 파일 경로 (=> Supabase-PostSql)
# 아직 실제 인증 로직은 구현 전. .env에 값만 채워두면 이후 auth 모듈에서 바로 가져다 쓸 수 있다.
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
