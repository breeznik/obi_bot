from pydantic import BaseModel, Field, EmailStr
from typing import Optional, Any, Dict
from typing import TypedDict, Annotated, Optional, Literal, List
from langgraph.graph import add_messages
from datetime import datetime

# Request / Response Models
class ChatRequest(BaseModel):
    message: str
    checkpoint_id: Optional[str | int] = None
    session_id: Optional[str] = None

class ChatResponse(BaseModel):
    content: Any
    checkpoint_id: Optional[str | int] = None
    status: str = "complete"
    error_code: Optional[str] = None

# Enhanced Contact Info with validation
class ContactInfo(TypedDict):
    firstname: str
    lastname: str  
    email: str  # Could use EmailStr for validation
    phone: str

# Enhanced Schedule Info with better typing
class ScheduleInfo(TypedDict):
    airportid: str  # 3-letter IATA code
    direction: Literal["A", "D"]  # A=Arrival, D=Departure
    traveldate: str  # YYYYMMDD format
    flightId: str   # Full flight number with airline code
    passengers: Optional[int]  # Number of passengers

# Enhanced Data structure
class Data(TypedDict):
    schedule_info: Optional[ScheduleInfo]
    schedule: Optional[Dict[str, Any]]
    contact_info: Optional[ContactInfo] 
    contact: Optional[Dict[str, Any]]
    product_type: Optional[str]
    reservation: Optional[Dict[str, Any]]
    cart: Optional[Dict[str, Any]]
    validation_errors: Optional[List[str]]
    retry_count: Optional[int]

# Enhanced State with better error handling
class State(TypedDict):
    messages: Annotated[List, add_messages]
    current_step: str
    failure_step: bool
    executionFlow: List[str]
    data: Optional[Data]
    session_id: Optional[str]
    timestamp: Optional[str]
    