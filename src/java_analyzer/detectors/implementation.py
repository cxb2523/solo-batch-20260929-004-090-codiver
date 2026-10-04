"""Implementation smell detector."""

from typing import List

import javalang

try:
    from detectors.base import REGISTRY, AnalysisContext, Detector, Finding
except ImportError:
    from java_analyzer.detectors.base import REGISTRY, AnalysisContext, Detector, Finding


@REGISTRY.register(
    detector_id="implementation",
    name="Implementation Smells",
    category="Implementation",
    config_key="implementation",
    description="Method complexity, size, and implementation-level risks",
)
class ImplementationSmells(Detector):
    """Detect implementation-level code smells."""

    def analyze(self, context: AnalysisContext) -> List[Finding]:
        results: List[Finding] = []

        for node in self.iter_methods(context):
            results.extend(self._detect_high_complexity(context, node))
            results.extend(self._detect_long_method(context, node))
            results.extend(self._detect_long_parameter_list(context, node))
            results.extend(self._detect_empty_catch_blocks(context, node))
            results.extend(self._detect_magic_numbers(context, node))
            results.extend(self._detect_deep_nesting(context, node))

        return results

    def _detect_high_complexity(
        self,
        context: AnalysisContext,
        node: javalang.tree.MethodDeclaration,
    ) -> List[Finding]:
        complexity = self._calculate_complexity(node)

        if complexity > 10:
            return [
                self.create_finding(
                    context,
                    self.node_line(node),
                    "High",
                    "High Complexity",
                    node.name,
                    f"Cyclomatic complexity: {complexity}",
                )
            ]
        return []

    def _detect_long_method(
        self,
        context: AnalysisContext,
        node: javalang.tree.MethodDeclaration,
    ) -> List[Finding]:
        if node.body and len(node.body) > 30:
            return [
                self.create_finding(
                    context,
                    self.node_line(node),
                    "Medium",
                    "Long Method",
                    node.name,
                    f"Method body contains {len(node.body)} statements",
                )
            ]
        return []

    def _detect_long_parameter_list(
        self,
        context: AnalysisContext,
        node: javalang.tree.MethodDeclaration,
    ) -> List[Finding]:
        if len(node.parameters) > 5:
            return [
                self.create_finding(
                    context,
                    self.node_line(node),
                    "Low",
                    "Long Parameter List",
                    node.name,
                    f"{len(node.parameters)} parameters",
                )
            ]
        return []

    def _detect_empty_catch_blocks(
        self,
        context: AnalysisContext,
        node: javalang.tree.MethodDeclaration,
    ) -> List[Finding]:
        results: List[Finding] = []

        for try_statement in self.iter_descendants(node, javalang.tree.TryStatement):
            for catch_index, catch in enumerate(try_statement.catches or []):
                if not catch.block or len(catch.block) == 0:
                    results.append(
                        self.create_finding(
                            context,
                            self._catch_line(
                                context,
                                try_statement,
                                catch_index,
                                self.node_line(node),
                            ),
                            "Critical",
                            "Empty Catch Block",
                            node.name,
                            "Exception swallowed without logs or logic",
                        )
                    )
        return results

    def _catch_line(
        self,
        context: AnalysisContext,
        try_statement: javalang.tree.TryStatement,
        catch_index: int,
        fallback: int,
    ) -> int:
        start_index = self.node_line(try_statement, fallback) - 1
        seen = 0
        for index in range(start_index, len(context.lines)):
            stripped = context.lines[index].strip()
            if stripped.startswith("catch") or stripped.startswith("} catch"):
                if seen == catch_index:
                    return index + 1
                seen += 1
        return fallback

    def _detect_magic_numbers(
        self,
        context: AnalysisContext,
        node: javalang.tree.MethodDeclaration,
    ) -> List[Finding]:
        magic_count = self._count_magic_numbers(node)

        if magic_count > 3:
            return [
                self.create_finding(
                    context,
                    self.node_line(node),
                    "Low",
                    "Magic Numbers",
                    node.name,
                    f"{magic_count} hard-coded numeric literals found",
                )
            ]
        return []

    def _detect_deep_nesting(
        self,
        context: AnalysisContext,
        node: javalang.tree.MethodDeclaration,
    ) -> List[Finding]:
        max_depth = self._calculate_nesting_depth(node)

        if max_depth > 4:
            return [
                self.create_finding(
                    context,
                    self.node_line(node),
                    "Medium",
                    "Deep Nesting",
                    node.name,
                    f"Maximum nesting depth: {max_depth}",
                )
            ]
        return []

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

        for _node in self.iter_descendants(method_node, branch_types):
            count += 1

        return count

    def _count_magic_numbers(self, method_node: javalang.tree.MethodDeclaration) -> int:
        count = 0

        for node in self.iter_descendants(method_node, javalang.tree.Literal):
            if hasattr(node, "value") and node.value:
                try:
                    val = float(node.value)
                    if val not in [0, 1, -1]:
                        count += 1
                except ValueError:
                    pass

        return count

    def _calculate_nesting_depth(self, node, current_depth: int = 0) -> int:
        max_depth = current_depth
        nesting_constructs = (
            javalang.tree.IfStatement,
            javalang.tree.WhileStatement,
            javalang.tree.ForStatement,
            javalang.tree.DoStatement,
            javalang.tree.TryStatement,
        )

        for child in self.iter_ast_children(node):
            if isinstance(child, nesting_constructs):
                child_depth = self._calculate_nesting_depth(child, current_depth + 1)
                max_depth = max(max_depth, child_depth)
            elif hasattr(child, "children"):
                child_depth = self._calculate_nesting_depth(child, current_depth)
                max_depth = max(max_depth, child_depth)

        return max_depth
