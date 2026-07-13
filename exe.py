import sys
import os

from pydantic import BaseModel
from typing import List, Dict
from dotenv import load_dotenv

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langchain.agents import create_agent

from server.agent import build_agent
from server.context_loader import load_context, save_and_summarize
import json

if __name__ == '__main__':
    
    # 3. 캐싱된 에이전트 인스턴스 가져오기
    agent = build_agent()

    # 3. 에이전트 실행 (단건 질문만 전달)
    print("종료하려면 !q 입력")
    in_t = ""
    while True:
        in_t = input("프롬프트 >>")
        result = agent.invoke(
        {"messages": in_t},
        config={"configurable": {"user_id": }}
    )