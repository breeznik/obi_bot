"""
Configuration management for the application
"""
import os
from typing import Dict, Any
from dataclasses import dataclass


@dataclass
class ApiConfig:
    """API configuration settings"""
    mcp_server_url: str = "http://localhost:3000/sse"
    mcp_server_key: str = "obi_mcp"
    default_session_id: str = "00009223581026309436128527"
    reservation_session_id: str = "00081400083250224448591690"
    max_retries: int = 3
    timeout_seconds: int = 30


@dataclass
class WorkflowConfig:
    """Workflow configuration settings"""
    max_retry_attempts: int = 3
    enable_validation: bool = True
    enable_detailed_logging: bool = True
    auto_advance_on_success: bool = True


@dataclass
class LLMConfig:
    """LLM configuration settings"""
    model_name: str = "gpt-4o"
    temperature: float = 0.7
    max_tokens: int = 1000


class ConfigManager:
    """Centralized configuration management"""
    
    def __init__(self):
        self.api = ApiConfig()
        self.workflow = WorkflowConfig()
        self.llm = LLMConfig()
        self._load_from_env()
    
    def _load_from_env(self):
        """Load configuration from environment variables"""
        # API Config
        self.api.mcp_server_url = os.getenv("MCP_SERVER_URL", self.api.mcp_server_url)
        self.api.mcp_server_key = os.getenv("MCP_SERVER_KEY", self.api.mcp_server_key)
        self.api.default_session_id = os.getenv("DEFAULT_SESSION_ID", self.api.default_session_id)
        self.api.max_retries = int(os.getenv("API_MAX_RETRIES", self.api.max_retries))
        
        # Workflow Config
        self.workflow.max_retry_attempts = int(os.getenv("MAX_RETRY_ATTEMPTS", self.workflow.max_retry_attempts))
        self.workflow.enable_validation = os.getenv("ENABLE_VALIDATION", "true").lower() == "true"
        self.workflow.enable_detailed_logging = os.getenv("ENABLE_DETAILED_LOGGING", "true").lower() == "true"
        
        # LLM Config
        self.llm.model_name = os.getenv("OPENAI_MODEL", self.llm.model_name)
        self.llm.temperature = float(os.getenv("LLM_TEMPERATURE", self.llm.temperature))
        self.llm.max_tokens = int(os.getenv("LLM_MAX_TOKENS", self.llm.max_tokens))
    
    def get_session_id(self, step: str = None) -> str:
        """Get appropriate session ID for different steps"""
        if step in ["reservation", "contact"]:
            return self.api.reservation_session_id
        return self.api.default_session_id
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary"""
        return {
            "api": self.api.__dict__,
            "workflow": self.workflow.__dict__,
            "llm": self.llm.__dict__
        }


# Global configuration instance
config = ConfigManager()
