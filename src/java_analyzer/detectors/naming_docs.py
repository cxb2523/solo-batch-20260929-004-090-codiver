"""Naming convention and documentation smell detectors."""

from typing import List

import javalang

try:
    from detectors.base import REGISTRY, AnalysisContext, Detector, Finding
    from utils.helpers import validate_class_name, validate_method_name
except ImportError:
    from java_analyzer.detectors.base import REGISTRY, AnalysisContext, Detector, Finding
    from java_analyzer.utils.helpers import validate_class_name, validate_method_name


@REGISTRY.register(
    detector_id="naming",
    name="Naming Conventions",
    category="Naming",
    config_key="naming",
    description="Class and method identifier naming rules",
)
class NamingSmells(Detector):
    """Detect naming convention violations."""

    def analyze(self, context: AnalysisContext) -> List[Finding]:
        results: List[Finding] = []

        for node in self.iter_classes(context):
            if not validate_class_name(node.name):
                results.append(
                    self.create_finding(
                        context,
                        self.node_line(node),
                        "Low",
                        "Invalid Class Name",
                        node.name,
                        "Class name should follow PascalCase convention",
                    )
                )

            if len(node.name) < 3:
                results.append(
                    self.create_finding(
                        context,
                        self.node_line(node),
                        "Low",
                        "Short Name",
                        node.name,
                        "Class name too short (< 3 characters)",
                    )
                )

        for node in self.iter_methods(context):
            if not validate_method_name(node.name):
                results.append(
                    self.create_finding(
                        context,
                        self.node_line(node),
                        "Low",
                        "Invalid Method Name",
                        node.name,
                        "Method name should follow camelCase convention",
                    )
                )

            if len(node.name) < 3 and node.name not in ["is", "do", "to", "of"]:
                results.append(
                    self.create_finding(
                        context,
                        self.node_line(node),
                        "Low",
                        "Short Name",
                        node.name,
                        "Method name too short (< 3 characters)",
                    )
                )

        return results


@REGISTRY.register(
    detector_id="documentation",
    name="Documentation",
    category="Documentation",
    config_key="documentation",
    description="Javadoc coverage for classes and public methods",
)
class DocumentationSmells(Detector):
    """Detect missing or inadequate documentation."""

    def analyze(self, context: AnalysisContext) -> List[Finding]:
        results: List[Finding] = []

        for node in self.iter_classes(context):
            if not node.documentation:
                results.append(
                    self.create_finding(
                        context,
                        self.node_line(node),
                        "Low",
                        "Missing Class Documentation",
                        node.name,
                        "No Javadoc found for class",
                    )
                )

        for node in self.iter_methods(context):
            if "public" in (node.modifiers or []) and not node.documentation:
                results.append(
                    self.create_finding(
                        context,
                        self.node_line(node),
                        "Low",
                        "Missing Method Documentation",
                        node.name,
                        "No Javadoc found for public method",
                    )
                )

        return results
