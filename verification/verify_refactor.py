import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "src" / "java_analyzer"))

from analyzer_engine import StaticAnalyzerEngine
from detectors.base import REGISTRY, SHARED_AST_CACHE, Finding

baseline = json.loads((ROOT / "verification" / "baseline_before_refactor.json").read_text(encoding="utf-8"))
sample_path = ROOT / "samples" / "OrderProcessorSample.java"
code = sample_path.read_text(encoding="utf-8")
FILE_NAME = sample_path.name


def run(code_text):
    engine = StaticAnalyzerEngine(code_text)
    engine.file_name = FILE_NAME
    issues, tree = engine.run()
    metrics = engine.calculate_metrics(tree)
    return engine, issues, metrics


failures = []

# 1. First run (cold cache)
engine1, issues1, metrics1 = run(code)

# 2. Second run on unchanged content (warm cache)
engine2, issues2, metrics2 = run(code)

print("registry order:", REGISTRY.keys())
print("cache size:", len(SHARED_AST_CACHE))
print("run1 stats:", engine1.cache_stats)
print("run2 stats:", engine2.cache_stats)

# legacy output must be byte-for-byte identical in content and order
base_issues = baseline["issues"]
if issues1 != base_issues:
    failures.append("legacy issue list differs from baseline")
    for i, (a, b) in enumerate(zip(base_issues, issues1)):
        if a != b:
            print("DIFF row", i, "\n base:", a, "\n now :", b)
    print("baseline count:", len(base_issues), "now:", len(issues1))

if len(issues1) != baseline["issue_count"]:
    failures.append("issue count differs")

if issues1 != issues2:
    failures.append("two runs produced different order/content")

if metrics1 != baseline["metrics"] or metrics2 != baseline["metrics"]:
    failures.append("metrics differ from baseline")
    print("base metrics:", baseline["metrics"])
    print("now  metrics:", metrics1)

if engine1.cache_stats["hits"] != 0 or engine1.cache_stats["misses"] != 1:
    failures.append(f"cold run stats wrong: {engine1.cache_stats}")
if engine2.cache_stats["hits"] != 1 or engine2.cache_stats["misses"] != 0:
    failures.append(f"warm run stats wrong: {engine2.cache_stats}")

# catalog checks
catalog = engine2.catalog
cat_keys = [entry["config_key"] for entry in catalog]
if cat_keys != REGISTRY.keys():
    failures.append("catalog order != registry order")
if cat_keys != ["design", "implementation", "naming", "documentation"]:
    failures.append(f"unexpected catalog order: {cat_keys}")

counts = {entry["config_key"]: entry["count"] for entry in catalog}
expected_counts = {}
for issue in issues1:
    expected_counts[issue["Category"].lower()] = expected_counts.get(issue["Category"].lower(), 0) + 1
# Category labels vs config keys: Design/Implementation/Naming/Documentation
mapping = {"design": "design", "implementation": "implementation",
           "naming": "naming", "documentation": "documentation"}
for key in cat_keys:
    if counts[key] != expected_counts.get(mapping[key], 0):
        failures.append(f"catalog count mismatch for {key}")

# findings carry file / line / severity
all_findings = engine2.findings
if not all_findings or not all(isinstance(f, Finding) for f in all_findings):
    failures.append("findings not all Finding instances")
missing = [f for f in all_findings if f.file != FILE_NAME or f.line is None or not f.severity]
if missing:
    failures.append(f"{len(missing)} findings missing file/line/severity")

lines = code.split("\n")
for f in all_findings:
    if not (1 <= f.line <= len(lines)):
        failures.append(f"finding line out of range: {f.target} L{f.line}")

# 3. Edited content => cache misses back to zero hits; conclusions change
edited = code.replace("    private boolean flag5;\n", "")
engine3, issues3, _ = run(edited)
print("edited run stats:", engine3.cache_stats)
if engine3.cache_stats["hits"] != 0 or engine3.cache_stats["misses"] != 1:
    failures.append(f"edited run stats wrong: {engine3.cache_stats}")
god_before = [i for i in issues1 if i["Type"] == "God Class"]
god_after = [i for i in issues3 if i["Type"] == "God Class"]
if god_before and god_after:
    failures.append("editing one field did not change conclusions (God Class still present)")
if issues3 == issues1:
    failures.append("edited sample produced identical issues")
print("God Class before:", len(god_before), "after:", len(god_after))

# 4. Different file with different content never aliases
other = "class Other { public void x() {} }\n"
engine4 = StaticAnalyzerEngine(other)
engine4.file_name = "Other.java"
issues4, _ = engine4.run()
print("other file stats:", engine4.cache_stats, "issues:", len(issues4))
if engine4.cache_stats["hits"] != 0:
    failures.append("different content should not hit cache")
# repeat original -> hit again
engine5, issues5, _ = run(code)
if engine5.cache_stats["hits"] != 1:
    failures.append("original content should hit cache after other-file interleave")

# 5. partial config respects registry ordering/filtering
engine6 = StaticAnalyzerEngine(code, {"design": False, "implementation": True,
                                      "naming": False, "documentation": True})
engine6.file_name = FILE_NAME
issues6, _ = engine6.run()
cats = {i["Category"] for i in issues6}
if cats != {"Implementation", "Documentation"}:
    failures.append(f"config filtering wrong: {cats}")
disabled = {e["config_key"]: e["enabled"] for e in engine6.catalog}
if disabled != {"design": False, "implementation": True, "naming": False, "documentation": True}:
    failures.append(f"catalog enabled flags wrong: {disabled}")

# dump findings with file/line for the report
report = {
    "total": len(all_findings),
    "cache_cold": engine1.cache_stats,
    "cache_warm": engine2.cache_stats,
    "cache_edited": engine3.cache_stats,
    "catalog_order": cat_keys,
    "counts": counts,
    "findings": [
        {"file": f.file, "line": f.line, "severity": f.severity,
         "category": f.category, "type": f.smell_type, "target": f.target,
         "reason": f.reason}
        for f in all_findings
    ],
}
(ROOT / "verification" / "findings_after_refactor.json").write_text(
    json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

print("\n".join(f"- {f.file}:{f.line} [{f.severity}] {f.category}/{f.smell_type} -> {f.target}"
                for f in all_findings))

if failures:
    print("\nFAILURES:")
    for item in failures:
        print(" *", item)
    sys.exit(1)
print("\nALL CHECKS PASSED:", len(all_findings), "findings")


