"""
CaptureRecaptureEstimator - Lincoln-Petersen estimation for bounded counts.

Per v1.3 spec §5.4, when computing RANGE with multiple overlapping sources,
we use Lincoln-Petersen to estimate the hidden population.

Formula:
- n_A: Count from Source A
- n_B: Count from Source B  
- m: Overlap (intersection) between A and B via entity resolution
- N̂ (Estimated Total): (n_A × n_B) / m

With Chapman correction for small samples.
"""

import logging
import math
from dataclasses import dataclass
from typing import List, Optional

from .executor import SourceEvidence
from .models import BoundedCount

logger = logging.getLogger(__name__)


@dataclass
class CRCInput:
    """Input for Capture-Recapture estimation."""
    source_a_count: int
    source_b_count: int
    overlap_count: int
    source_a_name: str = "Source A"
    source_b_name: str = "Source B"


class CaptureRecaptureEstimator:
    """
    Lincoln-Petersen Capture-Recapture estimator.
    
    Estimates total population size from two overlapping samples.
    Used when aggregating across multiple data sources.
    """
    
    # Minimum overlap required for reliable estimate
    MIN_OVERLAP = 2
    
    # Confidence level for interval
    CONFIDENCE_Z = 1.96  # 95% CI
    
    def estimate(
        self,
        sources: List[SourceEvidence],
    ) -> Optional[BoundedCount]:
        """
        Estimate total population from multiple sources.
        
        Args:
            sources: List of SourceEvidence objects with entities
            
        Returns:
            BoundedCount with lower, upper, expected, and method
        """
        if len(sources) < 2:
            logger.warning("CRC requires at least 2 sources")
            return None
        
        # Use first two sources
        source_a = sources[0]
        source_b = sources[1]
        
        n_a = source_a.count
        n_b = source_b.count
        
        # Calculate overlap via entity matching
        overlap = self._calculate_overlap(source_a.entities, source_b.entities)
        m = len(overlap)
        
        logger.info(f"CRC: n_a={n_a}, n_b={n_b}, overlap={m}")
        
        if m < self.MIN_OVERLAP:
            # Insufficient overlap for reliable estimate
            logger.warning(f"Insufficient overlap ({m}) for CRC estimate")
            return BoundedCount(
                lower=max(n_a, n_b),
                upper=n_a + n_b,  # Union as upper bound
                expected=None,
                method="union_only",
            )
        
        return self._lincoln_petersen(n_a, n_b, m)
    
    def estimate_from_counts(
        self,
        n_a: int,
        n_b: int,
        overlap: int,
    ) -> Optional[BoundedCount]:
        """
        Estimate from pre-computed counts.
        
        Useful when overlap is already known from entity resolution.
        """
        if overlap < self.MIN_OVERLAP:
            return BoundedCount(
                lower=max(n_a, n_b),
                upper=n_a + n_b,
                expected=None,
                method="union_only",
            )
        
        return self._lincoln_petersen(n_a, n_b, overlap)
    
    def _lincoln_petersen(
        self,
        n_a: int,
        n_b: int,
        m: int,
    ) -> BoundedCount:
        """
        Apply Lincoln-Petersen estimator with Chapman correction.
        
        Standard LP: N̂ = (n_a × n_b) / m
        Chapman correction (for small samples): N̂ = ((n_a+1)(n_b+1))/(m+1) - 1
        """
        # Chapman-corrected estimate (less biased for small samples)
        chapman_estimate = ((n_a + 1) * (n_b + 1)) / (m + 1) - 1
        
        # Variance estimate (Seber 1982)
        numerator = (n_a + 1) * (n_b + 1) * (n_a - m) * (n_b - m)
        denominator = (m + 1) ** 2 * (m + 2)
        
        if denominator == 0:
            variance = 0
        else:
            variance = numerator / denominator
        
        std_error = math.sqrt(variance) if variance > 0 else 0
        
        # Confidence interval
        lower = max(max(n_a, n_b), int(chapman_estimate - self.CONFIDENCE_Z * std_error))
        upper = int(chapman_estimate + self.CONFIDENCE_Z * std_error)
        
        logger.info(
            f"CRC result: estimate={chapman_estimate:.1f}, "
            f"SE={std_error:.1f}, CI=[{lower}, {upper}]"
        )
        
        return BoundedCount(
            lower=lower,
            upper=upper,
            expected=int(round(chapman_estimate)),
            method="lincoln_petersen",
        )
    
    def _calculate_overlap(
        self,
        entities_a: List[str],
        entities_b: List[str],
    ) -> List[str]:
        """
        Calculate overlap between two entity sets.
        
        In production, this would use entity resolution to match
        entities that may have different IDs but represent the same thing.
        """
        # Simple set intersection for now
        # Production would use entity_dedup_hints table
        set_a = set(entities_a)
        set_b = set(entities_b)
        return list(set_a & set_b)


# Convenience function for direct estimation
def estimate_population(
    source_a_count: int,
    source_b_count: int,
    overlap_count: int,
) -> Optional[BoundedCount]:
    """
    Quick Lincoln-Petersen estimation from counts.
    
    Usage:
        bounds = estimate_population(n_a=12, n_b=10, overlap=8)
        print(f"Estimated: {bounds.expected} (range: {bounds.lower}-{bounds.upper})")
    """
    estimator = CaptureRecaptureEstimator()
    return estimator.estimate_from_counts(source_a_count, source_b_count, overlap_count)
