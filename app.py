from fastapi import FastAPI, HTTPException
from typing import Optional , Any
from langchain_core.messages import HumanMessage
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import asyncio
from langgraph.types import Command
from src.scripts.workflow import compiled_graph
from src.utils.states import ChatResponse , ChatRequest
from src.services.mcp_client import McpClient
from src.controller.chat import Chat
from contextlib import asynccontextmanager
from src.services.mcp_client import init_tool_service
import sys
sys.stdout.reconfigure(encoding='utf-8')  # For Python 3.7+
    
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup logic
    await init_tool_service()
    yield


# fast interafce
app = FastAPI(lifespan=lifespan)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Type"],
)


# Routes
@app.get("/")
async def root():
    return {"message": "the api is working"}


@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    try:
        controller = Chat(
            message=request.message,
            checkpoint_id=request.checkpoint_id,
        )
        content = await asyncio.wait_for(controller.run(), timeout=120)
        
        # Step 1: Check for interrupt
        interrupt = content.get("__interrupt__", [])
        if interrupt:
            reply = interrupt[0].value

        # Step 2: Fallback to last message content
        else:
            messages = content.get("messages", [])
            if messages:
                last_msg = messages[-1]
                if hasattr(last_msg, "content"):
                    reply = last_msg.content
                elif isinstance(last_msg, dict):
                    reply = last_msg.get("content", "No content found.")
                else:
                    reply = str(last_msg)
            else:
                reply = "No messages found."

        return ChatResponse(
            content=reply,
            checkpoint_id=request.checkpoint_id,
            status="complete",
            state= content.get("data",{}),
            full_data=content
        )

    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail="Generation timed out")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Generation error: {e}")