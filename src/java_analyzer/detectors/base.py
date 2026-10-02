"""
Detector infrastructure for the Java static analyzer.

This module is the single home for everything the individual smell
detectors share:

* :class:`Finding`            - uniform violation record (file / line /
                                severity plus the descriptive fields the
                                dashboard needs).
* :class:`Detector`           - abstract base class (formerly
                                ``CodeSmell``) providing shared AST
                                traversal and the one-and-only violation
                                builder.
* :class:`DetectorRegistry`   - ordered registry; registration order is
                                the dashboard catalog order.
* :class:`AnalysisContext`   - per-run bundle (source, parsed AST,
                                shared traversal memos, cache stats).
* :class:`AstCache`           - cross-run parse cache whose key binds the
                                source content digest *and* the parser
                                language version, so two files can never
                                alias each other.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from hashlib import sha256
from typing import Any, Dict, List, Optional, Tuple, Type

import javalang

try:
    import importlib.metadata as _importlib_metadata
except ImportError:  # pragma: no cover
    import importlib_metadata as _importlib_metadata


def _resolve_parser_version() -> str:
    """Return the language/parser version the AST cache is bound to."""
    version = getattr(javalang, "__version__", None)
    if not version:
        try:
            version = _importlib_metadata.version("javalang")
        except _importlib_metadata.PackageNotFoundError:
            version = "unknown"
    return f"javalang-{version}"


#: Parser/grammar version. Bumped into every cache key so a parser upgrade
#: can never serve an AST produced by an older grammar.
PARSER_LANGUAGE_VERSION: str = _resolve_parser_version()

#: Default file label when the caller never supplied a file name.
UNKNOWN_FILE: str = "<source>.java"


@dataclass
class Finding:
    """Uniform violation record produced by every detector."""

    file: str
    line: Optional[int]
    severity: str
    smell_type: str
    target: str
    reason: str
    category: str
    detector: str

    def to_issue(self) -> Dict[str, Any]:
        """
        Adapter: project the finding onto the legacy issue dictionary
        consumed by ``analyzer_engine`` / ``dashboard``. The legacy
        contract (keys, value formats and ordering) is preserved exactly.
        """
        return {
            "Type": self.smell_type,
            "Target": self.target,
            "Severity": self.severity,
            "Reason": self.reason,
            "Category": self.category,
        }

    def to_record(self) -> Dict[str, Any]:
        """Serializable view (used for session state / catalog panel)."""
        return {
            "File": self.file,
            "Line": self.line if self.line is not None else "-",
            "Severity": self.severity,
            "Type": self.smell_type,
            "Target": self.target,
            "Reason": self.reason,
            "Category": self.category,
            "Detector": self.detector,
        }


@dataclass
class CacheStats:
    """Cache counters for a single analysis run."""

    hits: int = 0
    misses: int = 0

    def as_dict(self) -> Dict[str, int]:
        return {"hits": self.hits, "misses": self.misses}


class AstCache:
    """
    Process-wide parsed-AST cache.

    The cache key binds a SHA-256 digest of the *exact* source bytes to
    the parser language version. Sharing is content-addressed: different
    files (or an edited file) get a different key, while the unchanged
    file reuses its AST. A parser upgrade invalidates every entry
    automatically.
    """

    def __init__(self) -> None:
        self._entries: Dict[Tuple[str, str], javalang.tree.CompilationUnit] = {}

    @staticmethod
    def make_key(code: str) -> Tuple[str, str]:
        digest = sha256(code.encode("utf-8")).hexdigest()
        return digest, PARSER_LANGUAGE_VERSION

    def parse(
        self, code: str, stats: Optional[CacheStats] = None
    ) -> javalang.tree.CompilationUnit:
        """
        Return a parsed AST for ``code``, reusing a cached one when the
        content digest and language version match.
        """
        key = self.make_key(code)
        tree = self._entries.get(key)
        if tree is not None:
            if stats is not None:
                stats.hits += 1
            return tree

        tree = javalang.parse.parse(code)
        self._entries[key] = tree
        if stats is not None:
            stats.misses += 1
        return tree

    def __len__(self) -> int:
        return len(self._entries)


#: Cache that survives Streamlit reruns (the module is imported once per
#: server process), so the second run on an unchanged file hits it.
SHARED_AST_CACHE = AstCache()


class AnalysisContext:
    """
    Per-analysis bundle shared by every detector.

    Holds the source, the single parsed AST and memos of shared
    traversals (classes / methods are walked once per run and reused), so
    detectors never re-parse or duplicate the same ``tree.filter`` pass.
    """

    def __init__(
        self,
        code: str,
        tree: javalang.tree.CompilationUnit,
        file_name: Optional[str] = None,
        cache_stats: Optional[CacheStats] = None,
    ) -> None:
        self.code = code
        self.lines = code.split("\n")
        self.tree = tree
        self.file_name = file_name or UNKNOWN_FILE
        self.cache_stats = cache_stats or CacheStats()
        self._classes: Optional[List[Tuple[Any, javalang.tree.ClassDeclaration]]] = None
        self._methods: Optional[List[Tuple[Any, javalang.tree.MethodDeclaration]]] = None

    def iter_classes(self):
        """Shared, memoized class-declaration traversal."""
        if self._classes is None:
            self._classes = list(self.tree.filter(javalang.tree.ClassDeclaration))
        return iter(self._classes)

    def iter_methods(self):
        """Shared, memoized method-declaration traversal."""
        if self._methods is None:
            self._methods = list(self.tree.filter(javalang.tree.MethodDeclaration))
        return iter(self._methods)


class Detector(ABC):
    """
    Abstract base class for all code smell detectors.

    Subclasses declare their metadata (``config_key`` / ``display_name``
    / ``category``) and implement :meth:`analyze` returning
    :class:`Finding` objects. All violations go through :meth:`finding`
    so violation strings are assembled in exactly one place.
    """

    #: Key used in the engine configuration dictionary.
    config_key: str = ""
    #: Human readable name shown in the dashboard catalog.
    display_name: str = ""
    #: Category label attached to every finding of this detector.
    category: str = ""

    @abstractmethod
    def analyze(self, ctx: AnalysisContext) -> List[Finding]:
        """Detect smells and return findings."""
        raise NotImplementedError

    # -- shared traversal helpers -------------------------------------

    @staticmethod
    def node_line(node: Any) -> Optional[int]:
        """Return the 1-based source line of an AST node, if known."""
        position = getattr(node, "position", None)
        if position is None:
            return None
        return getattr(position, "line", None)

    @staticmethod
    def count_branches(method_node: javalang.tree.MethodDeclaration) -> int:
        """
        Cyclomatic branch count (baseline 1) shared by the implementation
        detector and the metrics engine.
        """
        branch_types = (
            javalang.tree.IfStatement,
            javalang.tree.WhileStatement,
            javalang.tree.DoStatement,
            javalang.tree.ForStatement,
            javalang.tree.CatchClause,
            javalang.tree.SwitchStatementCase,
            javalang.tree.TernaryExpression,
        )
        count = 1
        for _path, _node in method_node.filter(branch_types):
            count += 1
        return count

    # -- the one violation builder ------------------------------------

    def finding(
        self,
        ctx: AnalysisContext,
        smell_type: str,
        target: str,
        severity: str,
        reason: str,
        node: Any = None,
        line: Optional[int] = None,
    ) -> Finding:
        """Create a standardized finding bound to file and source line."""
        if line is None:
            line = self.node_line(node)
        return Finding(
            file=ctx.file_name,
            line=line,
            severity=severity,
            smell_type=smell_type,
            target=target,
            reason=reason,
            category=self.category,
            detector=self.config_key,
        )

    # -- legacy contract adapter --------------------------------------

    def detect(
        self,
        tree: javalang.tree.CompilationUnit,
        lines: List[str],
        file_name: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Backward-compatible entry point (formerly ``CodeSmell.detect``):
        run :meth:`analyze` and project findings to the legacy issue
        dictionaries.
        """
        code = "\n".join(lines)
        ctx = AnalysisContext(code=code, tree=tree, file_name=file_name)
        return [item.to_issue() for item in self.analyze(ctx)]


class DetectorRegistry:
    """
    Ordered detector registry.

    Registration order is the only source of truth for the order in
    which detectors run and appear in the dashboard catalog, so the same
    sample always produces the same finding/catalog order.
    """

    def __init__(self) -> None:
        self._classes: Dict[str, Type[Detector]] = {}
        self._order: List[str] = []

    def register(self, detector_cls: Type[Detector]) -> Type[Detector]:
        """Register a detector class (idempotent per ``config_key``)."""
        key = detector_cls.config_key
        if not key:
            raise ValueError(f"{detector_cls.__name__} must define a config_key")
        if key in self._classes:
            # Re-registration of the same key is allowed: importlib
            # reload re-executes class bodies, and the same registry is
            # intentionally kept (order preserved). A genuinely different
            # class stealing an existing key is still a programming error.
            if self._classes[key].__name__ == detector_cls.__name__:
                self._classes[key] = detector_cls
                return detector_cls
            raise ValueError(f"Detector '{key}' is already registered")
        self._classes[key] = detector_cls
        self._order.append(key)
        return detector_cls

    def get(self, key: str) -> Type[Detector]:
        return self._classes[key]

    def ordered_classes(self) -> List[Type[Detector]]:
        """All detector classes in registration order."""
        return [self._classes[key] for key in self._order]

    def entries(self) -> List[Tuple[str, Type[Detector]]]:
        """All (config_key, detector class) pairs in registration order."""
        return [(key, self._classes[key]) for key in self._order]

    def keys(self) -> List[str]:
        return list(self._order)

    def __len__(self) -> int:
        return len(self._order)


#: Process-wide ordered registry.
REGISTRY = DetectorRegistry()

#: Backward-compatible alias kept for the original ``CodeSmell`` import.
CodeSmell = Detector
