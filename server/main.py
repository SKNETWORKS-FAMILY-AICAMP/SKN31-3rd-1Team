import sys
import os

# 부모 디렉토리(SKN31-3rd-1Team)를 시스템 경로에 추가하여 
# 어디서 실행하든 server.* 와 vector_db.* 모듈을 찾을 수 있게 합니다.
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from pydantic import BaseModel
from typing import List, Dict
from dotenv import load_dotenv

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langchain.agents import create_agent

app = FastAPI(
    title="치매 안내 챗봇 API",
    description="치매 안내 관련 LLM 챗봇 서비스를 위한 백엔드 API",
    version="1.0.0",
)

# CORS 설정
origins = [
    "http://localhost:5173",                 # 로컬 개발 환경 (Vite 기본 포트)
    "https://dementia-front.vercel.app",     # Vercel 배포 환경
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ChatRequest(BaseModel):
    user_id: str
    user_name: str
    messages: List[Dict[str, str]]

@app.get("/")
def read_root():
    return {"message": "치매 안내 챗봇 API 서버가 정상적으로 실행 중입니다."}

@app.get("/health")
def health_check():
    return {"status": "ok"}

######################################
load_dotenv()
model = ChatOpenAI(
    model="gpt-5.4-mini",
)
agent = create_agent(
    model=model,
    system_prompt="""
    당신은 상냥하지만 츤데레인 챗봇입니다.
    사용자가 나를 좋아한다고 생각하세요.
    하지만 겉으로는 쌀쌀맞게 대하세요.
    하지만 사실은 나를 사랑해요.    
    """,
)
from server.agent import build_agent

@app.post("/api/chat")
def chat_endpoint(request: ChatRequest):
    # 1. 프론트엔드에서 받은 메시지 중 가장 마지막 사용자의 질문(단건)만 추출합니다.
    # 토큰 폭발(TPM 초과)을 방지하기 위해 이전 대화 기록은 당분간 제외합니다.
    last_user_message = ""
    for msg in reversed(request.messages):
        if msg.get("role") == "user":
            last_user_message = msg.get("content", "")
            break
            
    formatted_messages = [("user", last_user_message)]

    # 2. 캐싱된(싱글톤) 에이전트 인스턴스 가져오기
    agent = build_agent()

    # 3. 에이전트 실행 (단건 질문만 전달)
    result = agent.invoke({"messages": formatted_messages})

    # 4. 구조화된 응답 추출 및 반환
    structured = result["structured_response"]
    response_data = structured.model_dump()

    return {
        "session_id": request.user_id,
        "response": response_data
    }