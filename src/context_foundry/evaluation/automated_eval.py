"""
Automated 100-Query Evaluation System.

Runs all queries through both Context Foundry and GraphRAG baseline,
captures metrics, auto-scores where possible, and generates summary report.
"""
import time
import re
import random
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
import json
import statistics

from sqlalchemy import Column, String, Float, Boolean, DateTime, Text, Integer, JSON
from sqlalchemy.orm import Session

from ..models.schema import Base, get_session
from ..core import ContextFoundry
from .graphrag_baseline import GraphRAGBaseline
from .query_set import QuerySet, EvaluationQuery, QueryCategory


class EvaluationResult(Base):
    """Database table for storing evaluation results."""
    __tablename__ = 'evaluation_results'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    evaluation_run_id = Column(String(50), nullable=False, index=True)
    query_id = Column(String(20), nullable=False)
    query_text = Column(Text, nullable=False)
    query_type = Column(String(50), nullable=False)
    hop_count = Column(String(20), nullable=False)
    difficulty = Column(String(20), nullable=False)
    
    cf_response = Column(Text)
    cf_latency_ms = Column(Float)
    cf_confidence = Column(Float)
    
    graphrag_response = Column(Text)
    graphrag_latency_ms = Column(Float)
    
    auto_scores = Column(JSON)
    human_review = Column(JSON, nullable=True)
    flagged_for_review = Column(Boolean, default=False)
    
    created_at = Column(DateTime, default=datetime.utcnow)


@dataclass
class AutoScores:
    """Automatically computed scores for a comparison."""
    latency_winner: str  # 'cf', 'graphrag', or 'tie'
    latency_diff_ms: float
    latency_ratio: float
    
    cf_response_length: int
    graphrag_response_length: int
    length_winner: str
    
    cf_cites_relationships: bool
    cf_relationship_count: int
    graphrag_cites_relationships: bool
    graphrag_relationship_count: int
    
    cf_cites_rules: bool
    cf_rule_count: int
    graphrag_cites_rules: bool
    graphrag_rule_count: int
    
    cf_has_confidence: bool
    cf_confidence_value: Optional[float]
    
    provenance_score_cf: int  # 0-3 based on citations
    provenance_score_graphrag: int
    
    def to_dict(self) -> Dict:
        return {
            'latency_winner': self.latency_winner,
            'latency_diff_ms': self.latency_diff_ms,
            'latency_ratio': round(self.latency_ratio, 2),
            'cf_response_length': self.cf_response_length,
            'graphrag_response_length': self.graphrag_response_length,
            'length_winner': self.length_winner,
            'cf_cites_relationships': self.cf_cites_relationships,
            'cf_relationship_count': self.cf_relationship_count,
            'graphrag_cites_relationships': self.graphrag_cites_relationships,
            'graphrag_relationship_count': self.graphrag_relationship_count,
            'cf_cites_rules': self.cf_cites_rules,
            'cf_rule_count': self.cf_rule_count,
            'graphrag_cites_rules': self.graphrag_cites_rules,
            'graphrag_rule_count': self.graphrag_rule_count,
            'cf_has_confidence': self.cf_has_confidence,
            'cf_confidence_value': self.cf_confidence_value,
            'provenance_score_cf': self.provenance_score_cf,
            'provenance_score_graphrag': self.provenance_score_graphrag,
        }


@dataclass
class EvaluationSummary:
    """Summary statistics for the full evaluation."""
    run_id: str
    total_queries: int
    completed_queries: int
    
    cf_wins_latency: int = 0
    graphrag_wins_latency: int = 0
    latency_ties: int = 0
    
    cf_avg_latency_ms: float = 0.0
    graphrag_avg_latency_ms: float = 0.0
    
    cf_avg_response_length: float = 0.0
    graphrag_avg_response_length: float = 0.0
    
    cf_relationship_citation_rate: float = 0.0
    graphrag_relationship_citation_rate: float = 0.0
    
    cf_rule_citation_rate: float = 0.0
    graphrag_rule_citation_rate: float = 0.0
    
    cf_avg_confidence: float = 0.0
    
    cf_avg_provenance_score: float = 0.0
    graphrag_avg_provenance_score: float = 0.0
    
    by_category: Dict[str, Dict] = field(default_factory=dict)
    by_hop_count: Dict[str, Dict] = field(default_factory=dict)
    by_difficulty: Dict[str, Dict] = field(default_factory=dict)
    
    human_review_sample_size: int = 0
    human_review_cf_correct: int = 0
    human_review_graphrag_correct: int = 0
    
    statistical_significance: Optional[Dict] = None
    
    def to_dict(self) -> Dict:
        return {
            'run_id': self.run_id,
            'total_queries': self.total_queries,
            'completed_queries': self.completed_queries,
            'latency': {
                'cf_wins': self.cf_wins_latency,
                'graphrag_wins': self.graphrag_wins_latency,
                'ties': self.latency_ties,
                'cf_avg_ms': round(self.cf_avg_latency_ms, 1),
                'graphrag_avg_ms': round(self.graphrag_avg_latency_ms, 1),
            },
            'response_length': {
                'cf_avg': round(self.cf_avg_response_length, 0),
                'graphrag_avg': round(self.graphrag_avg_response_length, 0),
            },
            'provenance': {
                'cf_relationship_citation_rate': round(self.cf_relationship_citation_rate * 100, 1),
                'graphrag_relationship_citation_rate': round(self.graphrag_relationship_citation_rate * 100, 1),
                'cf_rule_citation_rate': round(self.cf_rule_citation_rate * 100, 1),
                'graphrag_rule_citation_rate': round(self.graphrag_rule_citation_rate * 100, 1),
                'cf_avg_provenance_score': round(self.cf_avg_provenance_score, 2),
                'graphrag_avg_provenance_score': round(self.graphrag_avg_provenance_score, 2),
            },
            'confidence': {
                'cf_avg': round(self.cf_avg_confidence, 2) if self.cf_avg_confidence else None,
            },
            'by_category': self.by_category,
            'by_hop_count': self.by_hop_count,
            'by_difficulty': self.by_difficulty,
            'human_review': {
                'sample_size': self.human_review_sample_size,
                'cf_correct': self.human_review_cf_correct,
                'graphrag_correct': self.human_review_graphrag_correct,
            },
            'statistical_significance': self.statistical_significance,
        }


class AutomatedEvaluator:
    """Runs automated evaluation across all 100 queries."""
    
    RELATIONSHIP_PATTERNS = [
        r'--\[.*?\]-->',
        r'--\[.*?\]--',
        r'DEPENDS_ON',
        r'OWNS',
        r'MEMBER_OF',
        r'AFFECTS',
        r'CAUSED_BY',
        r'ESCALATES_TO',
    ]
    
    RULE_PATTERNS = [
        r'ESCALATION_POLICY',
        r'INVARIANT',
        r'SAFETY_CHECK',
        r'VALIDATION',
        r'\[rule:',
        r'rule:.*?\]',
    ]
    
    def __init__(self, tenant_id: str = None):
        self.query_set = QuerySet()
        self.tenant_id = tenant_id
        self.cf = None
        self.graphrag = None
        
    def _init_systems(self):
        """Initialize both systems."""
        if self.cf is None:
            self.cf = ContextFoundry(tenant_id=self.tenant_id)
        if self.graphrag is None:
            self.graphrag = GraphRAGBaseline()
    
    def _cleanup_systems(self):
        """Cleanup systems."""
        if self.cf:
            self.cf.cleanup()
            self.cf = None
        self.graphrag = None
    
    def _count_pattern_matches(self, text: str, patterns: List[str]) -> int:
        """Count total matches for a list of patterns."""
        count = 0
        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            count += len(matches)
        return count
    
    def _has_pattern_match(self, text: str, patterns: List[str]) -> bool:
        """Check if any pattern matches."""
        for pattern in patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return True
        return False
    
    def _calculate_provenance_score(self, text: str) -> int:
        """Calculate provenance score 0-3 based on citations."""
        score = 0
        if self._has_pattern_match(text, self.RELATIONSHIP_PATTERNS):
            score += 1
        if self._has_pattern_match(text, self.RULE_PATTERNS):
            score += 1
        if re.search(r'confidence|certainty|\d+%', text, re.IGNORECASE):
            score += 1
        return score
    
    def _compute_auto_scores(
        self,
        cf_response: str,
        cf_latency: float,
        cf_confidence: Optional[float],
        graphrag_response: str,
        graphrag_latency: float,
    ) -> AutoScores:
        """Compute all automatic scores for a comparison."""
        
        latency_diff = graphrag_latency - cf_latency
        latency_ratio = cf_latency / graphrag_latency if graphrag_latency > 0 else 1.0
        
        if abs(latency_diff) < 500:
            latency_winner = 'tie'
        elif cf_latency < graphrag_latency:
            latency_winner = 'cf'
        else:
            latency_winner = 'graphrag'
        
        cf_len = len(cf_response)
        gr_len = len(graphrag_response)
        if abs(cf_len - gr_len) < 100:
            length_winner = 'tie'
        elif cf_len > gr_len:
            length_winner = 'cf'
        else:
            length_winner = 'graphrag'
        
        cf_rel_count = self._count_pattern_matches(cf_response, self.RELATIONSHIP_PATTERNS)
        gr_rel_count = self._count_pattern_matches(graphrag_response, self.RELATIONSHIP_PATTERNS)
        
        cf_rule_count = self._count_pattern_matches(cf_response, self.RULE_PATTERNS)
        gr_rule_count = self._count_pattern_matches(graphrag_response, self.RULE_PATTERNS)
        
        return AutoScores(
            latency_winner=latency_winner,
            latency_diff_ms=abs(latency_diff),
            latency_ratio=latency_ratio,
            cf_response_length=cf_len,
            graphrag_response_length=gr_len,
            length_winner=length_winner,
            cf_cites_relationships=cf_rel_count > 0,
            cf_relationship_count=cf_rel_count,
            graphrag_cites_relationships=gr_rel_count > 0,
            graphrag_relationship_count=gr_rel_count,
            cf_cites_rules=cf_rule_count > 0,
            cf_rule_count=cf_rule_count,
            graphrag_cites_rules=gr_rule_count > 0,
            graphrag_rule_count=gr_rule_count,
            cf_has_confidence=cf_confidence is not None,
            cf_confidence_value=cf_confidence,
            provenance_score_cf=self._calculate_provenance_score(cf_response),
            provenance_score_graphrag=self._calculate_provenance_score(graphrag_response),
        )
    
    def _select_human_review_sample(
        self,
        results: List[EvaluationResult],
        sample_size: int = 25,
    ) -> List[str]:
        """Select a stratified sample for human review."""
        by_category = {}
        for r in results:
            cat = r.query_type
            if cat not in by_category:
                by_category[cat] = []
            by_category[cat].append(r.query_id)
        
        sample = []
        per_category = max(1, sample_size // len(by_category))
        
        for cat, query_ids in by_category.items():
            n = min(per_category, len(query_ids))
            sample.extend(random.sample(query_ids, n))
        
        while len(sample) < sample_size and len(sample) < len(results):
            remaining = [r.query_id for r in results if r.query_id not in sample]
            if remaining:
                sample.append(random.choice(remaining))
            else:
                break
        
        return sample[:sample_size]
    
    def _calculate_statistical_significance(
        self,
        cf_latencies: List[float],
        gr_latencies: List[float],
        cf_provenance: List[int],
        gr_provenance: List[int],
    ) -> Dict:
        """Calculate statistical significance of differences."""
        result = {}
        
        if len(cf_latencies) >= 2 and len(gr_latencies) >= 2:
            cf_mean = statistics.mean(cf_latencies)
            gr_mean = statistics.mean(gr_latencies)
            cf_std = statistics.stdev(cf_latencies)
            gr_std = statistics.stdev(gr_latencies)
            
            pooled_std = ((cf_std**2 + gr_std**2) / 2) ** 0.5
            if pooled_std > 0:
                effect_size = abs(cf_mean - gr_mean) / pooled_std
            else:
                effect_size = 0
            
            result['latency'] = {
                'cf_mean': round(cf_mean, 1),
                'graphrag_mean': round(gr_mean, 1),
                'cf_std': round(cf_std, 1),
                'graphrag_std': round(gr_std, 1),
                'effect_size_cohens_d': round(effect_size, 2),
                'significant': effect_size > 0.5,
            }
        
        if len(cf_provenance) >= 2 and len(gr_provenance) >= 2:
            cf_mean = statistics.mean(cf_provenance)
            gr_mean = statistics.mean(gr_provenance)
            
            result['provenance'] = {
                'cf_mean': round(cf_mean, 2),
                'graphrag_mean': round(gr_mean, 2),
                'cf_advantage': round(cf_mean - gr_mean, 2),
                'significant': abs(cf_mean - gr_mean) > 0.5,
            }
        
        return result
    
    def run_full_evaluation(
        self,
        run_id: Optional[str] = None,
        sample_for_review: int = 25,
        progress_callback=None,
    ) -> EvaluationSummary:
        """Run the full 100-query evaluation."""
        
        if run_id is None:
            run_id = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        
        self._init_systems()
        
        queries = self.query_set.queries
        results: List[EvaluationResult] = []
        
        cf_latencies = []
        gr_latencies = []
        cf_confidences = []
        cf_provenance_scores = []
        gr_provenance_scores = []
        
        session = get_session()
        
        try:
            for i, query in enumerate(queries):
                if progress_callback:
                    progress_callback(i + 1, len(queries), query.id)
                
                try:
                    start_cf = time.time()
                    cf_result = self.cf.query(query.query_text)
                    cf_latency = (time.time() - start_cf) * 1000
                    
                    cf_response = cf_result.answer if hasattr(cf_result, 'answer') else str(cf_result)
                    cf_confidence = cf_result.confidence if hasattr(cf_result, 'confidence') else None
                except Exception as e:
                    cf_response = f"Error: {str(e)}"
                    cf_latency = 0
                    cf_confidence = None
                
                try:
                    start_gr = time.time()
                    gr_result = self.graphrag.query(query.query_text)
                    gr_latency = (time.time() - start_gr) * 1000
                    
                    gr_response = gr_result.answer if hasattr(gr_result, 'answer') else str(gr_result)
                except Exception as e:
                    gr_response = f"Error: {str(e)}"
                    gr_latency = 0
                
                auto_scores = self._compute_auto_scores(
                    cf_response, cf_latency, cf_confidence,
                    gr_response, gr_latency,
                )
                
                eval_result = EvaluationResult(
                    evaluation_run_id=run_id,
                    query_id=query.id,
                    query_text=query.query_text,
                    query_type=query.category.value,
                    hop_count=query.hop_count,
                    difficulty=query.difficulty,
                    cf_response=cf_response,
                    cf_latency_ms=cf_latency,
                    cf_confidence=cf_confidence,
                    graphrag_response=gr_response,
                    graphrag_latency_ms=gr_latency,
                    auto_scores=auto_scores.to_dict(),
                    flagged_for_review=False,
                )
                
                session.add(eval_result)
                results.append(eval_result)
                
                cf_latencies.append(cf_latency)
                gr_latencies.append(gr_latency)
                if cf_confidence:
                    cf_confidences.append(cf_confidence)
                cf_provenance_scores.append(auto_scores.provenance_score_cf)
                gr_provenance_scores.append(auto_scores.provenance_score_graphrag)
                
                if (i + 1) % 10 == 0:
                    session.commit()
            
            review_sample = self._select_human_review_sample(results, sample_for_review)
            for result in results:
                if result.query_id in review_sample:
                    result.flagged_for_review = True
            
            session.commit()
            
            summary = self._compute_summary(
                run_id, results,
                cf_latencies, gr_latencies,
                cf_confidences,
                cf_provenance_scores, gr_provenance_scores,
            )
            
            return summary
            
        finally:
            session.close()
            self._cleanup_systems()
    
    def _compute_summary(
        self,
        run_id: str,
        results: List[EvaluationResult],
        cf_latencies: List[float],
        gr_latencies: List[float],
        cf_confidences: List[float],
        cf_provenance: List[int],
        gr_provenance: List[int],
    ) -> EvaluationSummary:
        """Compute summary statistics."""
        
        summary = EvaluationSummary(
            run_id=run_id,
            total_queries=len(results),
            completed_queries=len(results),
        )
        
        for result in results:
            scores = result.auto_scores
            if scores['latency_winner'] == 'cf':
                summary.cf_wins_latency += 1
            elif scores['latency_winner'] == 'graphrag':
                summary.graphrag_wins_latency += 1
            else:
                summary.latency_ties += 1
        
        if cf_latencies:
            summary.cf_avg_latency_ms = statistics.mean(cf_latencies)
        if gr_latencies:
            summary.graphrag_avg_latency_ms = statistics.mean(gr_latencies)
        
        cf_lengths = [r.auto_scores['cf_response_length'] for r in results]
        gr_lengths = [r.auto_scores['graphrag_response_length'] for r in results]
        if cf_lengths:
            summary.cf_avg_response_length = statistics.mean(cf_lengths)
        if gr_lengths:
            summary.graphrag_avg_response_length = statistics.mean(gr_lengths)
        
        cf_rel_cites = sum(1 for r in results if r.auto_scores['cf_cites_relationships'])
        gr_rel_cites = sum(1 for r in results if r.auto_scores['graphrag_cites_relationships'])
        summary.cf_relationship_citation_rate = cf_rel_cites / len(results) if results else 0
        summary.graphrag_relationship_citation_rate = gr_rel_cites / len(results) if results else 0
        
        cf_rule_cites = sum(1 for r in results if r.auto_scores['cf_cites_rules'])
        gr_rule_cites = sum(1 for r in results if r.auto_scores['graphrag_cites_rules'])
        summary.cf_rule_citation_rate = cf_rule_cites / len(results) if results else 0
        summary.graphrag_rule_citation_rate = gr_rule_cites / len(results) if results else 0
        
        if cf_confidences:
            summary.cf_avg_confidence = statistics.mean(cf_confidences)
        
        if cf_provenance:
            summary.cf_avg_provenance_score = statistics.mean(cf_provenance)
        if gr_provenance:
            summary.graphrag_avg_provenance_score = statistics.mean(gr_provenance)
        
        for category in QueryCategory:
            cat_results = [r for r in results if r.query_type == category.value]
            if cat_results:
                cat_cf_lat = [r.cf_latency_ms for r in cat_results]
                cat_gr_lat = [r.graphrag_latency_ms for r in cat_results]
                cat_cf_prov = [r.auto_scores['provenance_score_cf'] for r in cat_results]
                cat_gr_prov = [r.auto_scores['provenance_score_graphrag'] for r in cat_results]
                
                summary.by_category[category.value] = {
                    'count': len(cat_results),
                    'cf_avg_latency': round(statistics.mean(cat_cf_lat), 1),
                    'graphrag_avg_latency': round(statistics.mean(cat_gr_lat), 1),
                    'cf_avg_provenance': round(statistics.mean(cat_cf_prov), 2),
                    'graphrag_avg_provenance': round(statistics.mean(cat_gr_prov), 2),
                }
        
        for hop in ['single_hop', 'multi_hop']:
            hop_results = [r for r in results if r.hop_count == hop]
            if hop_results:
                hop_cf_lat = [r.cf_latency_ms for r in hop_results]
                hop_gr_lat = [r.graphrag_latency_ms for r in hop_results]
                hop_cf_prov = [r.auto_scores['provenance_score_cf'] for r in hop_results]
                hop_gr_prov = [r.auto_scores['provenance_score_graphrag'] for r in hop_results]
                
                summary.by_hop_count[hop] = {
                    'count': len(hop_results),
                    'cf_avg_latency': round(statistics.mean(hop_cf_lat), 1),
                    'graphrag_avg_latency': round(statistics.mean(hop_gr_lat), 1),
                    'cf_avg_provenance': round(statistics.mean(hop_cf_prov), 2),
                    'graphrag_avg_provenance': round(statistics.mean(hop_gr_prov), 2),
                }
        
        for diff in ['easy', 'medium', 'hard']:
            diff_results = [r for r in results if r.difficulty == diff]
            if diff_results:
                diff_cf_lat = [r.cf_latency_ms for r in diff_results]
                diff_gr_lat = [r.graphrag_latency_ms for r in diff_results]
                diff_cf_prov = [r.auto_scores['provenance_score_cf'] for r in diff_results]
                diff_gr_prov = [r.auto_scores['provenance_score_graphrag'] for r in diff_results]
                
                summary.by_difficulty[diff] = {
                    'count': len(diff_results),
                    'cf_avg_latency': round(statistics.mean(diff_cf_lat), 1),
                    'graphrag_avg_latency': round(statistics.mean(diff_gr_lat), 1),
                    'cf_avg_provenance': round(statistics.mean(diff_cf_prov), 2),
                    'graphrag_avg_provenance': round(statistics.mean(diff_gr_prov), 2),
                }
        
        summary.human_review_sample_size = sum(1 for r in results if r.flagged_for_review)
        
        summary.statistical_significance = self._calculate_statistical_significance(
            cf_latencies, gr_latencies,
            cf_provenance, gr_provenance,
        )
        
        return summary
    
    def get_results_for_run(self, run_id: str) -> List[Dict]:
        """Get all results for a specific run."""
        session = get_session()
        try:
            results = session.query(EvaluationResult).filter(
                EvaluationResult.evaluation_run_id == run_id
            ).all()
            
            return [{
                'query_id': r.query_id,
                'query_text': r.query_text,
                'query_type': r.query_type,
                'hop_count': r.hop_count,
                'difficulty': r.difficulty,
                'cf_response': r.cf_response,
                'cf_latency_ms': r.cf_latency_ms,
                'cf_confidence': r.cf_confidence,
                'graphrag_response': r.graphrag_response,
                'graphrag_latency_ms': r.graphrag_latency_ms,
                'auto_scores': r.auto_scores,
                'human_review': r.human_review,
                'flagged_for_review': r.flagged_for_review,
            } for r in results]
        finally:
            session.close()
    
    def get_flagged_for_review(self, run_id: str) -> List[Dict]:
        """Get queries flagged for human review."""
        session = get_session()
        try:
            results = session.query(EvaluationResult).filter(
                EvaluationResult.evaluation_run_id == run_id,
                EvaluationResult.flagged_for_review == True
            ).all()
            
            return [{
                'query_id': r.query_id,
                'query_text': r.query_text,
                'cf_response': r.cf_response,
                'graphrag_response': r.graphrag_response,
                'auto_scores': r.auto_scores,
            } for r in results]
        finally:
            session.close()


def print_summary_report(summary: EvaluationSummary):
    """Print a formatted summary report."""
    data = summary.to_dict()
    
    print("\n" + "=" * 80)
    print("AUTOMATED EVALUATION REPORT")
    print(f"Run ID: {data['run_id']}")
    print(f"Queries Evaluated: {data['completed_queries']}/{data['total_queries']}")
    print("=" * 80)
    
    print("\n### LATENCY COMPARISON ###")
    lat = data['latency']
    print(f"  Context Foundry Wins:  {lat['cf_wins']} ({lat['cf_wins']/data['total_queries']*100:.1f}%)")
    print(f"  GraphRAG Wins:         {lat['graphrag_wins']} ({lat['graphrag_wins']/data['total_queries']*100:.1f}%)")
    print(f"  Ties (<500ms diff):    {lat['ties']}")
    print(f"  CF Avg Latency:        {lat['cf_avg_ms']:.0f}ms")
    print(f"  GraphRAG Avg Latency:  {lat['graphrag_avg_ms']:.0f}ms")
    
    print("\n### RESPONSE LENGTH ###")
    resp = data['response_length']
    print(f"  CF Avg Length:         {resp['cf_avg']:.0f} chars")
    print(f"  GraphRAG Avg Length:   {resp['graphrag_avg']:.0f} chars")
    
    print("\n### PROVENANCE & CITATIONS ###")
    prov = data['provenance']
    print(f"  CF Relationship Citations:     {prov['cf_relationship_citation_rate']:.1f}%")
    print(f"  GraphRAG Relationship Citations: {prov['graphrag_relationship_citation_rate']:.1f}%")
    print(f"  CF Rule Citations:             {prov['cf_rule_citation_rate']:.1f}%")
    print(f"  GraphRAG Rule Citations:       {prov['graphrag_rule_citation_rate']:.1f}%")
    print(f"  CF Avg Provenance Score:       {prov['cf_avg_provenance_score']:.2f}/3")
    print(f"  GraphRAG Avg Provenance Score: {prov['graphrag_avg_provenance_score']:.2f}/3")
    
    if data['confidence']['cf_avg']:
        print("\n### CONFIDENCE (CF Only) ###")
        print(f"  CF Avg Confidence:     {data['confidence']['cf_avg']:.2f}")
    
    print("\n### BY QUERY CATEGORY ###")
    for cat, stats in data['by_category'].items():
        print(f"  {cat}: n={stats['count']}, CF lat={stats['cf_avg_latency']:.0f}ms, "
              f"GR lat={stats['graphrag_avg_latency']:.0f}ms, "
              f"CF prov={stats['cf_avg_provenance']:.2f}, GR prov={stats['graphrag_avg_provenance']:.2f}")
    
    print("\n### BY HOP COUNT ###")
    for hop, stats in data['by_hop_count'].items():
        print(f"  {hop}: n={stats['count']}, CF lat={stats['cf_avg_latency']:.0f}ms, "
              f"GR lat={stats['graphrag_avg_latency']:.0f}ms, "
              f"CF prov={stats['cf_avg_provenance']:.2f}, GR prov={stats['graphrag_avg_provenance']:.2f}")
    
    print("\n### BY DIFFICULTY ###")
    for diff, stats in data['by_difficulty'].items():
        print(f"  {diff}: n={stats['count']}, CF lat={stats['cf_avg_latency']:.0f}ms, "
              f"GR lat={stats['graphrag_avg_latency']:.0f}ms, "
              f"CF prov={stats['cf_avg_provenance']:.2f}, GR prov={stats['graphrag_avg_provenance']:.2f}")
    
    print("\n### STATISTICAL SIGNIFICANCE ###")
    if data['statistical_significance']:
        sig = data['statistical_significance']
        if 'latency' in sig:
            lat_sig = sig['latency']
            print(f"  Latency Effect Size (Cohen's d): {lat_sig['effect_size_cohens_d']:.2f}")
            print(f"  Latency Significant?: {'YES' if lat_sig['significant'] else 'NO'}")
        if 'provenance' in sig:
            prov_sig = sig['provenance']
            print(f"  Provenance CF Advantage: {prov_sig['cf_advantage']:.2f}")
            print(f"  Provenance Significant?: {'YES' if prov_sig['significant'] else 'NO'}")
    
    print("\n### HUMAN REVIEW ###")
    hr = data['human_review']
    print(f"  Flagged for Review: {hr['sample_size']} queries")
    
    print("\n" + "=" * 80)
