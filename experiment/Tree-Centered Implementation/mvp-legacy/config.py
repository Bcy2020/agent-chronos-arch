"""
Configuration for decomposition MVP.
All parameters can be overridden via constructor or environment variables.
"""
import os
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Config:
    api_key: Optional[str] = None
    base_url: str = "https://api.deepseek.com"
    model: str = "deepseek-chat"
    
    max_depth: int = 3
    max_children: int = 4
    max_lines_threshold: int = 50
    
    temperature: float = 0.3
    max_retries: int = 3
    max_decompose_retries: int = 3
    timeout: int = 120
    
    output_dir: str = "output"
    nodes_dir: str = "output/nodes"
    
    def __post_init__(self):
        if self.api_key is None:
            self.api_key = os.getenv("DEEPSEEK_API_KEY")
    
    @classmethod
    def from_env(cls) -> "Config":
        return cls(
            api_key=os.getenv("DEEPSEEK_API_KEY"),
            base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
            model=os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
            max_depth=int(os.getenv("MAX_DEPTH", "3")),
            max_children=int(os.getenv("MAX_CHILDREN", "4")),
            max_lines_threshold=int(os.getenv("MAX_LINES_THRESHOLD", "50")),
            temperature=float(os.getenv("TEMPERATURE", "0.3")),
            max_retries=int(os.getenv("MAX_RETRIES", "3")),
            max_decompose_retries=int(os.getenv("MAX_DECOMPOSE_RETRIES", "3")),
            timeout=int(os.getenv("TIMEOUT", "120")),
        )
