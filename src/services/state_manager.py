"""
Centralized state management for workflow operations
"""
from typing import Dict, Any, List, Optional
from src.utils.states import State, Data
from src.utils import constants


class WorkflowStateManager:
    """Manages workflow state transitions and data consistency"""
    
    @staticmethod
    def initialize_data(state: State) -> State:
        """Initialize data structure if not present"""
        if not state.get("data"):
            state["data"] = {
                "validation_errors": [],
                "retry_count": 0,
                "session_id": None,
                "cart": {}
            }
        return state
    
    @staticmethod
    def add_execution_step(state: State, step: str, status: str = "completed") -> State:
        """Add step to execution flow tracking"""
        if "executionFlow" not in state:
            state["executionFlow"] = []
        
        step_entry = f"{step}_{status}"
        state["executionFlow"].append(step_entry)
        return state
    
    @staticmethod
    def add_validation_error(state: State, error: str) -> State:
        """Add validation error to state"""
        if "data" not in state:
            state = WorkflowStateManager.initialize_data(state)
        
        if "validation_errors" not in state["data"]:
            state["data"]["validation_errors"] = []
        
        state["data"]["validation_errors"].append(error)
        return state
    
    @staticmethod
    def clear_validation_errors(state: State) -> State:
        """Clear all validation errors"""
        if state.get("data", {}).get("validation_errors"):
            state["data"]["validation_errors"] = []
        return state
    
    @staticmethod
    def increment_retry_count(state: State) -> State:
        """Increment retry count for current step"""
        if "data" not in state:
            state = WorkflowStateManager.initialize_data(state)
        
        current_count = state["data"].get("retry_count", 0)
        state["data"]["retry_count"] = current_count + 1
        return state
    
    @staticmethod
    def reset_retry_count(state: State) -> State:
        """Reset retry count after successful step"""
        if state.get("data"):
            state["data"]["retry_count"] = 0
        return state
    
    @staticmethod
    def update_step_data(state: State, step: str, data: Dict[str, Any]) -> State:
        """Update data for specific step"""
        if "data" not in state:
            state = WorkflowStateManager.initialize_data(state)
        
        state["data"][step] = data
        return state
    
    @staticmethod
    def get_current_errors(state: State) -> List[str]:
        """Get current validation errors"""
        return state.get("data", {}).get("validation_errors", [])
    
    @staticmethod
    def should_exit_on_retry_limit(state: State, max_retries: int = 3) -> bool:
        """Check if retry limit exceeded"""
        retry_count = state.get("data", {}).get("retry_count", 0)
        return retry_count >= max_retries
    
    @staticmethod
    def create_success_response(state: State, next_step: str, message: Optional[str] = None) -> Dict[str, Any]:
        """Create standardized success response"""
        state = WorkflowStateManager.reset_retry_count(state)
        state = WorkflowStateManager.add_execution_step(state, state.get("current_step", "unknown"))
        
        response = {
            **state,
            "current_step": next_step,
            "failure_step": False
        }
        
        if message:
            from langchain_core.messages import AIMessage
            response["messages"] = state.get("messages", []) + [AIMessage(content=message)]
        
        return response
    
    @staticmethod
    def create_failure_response(state: State, error: str) -> Dict[str, Any]:
        """Create standardized failure response"""
        state = WorkflowStateManager.add_validation_error(state, error)
        state = WorkflowStateManager.increment_retry_count(state)
        state = WorkflowStateManager.add_execution_step(state, state.get("current_step", "unknown"), "failed")
        
        return {
            **state,
            "failure_step": True
        }
    
    @staticmethod
    def create_retry_response(state: State, message: str) -> Dict[str, Any]:
        """Create standardized retry response with user input"""
        from langgraph.types import interrupt
        from langchain_core.messages import HumanMessage
        
        state = WorkflowStateManager.increment_retry_count(state)
        
        user_input = interrupt(value=message)
        return {
            **state,
            "messages": state.get("messages", []) + [HumanMessage(content=user_input)],
            "failure_step": False
        }
