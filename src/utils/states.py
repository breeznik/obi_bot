from pydantic import BaseModel
from typing import Optional , Any
from typing import TypedDict, Annotated, Optional, Literal , List
from langgraph.graph import add_messages 

# request / response
class ChatRequest(BaseModel):
    message: str
    checkpoint_id: Optional[str | int] = None

class ChatResponse(BaseModel):
    content: Any
    checkpoint_id: Optional[str | int] = None
    status: str = "complete"

# workflow

# state
class State(TypedDict):
    messages: Annotated[List , add_messages]
    current_step:str
    failure_step:bool = False
    executionFlow:List