"""JUnit XML reporter for OQLos scenario results.

Produces output compatible with Jenkins, GitLab CI, GitHub Actions, etc.

Usage (programmatic):
    from oqlos.reporters.junit import JUnitReporter
    xml = JUnitReporter().generate(script_result)
    Path("results.xml").write_text(xml)

Usage (CLI):
    oqlctl run scenario.oql --output junit > results.xml
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from oqlos.core.base import ScriptResult


class JUnitReporter:
    """Generate JUnit XML from a ScriptResult."""

    def generate(self, result: "ScriptResult", suite_name: str | None = None) -> str:
        """Serialise *result* to JUnit XML string.

        Args:
            result:     Completed ScriptResult (from OqlInterpreter.execute).
            suite_name: Override testsuite name (defaults to result.source).

        Returns:
            UTF-8 XML string suitable for writing to a .xml file.
        """
        name = suite_name or result.source
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")

        root = ET.Element("testsuites")
        suite = ET.SubElement(
            root, "testsuite",
            name=name,
            tests=str(len(result.steps)),
            failures=str(result.failed),
            errors="0",
            skipped=str(sum(1 for s in result.steps if s.status.value == "skipped")),
            time=f"{result.duration_ms / 1000:.3f}",
            timestamp=timestamp,
        )

        if result.errors:
            props = ET.SubElement(suite, "properties")
            for i, err in enumerate(result.errors):
                ET.SubElement(props, "property", name=f"error_{i}", value=err)

        for step in result.steps:
            self._add_testcase(suite, name, step)

        ET.indent(root, space="  ")
        return ET.tostring(root, encoding="unicode", xml_declaration=True)

    @staticmethod
    def _add_testcase(suite: ET.Element, classname: str, step) -> None:
        """Append a <testcase> element for *step*."""
        case = ET.SubElement(
            suite, "testcase",
            classname=classname,
            name=step.name,
            time=f"{step.duration_ms / 1000:.3f}",
        )
        status = step.status.value
        if status == "failed":
            ET.SubElement(case, "failure", message=step.message or "assertion failed")
        elif status == "error":
            ET.SubElement(case, "error", message=step.message or "unexpected error")
        elif status == "skipped":
            ET.SubElement(case, "skipped")

        if step.message and status not in ("failed", "error"):
            case.text = step.message


def report_junit(result: "ScriptResult", suite_name: str | None = None) -> str:
    """Convenience function — wraps JUnitReporter().generate()."""
    return JUnitReporter().generate(result, suite_name=suite_name)
