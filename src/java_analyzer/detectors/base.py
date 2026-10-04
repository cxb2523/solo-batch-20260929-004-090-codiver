"""
Shared detector contract, finding model, registry, and AST cache.
"""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
from hashlib import sha256
from threading import Lock
from typing import Any, Callable, Dict, Iterator, List, Optional, Tuple, Type
import importlib.metadata

import javalang


JAVA_LANGUAGE_VERSION = "8"
try:
    JAVALANG_VERSION = importlib.metadata.version("javalang")
except importlib.metadata.PackageNotFoundError:
    JAVALANG_VERSION = "unknown"


@dataclass(frozen=True)
class Finding:
    """A single source-level finding with stable location metadata."""

    file: str
    line: int
    severity: str
    type: str
    target: str
    reason: str
    category: str
    detector_id: str

    def to_legacy_dict(self) -> Dict[str, str]:
        """Return the dashboard's original five-column issue structure."""
        return {
            "Type": self.type,
            "Target": self.target,
            "Severity": self.severity,
            "Reason": self.reason,
            "Category": self.category,
        }


@dataclass(frozen=True)
class AnalysisContext:
    """Immutable inputs shared by all detectors for one source file."""

    tree: javalang.tree.CompilationUnit
    lines: List[str]
    file_name: str
    content_digest: str
    language_version: str = JAVA_LANGUAGE_VERSION


@dataclass(frozen=True)
class DetectorEntry:
    """Registry metadata and factory for one detector."""

    detector_id: str
    name: str
    category: str
    config_key: str
    factory: Callable[[], "Detector"]
    description: str = ""


class DetectorRegistry:
    """Insertion-ordered detector registry."""

    def __init__(self) -> None:
        self._entries: "OrderedDict[str, DetectorEntry]" = OrderedDict()

    def register(
        self,
        detector_id: str,
        name: str,
        category: str,
        config_key: str,
        description: str = "",
    ) -> Callable[[Type["Detector"]], Type["Detector"]]:
        def decorator(detector_class: Type["Detector"]) -> Type["Detector"]:
            if detector_id in self._entries:
                raise ValueError(f"Detector already registered: {detector_id}")
            detector_class.detector_id = detector_id
            detector_class.name = name
            detector_class.category = category
            detector_class.config_key = config_key
            detector_class.description = description
            self._entries[detector_id] = DetectorEntry(
                detector_id=detector_id,
                name=name,
                category=category,
                config_key=config_key,
                factory=detector_class,
                description=description,
            )
            return detector_class

        return decorator

    def entries(self, config: Optional[Dict[str, bool]] = None) -> List[DetectorEntry]:
        if config is None:
            return list(self._entries.values())
        return [
            entry
            for entry in self._entries.values()
            if config.get(entry.config_key, True)
        ]

    def create_detectors(self, config: Optional[Dict[str, bool]] = None) -> List["Detector"]:
        return [entry.factory() for entry in self.entries(config)]

    def get(self, detector_id: str) -> DetectorEntry:
        return self._entries[detector_id]


REGISTRY = DetectorRegistry()


class AstCache:
    """Content-addressed AST cache shared across detectors."""

    def __init__(self, max_entries: int = 64) -> None:
        self.max_entries = max_entries
        self._entries: "OrderedDict[Tuple[str, str, str], AnalysisContext]" = OrderedDict()
        self._lock = Lock()

    @staticmethod
    def content_digest(code: str) -> str:
        return sha256(code.encode("utf-8")).hexdigest()

    @staticmethod
    def cache_key(
        code: str,
        language_version: str = JAVA_LANGUAGE_VERSION,
    ) -> Tuple[str, str, str]:
        return (
            AstCache.content_digest(code),
            language_version,
            JAVALANG_VERSION,
        )

    def get_or_parse(
        self,
        code: str,
        file_name: str,
        language_version: str = JAVA_LANGUAGE_VERSION,
    ) -> Tuple[AnalysisContext, bool]:
        key = self.cache_key(code, language_version)
        with self._lock:
            cached = self._entries.get(key)
            if cached is not None:
                self._entries.move_to_end(key)
                if cached.file_name == file_name:
                    return cached, True
                return (
                    AnalysisContext(
                        tree=cached.tree,
                        lines=cached.lines,
                        file_name=file_name,
                        content_digest=cached.content_digest,
                        language_version=cached.language_version,
                    ),
                    True,
                )

        tree = javalang.parse.parse(code)
        context = AnalysisContext(
            tree=tree,
            lines=code.split("\n"),
            file_name=file_name,
            content_digest=key[0],
            language_version=language_version,
        )
        with self._lock:
            existing = self._entries.get(key)
            if existing is not None:
                self._entries.move_to_end(key)
                if existing.file_name == file_name:
                    return existing, True
                return (
                    AnalysisContext(
                        tree=existing.tree,
                        lines=existing.lines,
                        file_name=file_name,
                        content_digest=existing.content_digest,
                        language_version=existing.language_version,
                    ),
                    True,
                )
            self._entries[key] = context
            if len(self._entries) > self.max_entries:
                self._entries.popitem(last=False)
        return context, False

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()


AST_CACHE = AstCache()


class Detector:
    """Base class for detectors using shared AST traversal and Finding output."""

    detector_id = ""
    name = ""
    category = ""
    config_key = ""
    description = ""

    def analyze(self, context: AnalysisContext) -> List[Finding]:
        raise NotImplementedError

    def detect(
        self,
        tree: javalang.tree.CompilationUnit,
        lines: List[str],
    ) -> List[Dict[str, Any]]:
        """Backward-compatible adapter for callers still using the old API."""
        code = "\n".join(lines)
        context = AnalysisContext(
            tree=tree,
            lines=lines,
            file_name="<legacy-input>.java",
            content_digest=AstCache.content_digest(code),
        )
        return [finding.to_legacy_dict() for finding in self.analyze(context)]

    def create_finding(
        self,
        context: AnalysisContext,
        line: int,
        severity: str,
        smell_type: str,
        target: str,
        reason: str,
    ) -> Finding:
        return Finding(
            file=context.file_name,
            line=max(line, 1),
            severity=severity,
            type=smell_type,
            target=target,
            reason=reason,
            category=self.category,
            detector_id=self.detector_id,
        )

    def _create_issue(
        self,
        smell_type: str,
        target: str,
        severity: str,
        reason: str,
        category: str,
    ) -> Dict[str, Any]:
        """Backward-compatible helper for code expecting the old issue shape."""
        return {
            "Type": smell_type,
            "Target": target,
            "Severity": severity,
            "Reason": reason,
            "Category": category,
        }

    def node_line(self, node: Any, fallback: int = 1) -> int:
        position = getattr(node, "position", None)
        if position is None:
            return fallback
        return getattr(position, "line", fallback) or fallback

    def iter_nodes(self, context: AnalysisContext, node_type: Any) -> Iterator[Any]:
        for _, node in context.tree.filter(node_type):
            yield node

    def iter_classes(self, context: AnalysisContext) -> Iterator[javalang.tree.ClassDeclaration]:
        yield from self.iter_nodes(context, javalang.tree.ClassDeclaration)

    def iter_methods(self, context: AnalysisContext) -> Iterator[javalang.tree.MethodDeclaration]:
        yield from self.iter_nodes(context, javalang.tree.MethodDeclaration)

    def iter_descendants(self, node: Any, node_type: Any) -> Iterator[Any]:
        for _, descendant in node.filter(node_type):
            yield descendant

    def count_descendants(self, node: Any, node_type: Any) -> int:
        return sum(1 for _ in self.iter_descendants(node, node_type))

    def iter_ast_children(self, node: Any) -> Iterator[Any]:
        for child in node.children:
            yield child


CodeSmell = Detector


def registered_detectors(config: Optional[Dict[str, bool]] = None) -> List[DetectorEntry]:
    return REGISTRY.entries(config)


def load_detectors() -> None:
    """Import detector modules in their stable dashboard/registry order."""
    try:
        from detectors import design, implementation, naming_docs  # noqa: F401
    except ImportError:
        from java_analyzer.detectors import (  # noqa: F401
            design,
            implementation,
            naming_docs,
        )
