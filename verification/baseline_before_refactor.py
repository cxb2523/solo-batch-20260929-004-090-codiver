import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "src" / "java_analyzer"))

from analyzer_engine import StaticAnalyzerEngine

code = (ROOT / "samples" / "OrderProcessorSample.java").read_text(encoding="utf-8")
engine = StaticAnalyzerEngine(code)
issues, tree = engine.run()
metrics = engine.calculate_metrics(tree)

out = {
    "issue_count": len(issues),
    "issues": issues,
    "metrics": metrics,
}
(ROOT / "verification" / "baseline_before_refactor.json").write_text(
    json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8"
)
print(len(issues))
for i in issues:
    print(i["Category"], "|", i["Type"], "|", i["Target"], "|", i["Severity"], "|", i["Reason"])
print(json.dumps(metrics))

