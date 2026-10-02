"""
Naming Convention and Documentation Smell Detectors
Validates naming standards and documentation coverage
"""

from typing import List

from detectors.base import Detector, REGISTRY, AnalysisContext, Finding
from utils.helpers import validate_class_name, validate_method_name


@REGISTRY.register
class NamingSmells(Detector):
    """
    Detects naming convention violations including:
    - Invalid class names (PascalCase)
    - Invalid method names (camelCase)
    - Short identifiers
    """

    config_key = "naming"
    display_name = "Naming Conventions"
    category = "Naming"

    def analyze(self, ctx: AnalysisContext) -> List[Finding]:
        """Detect all naming convention violations."""
        results = []

        # Check class naming conventions
        for _path, node in ctx.iter_classes():
            if not validate_class_name(node.name):
                results.append(self.finding(
                    ctx,
                    "Invalid Class Name",
                    node.name,
                    "Low",
                    "Class name should follow PascalCase convention",
                    node=node,
                ))

            if len(node.name) < 3:
                results.append(self.finding(
                    ctx,
                    "Short Name",
                    node.name,
                    "Low",
                    "Class name too short (< 3 characters)",
                    node=node,
                ))

        # Check method naming conventions
        for _path, node in ctx.iter_methods():
            if not validate_method_name(node.name):
                results.append(self.finding(
                    ctx,
                    "Invalid Method Name",
                    node.name,
                    "Low",
                    "Method name should follow camelCase convention",
                    node=node,
                ))

            # Allow short common method names
            if len(node.name) < 3 and node.name not in ['is', 'do', 'to', 'of']:
                results.append(self.finding(
                    ctx,
                    "Short Name",
                    node.name,
                    "Low",
                    "Method name too short (< 3 characters)",
                    node=node,
                ))

        return results


@REGISTRY.register
class DocumentationSmells(Detector):
    """
    Detects missing or inadequate documentation including:
    - Missing class Javadoc
    - Missing public method Javadoc
    """

    config_key = "documentation"
    display_name = "Documentation Coverage"
    category = "Documentation"

    def analyze(self, ctx: AnalysisContext) -> List[Finding]:
        """Detect all documentation issues."""
        results = []

        # Check class documentation
        for _path, node in ctx.iter_classes():
            if not node.documentation:
                results.append(self.finding(
                    ctx,
                    "Missing Class Documentation",
                    node.name,
                    "Low",
                    "No Javadoc found for class",
                    node=node,
                ))

        # Check public method documentation
        for _path, node in ctx.iter_methods():
            if 'public' in (node.modifiers or []) and not node.documentation:
                results.append(self.finding(
                    ctx,
                    "Missing Method Documentation",
                    node.name,
                    "Low",
                    "No Javadoc found for public method",
                    node=node,
                ))

        return results
