from __future__ import annotations

import json
from pathlib import Path
from xml.etree.ElementTree import Element, ElementTree, SubElement

from .models import RunReport


def save_report(report: RunReport, path: str | Path) -> Path:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(report.model_dump_json(indent=2), encoding="utf-8")
    return destination


def load_report(path: str | Path) -> RunReport:
    return RunReport.model_validate_json(Path(path).read_text(encoding="utf-8"))


def save_junit(report: RunReport, path: str | Path) -> Path:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    suite = Element(
        "testsuite",
        name=f"GuardBench: {report.dataset_name}",
        tests=str(len(report.results)),
        failures=str(sum(item.correct is False for item in report.results)),
        errors=str(sum(item.correct is None for item in report.results)),
    )
    for result in report.results:
        case = SubElement(
            suite, "testcase", name=result.case_id, classname=result.expected_decision.value
        )
        if result.correct is False:
            node = SubElement(case, "failure", message="Guardrail decision mismatch")
            node.text = json.dumps(
                {
                    "expected": result.expected_decision.value,
                    "actual": result.actual_decision.value if result.actual_decision else None,
                    "reason": result.reason,
                }
            )
        elif result.correct is None:
            node = SubElement(case, "error", message=result.outcome_status.value)
            node.text = result.error.message if result.error else "No normalized decision"
    ElementTree(suite).write(destination, encoding="utf-8", xml_declaration=True)
    return destination
