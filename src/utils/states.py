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
    status: str = "complete",
    state: Optional[Any] = None  # To include the full content of the response
    full_data: Optional[Any] = None  # To include the full content of the response

# workflow

class ContactInfo(TypedDict):
    firstname: str
    lastname: str
    email: str
    phone: str

class ScheduleInfo(TypedDict):
    airportid: str
    direction: Literal["A", "D"]
    traveldate: str
    flightId: str


class Data(TypedDict):
    schedule_info: ScheduleInfo = None
    schedule: Optional[any] = None
    contact_info:ContactInfo = None
    contact: Optional[any] = None
    product_type: str = None
    reservation: Optional[any] = None
    cart:Optional[any] = {}
    
    
# state
class State(TypedDict):
    messages: List
    current_step:str
    failure_step:bool = False
    executionFlow:List
    data:Data = None
    