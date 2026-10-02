"""
Design Smell Detector
Identifies architectural and design-level code smells
"""

from typing import List

import javalang

from detectors.base import Detector, REGISTRY, AnalysisContext, Finding


@REGISTRY.register
class DesignSmells(Detector):
    """
    Detects design-level code smells including:
    - God Class
    - Swiss Army Knife
    - Data Class
    - Feature Envy
    - Lazy Class
    - Abstract Without Abstracts
    """

    config_key = "design"
    display_name = "Design Smells"
    category = "Design"

    def analyze(self, ctx: AnalysisContext) -> List[Finding]:
        """Detect all design smells using the shared class traversal."""
        results = []

        for _path, node in ctx.iter_classes():
            results.extend(self._detect_swiss_army_knife(ctx, node))
            results.extend(self._detect_god_class(ctx, node))
            results.extend(self._detect_data_class(ctx, node))
            results.extend(self._detect_feature_envy(ctx, node))
            results.extend(self._detect_lazy_class(ctx, node))
            results.extend(self._detect_abstract_without_abstracts(ctx, node))

        return results

    def _detect_swiss_army_knife(
        self, ctx: AnalysisContext, node: javalang.tree.ClassDeclaration
    ) -> List[Finding]:
        """Detect classes implementing too many interfaces."""
        results = []
        if node.implements and len(node.implements) > 5:
            results.append(self.finding(
                ctx,
                "Swiss Army Knife",
                node.name,
                "Medium",
                f"{len(node.implements)} interfaces implemented",
                node=node,
            ))
        return results

    def _detect_god_class(
        self, ctx: AnalysisContext, node: javalang.tree.ClassDeclaration
    ) -> List[Finding]:
        """Detect classes with too many methods or fields."""
        results = []
        methods = node.methods if node.methods else []
        fields = node.fields if node.fields else []

        if len(methods) > 20 or len(fields) > 15:
            results.append(self.finding(
                ctx,
                "God Class",
                node.name,
                "Critical",
                f"{len(methods)} methods, {len(fields)} fields",
                node=node,
            ))
        return results

    def _detect_data_class(
        self, ctx: AnalysisContext, node: javalang.tree.ClassDeclaration
    ) -> List[Finding]:
        """Detect classes with no behavioral logic (only getters/setters)."""
        results = []
        methods = node.methods if node.methods else []

        if len(methods) > 0:
            logic_methods = [m for m in methods if not m.name.startswith(('get', 'set', 'is'))]
            if len(logic_methods) == 0:
                results.append(self.finding(
                    ctx,
                    "Data Class",
                    node.name,
                    "Low",
                    "No behavioral logic found",
                    node=node,
                ))
        return results

    def _detect_feature_envy(
        self, ctx: AnalysisContext, node: javalang.tree.ClassDeclaration
    ) -> List[Finding]:
        """Detect methods with excessive external method calls."""
        results = []
        methods = node.methods if node.methods else []

        for method in methods:
            if method.body:
                external_calls = sum(1 for _p, _n in method.filter(javalang.tree.MethodInvocation))
                if external_calls > 10:
                    results.append(self.finding(
                        ctx,
                        "Feature Envy",
                        f"{node.name}.{method.name}",
                        "Medium",
                        f"{external_calls} external method calls",
                        node=method,
                    ))
        return results

    def _detect_lazy_class(
        self, ctx: AnalysisContext, node: javalang.tree.ClassDeclaration
    ) -> List[Finding]:
        """Detect classes with minimal functionality."""
        results = []
        methods = node.methods if node.methods else []
        fields = node.fields if node.fields else []

        if len(methods) < 3 and len(fields) < 3 and len(methods) > 0:
            results.append(self.finding(
                ctx,
                "Lazy Class",
                node.name,
                "Low",
                f"Minimal functionality: {len(methods)} methods, {len(fields)} fields",
                node=node,
            ))
        return results

    def _detect_abstract_without_abstracts(
        self, ctx: AnalysisContext, node: javalang.tree.ClassDeclaration
    ) -> List[Finding]:
        """Detect abstract classes with no abstract methods."""
        results = []
        methods = node.methods if node.methods else []

        if 'abstract' in (node.modifiers or []):
            abstract_methods = [m for m in methods if 'abstract' in (m.modifiers or [])]
            if len(abstract_methods) == 0:
                results.append(self.finding(
                    ctx,
                    "Abstract Without Abstracts",
                    node.name,
                    "Low",
                    "Abstract class with no abstract methods",
                    node=node,
                ))
        return results
