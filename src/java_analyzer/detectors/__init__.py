"""
Detector package.

Importing the package registers every detector with the ordered
:data:`detectors.base.REGISTRY`. Import order here is the canonical
registration (and therefore dashboard catalog) order.
"""

from detectors.design import DesignSmells
from detectors.implementation import ImplementationSmells
from detectors.naming_docs import NamingSmells, DocumentationSmells
from detectors.base import (
    Detector,
    CodeSmell,
    Finding,
    REGISTRY,
    AnalysisContext,
    AstCache,
    SHARED_AST_CACHE,
    CacheStats,
    PARSER_LANGUAGE_VERSION,
)

__all__ = [
    "Detector",
    "CodeSmell",
    "Finding",
    "REGISTRY",
    "AnalysisContext",
    "AstCache",
    "SHARED_AST_CACHE",
    "CacheStats",
    "PARSER_LANGUAGE_VERSION",
    "DesignSmells",
    "ImplementationSmells",
    "NamingSmells",
    "DocumentationSmells",
]
