"""
Updated main application using the optimized workflow
"""
from src.workflows.optimized_workflow import compiled_graph
from src.utils.states import ChatRequest, ChatResponse
from src.utils.logger import workflow_logger
from src.config.settings import config


class OptimizedBookingApp:
    """Main application class using optimized workflow"""
    
    def __init__(self):
        self.graph = compiled_graph
        self.config = config
    
    async def process_message(self, request: ChatRequest) -> ChatResponse:
        """Process a user message through the optimized workflow"""
        try:
            workflow_logger.log_step_start("message_processing", {"message": request.message})
            
            # Prepare initial state
            initial_state = {
                "messages": [{"role": "user", "content": request.message}],
                "current_step": "direction",
                "failure_step": False,
                "executionFlow": [],
                "data": {
                    "validation_errors": [],
                    "retry_count": 0,
                    "session_id": request.checkpoint_id or self.config.get_session_id()
                },
                "session_id": request.checkpoint_id,
                "timestamp": None
            }
            
            # Run the workflow
            result = await self.graph.ainvoke(
                initial_state,
                config={"thread_id": request.checkpoint_id or "default"}
            )
            
            # Extract response
            messages = result.get("messages", [])
            last_message = messages[-1] if messages else None
            
            response_content = last_message.content if last_message else "I'm sorry, I couldn't process your request."
            
            workflow_logger.log_workflow_complete(
                result.get("current_step", "unknown"),
                len(result.get("executionFlow", []))
            )
            
            return ChatResponse(
                content=response_content,
                checkpoint_id=request.checkpoint_id,
                status="complete"
            )
            
        except Exception as e:
            workflow_logger.log_exception("message_processing", e)
            return ChatResponse(
                content="I'm experiencing technical difficulties. Please try again later.",
                checkpoint_id=request.checkpoint_id,
                status="error",
                error_code="INTERNAL_ERROR"
            )
    
    def get_workflow_status(self, checkpoint_id: str) -> dict:
        """Get current workflow status"""
        try:
            # This would need to be implemented based on your state persistence strategy
            return {
                "status": "active",
                "current_step": "unknown",
                "checkpoint_id": checkpoint_id
            }
        except Exception as e:
            workflow_logger.log_exception("status_check", e)
            return {
                "status": "error",
                "error": str(e)
            }


# Create the optimized app instance
app = OptimizedBookingApp()
