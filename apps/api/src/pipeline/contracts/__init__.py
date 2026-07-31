"""Agent stage JSON contracts (design §4.1)."""

from __future__ import annotations

from ._common import (
    AdaptationDirection,
    Chunk,
    ClaimRef,
    ClaimType,
    ConflictClass,
    ConflictScope,
    ConflictSeverity,
    DetailDepth,
    ExtractedClaim,
    FidelityVerdict,
    FitVerdict,
    MatchedVia,
    Priority,
    ProposedEdge,
    ProposedNode,
    ReviewSeed,
    SubjectType,
    TeamProfileSnapshot,
)
from .adaptation import AdaptationInput, AdaptationOutput, Substitution
from .claim_extraction import ClaimExtractionInput, ClaimExtractionOutput
from .conflict import ConflictInput, ConflictItem, ConflictOutput
from .decomposition import CONTRACT_VERSION, DecompositionInput, DecompositionOutput
from .judge import AudienceFitResult, FidelityResult, JudgeInput, JudgeOutput
from .linking import LinkingInput, LinkingOutput, LinkProposal
from .prioritization import PrioritizationInput, PrioritizationOutput

__all__ = [
    "CONTRACT_VERSION",
    "AdaptationDirection",
    "AdaptationInput",
    "AdaptationOutput",
    "AudienceFitResult",
    "Chunk",
    "ClaimExtractionInput",
    "ClaimExtractionOutput",
    "ClaimRef",
    "ClaimType",
    "ConflictClass",
    "ConflictInput",
    "ConflictItem",
    "ConflictOutput",
    "ConflictScope",
    "ConflictSeverity",
    "DecompositionInput",
    "DecompositionOutput",
    "DetailDepth",
    "ExtractedClaim",
    "FidelityResult",
    "FidelityVerdict",
    "FitVerdict",
    "JudgeInput",
    "JudgeOutput",
    "LinkProposal",
    "LinkingInput",
    "LinkingOutput",
    "MatchedVia",
    "PrioritizationInput",
    "PrioritizationOutput",
    "Priority",
    "ProposedEdge",
    "ProposedNode",
    "ReviewSeed",
    "SubjectType",
    "Substitution",
    "TeamProfileSnapshot",
]
