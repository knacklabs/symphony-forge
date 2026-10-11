"""Close's temporary client-side pytest hook; worker tests and CI never load it."""
import hashlib
import json
import os
import re
import subprocess
import tempfile
from pathlib import Path

import pytest


def pytest_configure(config):
    root = os.environ.get("FORGE_REPAIR_ROOT")
    if not root:
        return
    top = Path(root)
    if not Path(config.invocation_params.dir).resolve().is_relative_to(top):
        return
    if not Path(config.rootpath).resolve().is_relative_to(top):
        return  # A test may itself launch pytest in another repository.
    repair = Repair(config, top)
    config.pluginmanager.register(repair, "forge-repair")
    if any(record.get("outcome") == "failed" for record in repair.records.values()):
        # Finish failures before starting other tests, including with xdist enabled.
        if hasattr(config.option, "numprocesses"):
            config.option.numprocesses = 0
            config.option.dist = "no"
            config.option.tx = []


class Repair:
    def __init__(self, config, top):
        self.config, self.top = config, top
        args = list(config.invocation_params.args)
        # The picker changes ignored files, not the configured test invocation.
        if "_forge_pytest_selection" in args:
            index = args.index("_forge_pytest_selection")
            if index and args[index - 1] == "-p":
                del args[index - 1:index + 1]
        environment = dict(os.environ)
        environment["PYTHONPATH"] = os.pathsep.join(
            path for path in environment.get("PYTHONPATH", "").split(os.pathsep)
            if not any((Path(path) / name).is_file() for name in
                       ("_forge_pytest_repair.py", "_forge_pytest_selection.py")))
        key = hashlib.sha256(json.dumps([str(Path(config.invocation_params.dir).resolve()),
                                         args, environment], sort_keys=True).encode()).hexdigest()
        worker = getattr(config, "workerinput", {})
        self.cache = Path(worker.get("forge_repair_cache") or
                          Path(os.environ["FORGE_REPAIR_CACHE"]) / (key + ".json"))
        try:
            self.records = json.loads(self.cache.read_text("utf-8"))
        except (FileNotFoundError, ValueError):
            self.records = {}
        self.keys, self.reports, self.reused = {}, {}, 0
        self.clean = not subprocess.run(["git", "status", "--porcelain"], cwd=top,
                                        check=True, capture_output=True, text=True).stdout
        listing = subprocess.run(["git", "ls-tree", "-r", "-z", "--full-tree", "HEAD"],
                                 cwd=top, check=True, capture_output=True, text=True).stdout
        self.files = {path: entry for row in listing.split("\0") if row
                      for entry, _, path in [row.partition("\t")]
                      if not path.startswith(".factory/")}
        tests = {path for path in self.files if path.endswith(".py") and
                 (Path(path).name.startswith("test_") or Path(path).name.endswith("_test.py"))}
        # Imported test helpers are shared inputs too, even if pytest also collects them.
        referenced = set()
        for path in self.files:
            if path.endswith(".py") and (top / path).is_file():
                referenced.update(word for word in re.findall(r"\b\w+\b", (top / path).read_text("utf-8", errors="replace"))
                                  if word != Path(path).stem)
        # shortcut: production files invalidate all passes; dependency tracing needs a separate change.
        shared = [path + "\0" + entry for path, entry in self.files.items()
                  if path not in tests or Path(path).stem in referenced]
        self.shared = hashlib.sha256("\0".join(shared).encode()).hexdigest()

    @pytest.hookimpl(trylast=True)
    def pytest_collection_modifyitems(self, items):
        selected, reused = [], []
        self.records = {item.nodeid: self.records[item.nodeid] for item in items
                        if item.nodeid in self.records}
        for item in items:
            file = Path(str(item.fspath)).resolve()
            path = file.relative_to(self.top).as_posix() if file.is_relative_to(self.top) else None
            # Tests outside the committed tree are never reused.
            key = self.shared + self.files[path] if self.clean and path in self.files else None
            self.keys[item.nodeid] = key
            old = self.records.get(item.nodeid, {})
            if key and old == {"key": key, "outcome": "passed"}:
                reused.append(item)
            else:
                selected.append(item)
        selected.sort(key=lambda item: self.records.get(item.nodeid, {}).get("outcome") != "failed")
        items[:] = selected
        self.reused = len(reused)
        if reused:
            self.config.hook.pytest_deselected(items=reused)

    @pytest.hookimpl(hookwrapper=True)
    def pytest_runtest_makereport(self, item, call):
        report = (yield).get_result()
        report.user_properties.append(("forge_repair_key", self.keys.get(item.nodeid)))

    @pytest.hookimpl(tryfirst=True)
    def pytest_runtest_setup(self):
        # A test's child commands must run normally, without this close's receipts.
        os.environ.pop("FORGE_REPAIR_ROOT", None)
        os.environ.pop("FORGE_REPAIR_CACHE", None)
        plugins = [name for name in os.environ.get("PYTEST_PLUGINS", "").split(",")
                   if name.strip() and name.strip() != "_forge_pytest_repair"]
        if plugins:
            os.environ["PYTEST_PLUGINS"] = ",".join(plugins)
        else:
            os.environ.pop("PYTEST_PLUGINS", None)

    @pytest.hookimpl(optionalhook=True)
    def pytest_configure_node(self, node):
        node.workerinput["forge_repair_cache"] = str(self.cache)

    def pytest_runtest_logreport(self, report):
        key = dict(report.user_properties).get("forge_repair_key")
        if key is None:
            return
        reports = self.reports.setdefault(report.nodeid, {})
        reports[report.when] = report.outcome
        # A passing call is insufficient: setup and teardown must pass as well.
        outcome = ("passed" if reports == {"setup": "passed", "call": "passed", "teardown": "passed"}
                   else "failed")
        self.records[report.nodeid] = {"key": key, "outcome": outcome}

    @pytest.hookimpl(optionalhook=True)
    def pytest_testnodedown(self, node):
        self.reused = max(self.reused, node.workeroutput.get("forge_repair_reused", 0))

    def pytest_sessionfinish(self, session):
        if hasattr(self.config, "workerinput"):
            self.config.workeroutput["forge_repair_reused"] = self.reused
            return
        if self.config.option.collectonly:
            return
        if session.exitstatus == 5 and self.reused:
            session.exitstatus = 0
        self.cache.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=self.cache.parent,
                                         delete=False) as saved:
            json.dump(self.records, saved)
        Path(saved.name).replace(self.cache)

    def pytest_terminal_summary(self, terminalreporter):
        if self.reused:
            terminalreporter.write_line(f"Reused {self.reused} unchanged passing tests on this machine.")
