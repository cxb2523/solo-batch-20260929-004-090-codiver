"""
Implementation Smell Detector
Identifies implementation-level code smells and complexity issues
"""

from typing import List

import javalang

from detectors.base import Detector, REGISTRY, AnalysisContext, Finding


@REGISTRY.register
class ImplementationSmells(Detector):
    """
    Detects implementation-level code smells including:
    - High Cyclomatic Complexity
    - Long Methods
    - Long Parameter Lists
    - Empty Catch Blocks
    - Magic Numbers
    - Deep Nesting
    """

    config_key = "implementation"
    display_name = "Implementation Smells"
    category = "Implementation"

    def analyze(self, ctx: AnalysisContext) -> List[Finding]:
        """Detect all implementation smells using the shared method traversal."""
        results = []

        for _path, node in ctx.iter_methods():
            results.extend(self._detect_high_complexity(ctx, node))
            results.extend(self._detect_long_method(ctx, node))
            results.extend(self._detect_long_parameter_list(ctx, node))
            results.extend(self._detect_empty_catch_blocks(ctx, node))
            results.extend(self._detect_magic_numbers(ctx, node))
            results.extend(self._detect_deep_nesting(ctx, node))

        return results

    def _detect_high_complexity(
        self, ctx: AnalysisContext, node: javalang.tree.MethodDeclaration
    ) -> List[Finding]:
        """Detect methods with high cyclomatic complexity."""
        results = []
        complexity = self._calculate_complexity(node)

        if complexity > 10:
            results.append(self.finding(
                ctx,
                "High Complexity",
                node.name,
                "High",
                f"Cyclomatic complexity: {complexity}",
                node=node,
            ))
        return results

    def _detect_long_method(
        self, ctx: AnalysisContext, node: javalang.tree.MethodDeclaration
    ) -> List[Finding]:
        """Detect methods that are too long."""
        results = []

        if node.body and len(node.body) > 30:
            results.append(self.finding(
                ctx,
                "Long Method",
                node.name,
                "Medium",
                f"Method body contains {len(node.body)} statements",
                node=node,
            ))
        return results

    def _detect_long_parameter_list(
        self, ctx: AnalysisContext, node: javalang.tree.MethodDeclaration
    ) -> List[Finding]:
        """Detect methods with too many parameters."""
        results = []

        if len(node.parameters) > 5:
            results.append(self.finding(
                ctx,
                "Long Parameter List",
                node.name,
                "Low",
                f"{len(node.parameters)} parameters",
                node=node,
            ))
        return results

    def _detect_empty_catch_blocks(
        self, ctx: AnalysisContext, node: javalang.tree.MethodDeclaration
    ) -> List[Finding]:
        """Detect empty catch blocks that swallow exceptions."""
        results = []

        for _path, catch in node.filter(javalang.tree.CatchClause):
            if not catch.block or len(catch.block) == 0:
                results.append(self.finding(
                    ctx,
                    "Empty Catch Block",
                    node.name,
                    "Critical",
                    "Exception swallowed without logs or logic",
                    # javalang does not attach a position to CatchClause;
                    # anchor the finding at the enclosing method.
                    node=node,
                ))
        return results

    def _detect_magic_numbers(
        self, ctx: AnalysisContext, node: javalang.tree.MethodDeclaration
    ) -> List[Finding]:
        """Detect hard-coded numeric literals (magic numbers)."""
        results = []
        magic_count = self._count_magic_numbers(node)

        if magic_count > 3:
            results.append(self.finding(
                ctx,
                "Magic Numbers",
                node.name,
                "Low",
                f"{magic_count} hard-coded numeric literals found",
                node=node,
            ))
        return results

    def _detect_deep_nesting(
        self, ctx: AnalysisContext, node: javalang.tree.MethodDeclaration
    ) -> List[Finding]:
        """Detect deeply nested control structures."""
        results = []
        max_depth = self._calculate_nesting_depth(node)

        if max_depth > 4:
            results.append(self.finding(
                ctx,
                "Deep Nesting",
                node.name,
                "Medium",
                f"Maximum nesting depth: {max_depth}",
                node=node,
            ))
        return results

    # Helper methods for calculations

    def _calculate_complexity(self, method_node: javalang.tree.MethodDeclaration) -> int:
        """
        Calculate cyclomatic complexity of a method.

        Delegates to the shared base implementation so the detector and
        the metrics engine can never drift apart.
        """
        return self.count_branches(method_node)

    def _count_magic_numbers(self, method_node: javalang.tree.MethodDeclaration) -> int:
        """Count magic numbers (excluding 0, 1, -1)."""
        count = 0

        for _path, node in method_node.filter(javalang.tree.Literal):
            if hasattr(node, 'value') and node.value:
                try:
                    val = float(node.value)
                    if val not in [0, 1, -1]:
                        count += 1
                except:
                    pass

        return count

    def _calculate_nesting_depth(self, node, current_depth: int = 0) -> int:
        """Calculate maximum nesting depth of control structures."""
        max_depth = current_depth
        nesting_constructs = (
            javalang.tree.IfStatement,
            javalang.tree.WhileStatement,
            javalang.tree.ForStatement,
            javalang.tree.DoStatement,
            javalang.tree.TryStatement
        )

        for child in node.children:
            if isinstance(child, nesting_constructs):
                child_depth = self._calculate_nesting_depth(child, current_depth + 1)
                max_depth = max(max_depth, child_depth)
            elif hasattr(child, 'children'):
                child_depth = self._calculate_nesting_depth(child, current_depth)
                max_depth = max(max_depth, child_depth)

        return max_depth
