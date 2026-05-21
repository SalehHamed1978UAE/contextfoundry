from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """Application settings"""

    # Database
    database_url: str = "postgresql://cf_user:cf_password@localhost:5433/context_foundry"
    redis_url: str = "redis://localhost:6380"

    # LLM Provider: "ollama" or "openai"
    llm_provider: str = "ollama"

    # Ollama
    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5:1.5b"
    ollama_embedding_model: str = "nomic-embed-text"

    # OpenAI (used when llm_provider = "openai")
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    openai_base_url: str = "https://api.openai.com/v1"

    # Local embeddings (fallback if not using Ollama embeddings)
    embedding_model: str = "BAAI/bge-small-en-v1.5"
    embedding_dimension: int = 768

    # Graph settings
    graph_name: str = "cf_knowledge"

    # Confidence thresholds
    confidence_threshold_high: float = 0.85
    confidence_threshold_medium: float = 0.70
    confidence_threshold_low: float = 0.50
    confidence_threshold_floor: float = 0.40

    # Retrieval settings
    vector_search_top_k: int = 15
    graph_max_hops: int = 2

    # Query timeouts (seconds)
    llm_timeout: int = 600  # Generous for CPU inference
    vector_search_timeout: int = 5
    graph_query_timeout: int = 10

    # Session settings
    session_ttl_seconds: int = 3600  # 1 hour

    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()
