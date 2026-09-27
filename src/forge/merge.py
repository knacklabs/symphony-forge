"""The merge command's permission gate; merging is added by the MERGE task."""
from __future__ import annotations

import argparse

from forge import repo

REFUSALS = {
    "disabled": ("forge merge is disabled by merge = \"human\" in the default branch's forge.toml.",
                 "ask the repo owner to set merge = \"agent\" on the default branch"),
    "not_built": ("forge merge is not ready to merge pull requests yet.",
                  "ask a human to merge this pull request"),
}


def merge(args: argparse.Namespace) -> int:
    config = repo.default_config(repo.root())
    if config["merge"] != "agent":
        repo.refuse(REFUSALS["disabled"])
    repo.refuse(REFUSALS["not_built"])
