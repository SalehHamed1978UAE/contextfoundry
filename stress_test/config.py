"""
Stress Test Configuration
"""
import os
from dataclasses import dataclass, field
from typing import List

@dataclass
class StressTestConfig:
    base_url: str = "http://localhost:5000"
    results_dir: str = "/home/runner/workspace/overnight_results"
    
    duration_hours: float = 8.0
    
    target_documents: int = 1000
    target_queries: int = 10000
    
    docs_per_hour: int = 125
    queries_per_hour: int = 1250
    
    parallel_extractions: int = 3
    parallel_queries: int = 5
    
    hourly_checkpoint: bool = True
    
    accuracy_sample_size: int = 100
    consistency_test_repeats: int = 10
    
    doc_size_min: int = 100
    doc_size_max: int = 100000
    doc_size_weights: List[float] = field(default_factory=lambda: [0.1, 0.3, 0.4, 0.15, 0.05])
    
    entity_density_sparse: int = 3
    entity_density_medium: int = 15
    entity_density_dense: int = 50
    
    domains: List[str] = field(default_factory=lambda: [
        "it_infrastructure", "healthcare", "finance", "aviation", "supply_chain",
        "manufacturing", "construction", "real_estate", "energy", "utilities",
        "telecommunications", "retail", "hospitality", "education", "government",
        "defense", "aerospace", "automotive", "pharmaceuticals", "biotechnology",
        "insurance", "banking", "investment", "private_equity", "venture_capital",
        "logistics", "shipping", "ports", "airports", "railways",
        "oil_gas", "renewable_energy", "mining", "agriculture", "food_processing",
        "media", "entertainment", "sports", "gaming", "technology",
        "cybersecurity", "cloud_computing", "artificial_intelligence", "robotics", "iot",
        "legal", "consulting", "human_resources", "marketing", "advertising"
    ])
    
    doc_formats: List[str] = field(default_factory=lambda: [
        "structured_report", "narrative_memo", "bullet_points", "table_format",
        "mixed_format", "email_thread", "meeting_notes", "technical_spec",
        "policy_document", "contract_excerpt"
    ])
    
    query_patterns: List[str] = field(default_factory=lambda: [
        "property_query", "relationship_query", "multi_hop_query",
        "aggregation_query", "impact_query", "inverse_relationship",
        "existence_check", "non_existent_entity", "fuzzy_match",
        "contradiction_check", "provenance_query", "confidence_query"
    ])
    
    adversarial_doc_rate: float = 0.15
    adversarial_query_rate: float = 0.20
    contradiction_rate: float = 0.10
    cross_reference_rate: float = 0.30
    
    openai_model: str = "gpt-4o-mini"
    embedding_model: str = "text-embedding-3-small"
    
    def get_quick_test_config(self):
        """1-hour quick test configuration"""
        self.duration_hours = 1.0
        self.target_documents = 50
        self.target_queries = 500
        self.docs_per_hour = 50
        self.queries_per_hour = 500
        self.accuracy_sample_size = 20
        return self
    
    def get_medium_test_config(self):
        """4-hour medium test configuration"""
        self.duration_hours = 4.0
        self.target_documents = 400
        self.target_queries = 4000
        self.docs_per_hour = 100
        self.queries_per_hour = 1000
        return self


QUICK_CONFIG = StressTestConfig().get_quick_test_config()
MEDIUM_CONFIG = StressTestConfig().get_medium_test_config()
OVERNIGHT_CONFIG = StressTestConfig()
