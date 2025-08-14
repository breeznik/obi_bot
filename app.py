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
        last_msg = content.get("messages", [])[-1]
        
        # Step 1: Check for interrupt
        interrupt = content.get("__interrupt__", [])
        if interrupt:
            reply = interrupt[0].value

        # Step 2: Fallback to last message content
        else:
            messages = content.get("messages", [])
            if messages:
                if hasattr(last_msg, "content"):
                    reply = last_msg.content
                elif isinstance(last_msg, dict):
                    reply = last_msg.get("content", "No content found.")
                else:
                    reply = str(last_msg)
            else:
                reply = "No messages found."
                
        data = {"message": reply, "data": {}}
        # Check if last_msg has 'client_events' attribute
        if "client_events" in content:
            data["data"] = {**data["data"], "client_events": content["client_events"]}
            
        print('prinitng data', data)
        return ChatResponse(
            content=data,
            checkpoint_id=request.checkpoint_id,
            status="complete",
            state= content.get("data",{}),
            full_data=content
        )

    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail="Generation timed out")
    except Exception as e:
        import traceback
        import sys
        
        # Capture full traceback
        exc_type, exc_value, exc_traceback = sys.exc_info()
        traceback_str = ''.join(traceback.format_exception(exc_type, exc_value, exc_traceback))
        
        # Create detailed error message
        error_details = {
            "error_type": exc_type.__name__ if exc_type else "Unknown",
            "error_message": str(e),
            "traceback": traceback_str,
            "checkpoint_id": request.checkpoint_id,
            "message": request.message
        }
        
        # Log the full error for debugging
        print(f"=== DETAILED ERROR INFORMATION ===")
        print(f"Error Type: {error_details['error_type']}")
        print(f"Error Message: {error_details['error_message']}")
        print(f"Checkpoint ID: {error_details['checkpoint_id']}")
        print(f"User Message: {error_details['message']}")
        print(f"Full Traceback:\n{error_details['traceback']}")
        print(f"=== END ERROR INFORMATION ===")
        
        # Return detailed error to client
        raise HTTPException(
            status_code=500, 
            detail={
                "error": "Generation failed",
                "type": error_details['error_type'],
                "message": error_details['error_message'],
                "context": {
                    "checkpoint_id": error_details['checkpoint_id'],
                    "user_message": error_details['message']
                },
                "traceback": error_details['traceback']
            }
        )