"""
Enhanced logging system for workflow tracking
"""
import logging
import json
from typing import Any, Dict, Optional
from datetime import datetime
from src.config.settings import config


class WorkflowLogger:
    """Enhanced logging for workflow operations"""
    
    def __init__(self, name: str = "workflow"):
        self.logger = logging.getLogger(name)
        self._setup_logger()
    
    def _setup_logger(self):
        """Setup logger with appropriate formatting"""
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
            
        # Set level based on config
        if config.workflow.enable_detailed_logging:
            self.logger.setLevel(logging.DEBUG)
        else:
            self.logger.setLevel(logging.INFO)
    
    def log_step_start(self, step: str, state: Dict[str, Any]):
        """Log the start of a workflow step"""
        self.logger.info(f"🔄 Starting step: {step}")
        if config.workflow.enable_detailed_logging:
            self.logger.debug(f"State: {self._safe_serialize(state)}")
    
    def log_step_success(self, step: str, next_step: str, duration: Optional[float] = None):
        """Log successful step completion"""
        msg = f"✅ Step {step} completed successfully → {next_step}"
        if duration:
            msg += f" (took {duration:.2f}s)"
        self.logger.info(msg)
    
    def log_step_failure(self, step: str, error: str, retry_count: int = 0):
        """Log step failure"""
        self.logger.error(f"❌ Step {step} failed: {error} (retry #{retry_count})")
    
    def log_api_call(self, api_name: str, payload: Dict[str, Any], success: bool, response: Any = None, error: str = None):
        """Log API calls with payload and response"""
        if success:
            self.logger.info(f"📡 API call to {api_name} succeeded")
            if config.workflow.enable_detailed_logging:
                self.logger.debug(f"Payload: {self._safe_serialize(payload)}")
                self.logger.debug(f"Response: {self._safe_serialize(response)}")
        else:
            self.logger.error(f"📡 API call to {api_name} failed: {error}")
            if config.workflow.enable_detailed_logging:
                self.logger.debug(f"Payload: {self._safe_serialize(payload)}")
    
    def log_validation_error(self, step: str, errors: list):
        """Log validation errors"""
        self.logger.warning(f"⚠️ Validation failed for {step}: {', '.join(errors)}")
    
    def log_user_interrupt(self, message: str):
        """Log user interrupts"""
        self.logger.info(f"🛑 User interrupt: {message}")
    
    def log_workflow_complete(self, final_state: str, total_steps: int):
        """Log workflow completion"""
        self.logger.info(f"🎉 Workflow completed with state: {final_state} (total steps: {total_steps})")
    
    def log_exception(self, step: str, exception: Exception):
        """Log exceptions with full traceback"""
        self.logger.exception(f"💥 Exception in step {step}: {str(exception)}")
    
    def _safe_serialize(self, obj: Any) -> str:
        """Safely serialize objects for logging"""
        try:
            return json.dumps(obj, indent=2, default=str)
        except (TypeError, ValueError):
            return str(obj)


# Global logger instance
workflow_logger = WorkflowLogger()
