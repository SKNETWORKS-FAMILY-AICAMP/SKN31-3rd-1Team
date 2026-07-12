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
messages=[]
#################################################

@app.post("/api/chat")
def chat_endpoint(request: ChatRequest):
    # 프론트엔드 통신 테스트용 더미 로직
    # 마지막으로 보낸 사용자 메시지를 추출
    last_user_message = ""  # 사용자가 보낸 메세지
    for msg in reversed(request.messages):
        if msg.get("role") == "user":
            last_user_message = msg.get("content", "")
            break
    messages.append(HumanMessage(content=last_user_message))
    response = agent.invoke({
        "messages":messages
    })
    messages.append(AIMessage(content=response['messages'][-1].content))
    reply_text = response['messages'][-1].content
    
    #return {"reply": reply_text}
    return {
    "session_id": request.user_id,
    "response": {
        "type": "reply",
        "content": {
        "text": reply_text,
        },
        "sources": [
        {
            "title": "치매 가이드북 2장",
            "snippet": "같은 질문을 반복하는 양상은 초기 단계에서...",
            "url": "https://www.naver.com"
        }
        ]
    }
    }