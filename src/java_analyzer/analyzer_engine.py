"""
Static Analyzer Engine
Core logic for AST parsing and metric calculation
"""

import javalang
from typing import List, Dict, Any, Tuple, Optional

# Importing the detectors package registers every detector in order.
import detectors  # noqa: F401
from detectors.base import (
    Detector,
    CodeSmell,
    Finding,
    REGISTRY,
    AnalysisContext,
    CacheStats,
    SHARED_AST_CACHE,
)
from utils.helpers import count_blank_lines, count_comment_lines


class StaticAnalyzerEngine:
    """
    Main analyzer engine that orchestrates all code smell detectors
    and calculates comprehensive code metrics.
    """

    def __init__(self, code: str, config: Dict[str, bool] = None):
        """
        Initialize the analyzer engine.

        Args:
            code: Java source code as a string
            config: Dictionary specifying which detectors to enable
        """
        self.code = code
        self.lines = code.split('\n')
        self.config = config or {
            'design': True,
            'implementation': True,
            'naming': True,
            'documentation': True
        }
        self.file_name: Optional[str] = None
        self.detectors: List[CodeSmell] = self._initialize_detectors()
        # Outputs of the most recent run (catalog + cache telemetry).
        self.findings: List[Finding] = []
        self.catalog: List[Dict[str, Any]] = []
        self.cache_stats: Dict[str, int] = {"hits": 0, "misses": 0}

    def _initialize_detectors(self) -> List[CodeSmell]:
        """
        Instantiate enabled detectors.

        Detectors come from the ordered REGISTRY, so instantiation,
        execution and dashboard catalog order are always identical.

        Returns:
            List of code smell detector instances
        """
        return [
            detector_cls()
            for detector_cls in REGISTRY.ordered_classes()
            if self.config.get(detector_cls.config_key, True)
        ]

    def run(self) -> Tuple[List[Dict[str, Any]], javalang.tree.CompilationUnit]:
        """
        Run the complete analysis pipeline.

        Returns:
            Tuple of (list of detected issues, parsed AST tree)

        Raises:
            ValueError: If syntax error or parsing fails
        """
        try:
            # One parsed AST per run, shared by every detector and served
            # from the content+version keyed cross-run cache.
            cache_stats = CacheStats()
            tree = SHARED_AST_CACHE.parse(self.code, stats=cache_stats)
        except javalang.parser.JavaSyntaxError as e:
            raise ValueError(f"Syntax Error at {e.at}: {e.description}")

        try:
            ctx = AnalysisContext(
                code=self.code,
                tree=tree,
                file_name=self.file_name,
                cache_stats=cache_stats,
            )

            findings_by_detector: Dict[str, List[Finding]] = {}
            all_findings: List[Finding] = []
            for detector in self.detectors:
                detector_findings = detector.analyze(ctx)
                findings_by_detector[detector.config_key] = detector_findings
                all_findings.extend(detector_findings)

            # Catalog in registry order, including disabled detectors, so
            # the dashboard can list every registered entry deterministically.
            catalog: List[Dict[str, Any]] = []
            for key, detector_cls in REGISTRY.entries():
                enabled = any(d.config_key == key for d in self.detectors)
                detector_findings = findings_by_detector.get(key, [])
                catalog.append({
                    "config_key": key,
                    "name": detector_cls.display_name or detector_cls.__name__,
                    "category": detector_cls.category,
                    "enabled": enabled,
                    "count": len(detector_findings),
                    "findings": [f.to_record() for f in detector_findings],
                })

            self.findings = all_findings
            self.catalog = catalog
            self.cache_stats = cache_stats.as_dict()

            # Adapter layer: project findings onto the legacy issue dict.
            all_issues = [item.to_issue() for item in all_findings]
            return all_issues, tree

        except Exception as e:
            raise ValueError(f"AST Analysis Failed: {str(e)}")

    def calculate_metrics(self, tree: javalang.tree.CompilationUnit) -> Dict[str, Any]:
        """
        Calculate comprehensive code metrics from the AST.

        Args:
            tree: Parsed Java AST

        Returns:
            Dictionary containing various code metrics
        """
        metrics = {
            'total_classes': 0,
            'total_methods': 0,
            'total_fields': 0,
            'total_lines': len(self.lines),
            'blank_lines': count_blank_lines(self.lines),
            'comment_lines': count_comment_lines(self.lines),
            'avg_method_length': 0,
            'max_method_length': 0,
            'avg_complexity': 0,
            'max_complexity': 0,
            'code_lines': 0
        }

        method_lengths = []
        complexities = []

        # Analyze classes
        for _, node in tree.filter(javalang.tree.ClassDeclaration):
            metrics['total_classes'] += 1

            # Count methods
            if node.methods:
                metrics['total_methods'] += len(node.methods)

                for method in node.methods:
                    # Calculate method length
                    if method.body:
                        length = len(method.body)
                        method_lengths.append(length)

                        # Calculate cyclomatic complexity
                        complexity = self._calculate_complexity(method)
                        complexities.append(complexity)

            # Count fields
            if node.fields:
                metrics['total_fields'] += len(node.fields)

        # Calculate averages
        if method_lengths:
            metrics['avg_method_length'] = sum(method_lengths) / len(method_lengths)
            metrics['max_method_length'] = max(method_lengths)

        if complexities:
            metrics['avg_complexity'] = sum(complexities) / len(complexities)
            metrics['max_complexity'] = max(complexities)

        # Calculate code lines (excluding blanks and comments)
        metrics['code_lines'] = (metrics['total_lines'] -
                                 metrics['blank_lines'] -
                                 metrics['comment_lines'])

        return metrics

    def _calculate_complexity(self, method_node: javalang.tree.MethodDeclaration) -> int:
        """
        Calculate cyclomatic complexity for a method.

        Args:
            method_node: AST node representing a method

        Returns:
            Cyclomatic complexity value
        """
        return Detector.count_branches(method_node)
