"""Combine pytest JUnit reports into a pytest-split duration map."""

import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


def node_id(case):
    parts = case.attrib["classname"].split(".")
    for count in range(len(parts), 0, -1):
        source = Path(*parts[:count]).with_suffix(".py")
        if source.is_file():
            return "::".join((source.as_posix(), *parts[count:], case.attrib["name"]))
    raise ValueError(f"No test file for JUnit class {case.attrib['classname']!r}")


def main(output, reports):
    durations = {}
    for report in reports:
        for case in ET.parse(report).iter("testcase"):
            identity = node_id(case)
            if identity in durations:
                raise ValueError(f"Duplicate test across shards: {identity}")
            durations[identity] = float(case.attrib["time"])
    if not durations:
        raise ValueError("No JUnit test cases found")
    Path(output).write_text(json.dumps(durations, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2:])
