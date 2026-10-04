"""
Static analyzer engine.
"""

from typing import Any, Dict, List, Optional, Tuple

import javalang

try:
    from detectors.base import (
        AST_CACHE,
        AnalysisContext,
        Detector,
        Finding,
        REGISTRY,
        load_detectors,
    )
    from utils.helpers import count_blank_lines, count_comment_lines
except ImportError:
    from java_analyzer.detectors.base import (
        AST_CACHE,
        AnalysisContext,
        Detector,
        Finding,
        REGISTRY,
        load_detectors,
    )
    from java_analyzer.utils.helpers import count_blank_lines, count_comment_lines


load_detectors()


class StaticAnalyzerEngine:
    """Orchestrate the shared AST cache and registered Java detectors."""

    def __init__(
        self,
        code: str,
        config: Optional[Dict[str, bool]] = None,
        file_name: str = "<input>.java",
    ):
        self.code = code
        self.lines = code.split("\n")
        self.file_name = file_name
        self.config = config or {
            "design": True,
            "implementation": True,
            "naming": True,
            "documentation": True,
        }
        self.detectors: List[Detector] = self._initialize_detectors()
        self.findings: List[Finding] = []
        self.context: Optional[AnalysisContext] = None
        self.last_cache_hits: int = 0
        self.last_content_digest: Optional[str] = None

    def _initialize_detectors(self) -> List[Detector]:
        return REGISTRY.create_detectors(self.config)

    def run(self) -> Tuple[List[Dict[str, Any]], javalang.tree.CompilationUnit]:
        """
        Run all enabled detectors.

        The returned issue list intentionally keeps the historical five-key
        dictionary structure expected by the dashboard.
        """
        try:
            context, cache_hit = AST_CACHE.get_or_parse(
                self.code,
                self.file_name,
            )
            self.context = context
            self.last_cache_hits = 1 if cache_hit else 0
            self.last_content_digest = context.content_digest

            self.findings = []
            for detector in self.detectors:
                self.findings.extend(detector.analyze(context))

            all_issues = [finding.to_legacy_dict() for finding in self.findings]
            return all_issues, context.tree

        except javalang.parser.JavaSyntaxError as error:
            raise ValueError(f"Syntax Error at {error.at}: {error.description}")
        except Exception as error:
            raise ValueError(f"AST Analysis Failed: {str(error)}")

    def calculate_metrics(self, tree: javalang.tree.CompilationUnit) -> Dict[str, Any]:
        metrics = {
            "total_classes": 0,
            "total_methods": 0,
            "total_fields": 0,
            "total_lines": len(self.lines),
            "blank_lines": count_blank_lines(self.lines),
            "comment_lines": count_comment_lines(self.lines),
            "avg_method_length": 0,
            "max_method_length": 0,
            "avg_complexity": 0,
            "max_complexity": 0,
            "code_lines": 0,
        }

        method_lengths = []
        complexities = []

        for _, node in tree.filter(javalang.tree.ClassDeclaration):
            metrics["total_classes"] += 1

            if node.methods:
                metrics["total_methods"] += len(node.methods)

                for method in node.methods:
                    if method.body:
                        length = len(method.body)
                        method_lengths.append(length)
                        complexity = self._calculate_complexity(method)
                        complexities.append(complexity)

            if node.fields:
                metrics["total_fields"] += len(node.fields)

        if method_lengths:
            metrics["avg_method_length"] = sum(method_lengths) / len(method_lengths)
            metrics["max_method_length"] = max(method_lengths)

        if complexities:
            metrics["avg_complexity"] = sum(complexities) / len(complexities)
            metrics["max_complexity"] = max(complexities)

        metrics["code_lines"] = (
            metrics["total_lines"]
            - metrics["blank_lines"]
            - metrics["comment_lines"]
        )

        return metrics

    def _calculate_complexity(self, method_node: javalang.tree.MethodDeclaration) -> int:
        count = 1
        branch_types = (
            javalang.tree.IfStatement,
            javalang.tree.WhileStatement,
            javalang.tree.DoStatement,
            javalang.tree.ForStatement,
            javalang.tree.CatchClause,
            javalang.tree.SwitchStatementCase,
            javalang.tree.TernaryExpression,
        )

        for _, _node in method_node.filter(branch_types):
            count += 1

        return count
