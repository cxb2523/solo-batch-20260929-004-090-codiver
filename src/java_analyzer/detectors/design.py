"""Design smell detector."""

from typing import List

import javalang

try:
    from detectors.base import REGISTRY, AnalysisContext, Detector, Finding
except ImportError:
    from java_analyzer.detectors.base import REGISTRY, AnalysisContext, Detector, Finding


@REGISTRY.register(
    detector_id="design",
    name="Design Smells",
    category="Design",
    config_key="design",
    description="Architectural and class-responsibility smells",
)
class DesignSmells(Detector):
    """Detect design-level code smells."""

    def analyze(self, context: AnalysisContext) -> List[Finding]:
        results: List[Finding] = []
        for node in self.iter_classes(context):
            results.extend(self._detect_swiss_army_knife(context, node))
            results.extend(self._detect_god_class(context, node))
            results.extend(self._detect_data_class(context, node))
            results.extend(self._detect_feature_envy(context, node))
            results.extend(self._detect_lazy_class(context, node))
            results.extend(self._detect_abstract_without_abstracts(context, node))
        return results

    def _detect_swiss_army_knife(
        self,
        context: AnalysisContext,
        node: javalang.tree.ClassDeclaration,
    ) -> List[Finding]:
        if node.implements and len(node.implements) > 5:
            return [
                self.create_finding(
                    context,
                    self.node_line(node),
                    "Medium",
                    "Swiss Army Knife",
                    node.name,
                    f"{len(node.implements)} interfaces implemented",
                )
            ]
        return []

    def _detect_god_class(
        self,
        context: AnalysisContext,
        node: javalang.tree.ClassDeclaration,
    ) -> List[Finding]:
        methods = node.methods if node.methods else []
        fields = node.fields if node.fields else []

        if len(methods) > 20 or len(fields) > 15:
            return [
                self.create_finding(
                    context,
                    self.node_line(node),
                    "Critical",
                    "God Class",
                    node.name,
                    f"{len(methods)} methods, {len(fields)} fields",
                )
            ]
        return []

    def _detect_data_class(
        self,
        context: AnalysisContext,
        node: javalang.tree.ClassDeclaration,
    ) -> List[Finding]:
        methods = node.methods if node.methods else []

        if methods:
            logic_methods = [m for m in methods if not m.name.startswith(("get", "set", "is"))]
            if not logic_methods:
                return [
                    self.create_finding(
                        context,
                        self.node_line(node),
                        "Low",
                        "Data Class",
                        node.name,
                        "No behavioral logic found",
                    )
                ]
        return []

    def _detect_feature_envy(
        self,
        context: AnalysisContext,
        node: javalang.tree.ClassDeclaration,
    ) -> List[Finding]:
        results: List[Finding] = []
        methods = node.methods if node.methods else []

        for method in methods:
            if method.body:
                external_calls = self.count_descendants(method, javalang.tree.MethodInvocation)
                if external_calls > 10:
                    results.append(
                        self.create_finding(
                            context,
                            self.node_line(method),
                            "Medium",
                            "Feature Envy",
                            f"{node.name}.{method.name}",
                            f"{external_calls} external method calls",
                        )
                    )
        return results

    def _detect_lazy_class(
        self,
        context: AnalysisContext,
        node: javalang.tree.ClassDeclaration,
    ) -> List[Finding]:
        methods = node.methods if node.methods else []
        fields = node.fields if node.fields else []

        if 0 < len(methods) < 3 and len(fields) < 3:
            return [
                self.create_finding(
                    context,
                    self.node_line(node),
                    "Low",
                    "Lazy Class",
                    node.name,
                    f"Minimal functionality: {len(methods)} methods, {len(fields)} fields",
                )
            ]
        return []

    def _detect_abstract_without_abstracts(
        self,
        context: AnalysisContext,
        node: javalang.tree.ClassDeclaration,
    ) -> List[Finding]:
        methods = node.methods if node.methods else []

        if "abstract" in (node.modifiers or []):
            abstract_methods = [m for m in methods if "abstract" in (m.modifiers or [])]
            if not abstract_methods:
                return [
                    self.create_finding(
                        context,
                        self.node_line(node),
                        "Low",
                        "Abstract Without Abstracts",
                        node.name,
                        "Abstract class with no abstract methods",
                    )
                ]
        return []
