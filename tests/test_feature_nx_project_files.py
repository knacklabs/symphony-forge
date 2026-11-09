"""Generated features keep Nx configuration keys and rename starter names."""
import json

import pytest

from test_feature_command import _adopted_starter
from test_setup import _fresh_client

STORY = "feature-keeps-projecttype"


@pytest.mark.platform
@pytest.mark.parametrize("adopted", [False, True], ids=["new", "earlier-adopted"])
def test_1_feature_keeps_nx_keys_and_renames_project_names(repo, gh, tmp_path, adopted):
    # Audit: protect the generated Nx contract against substring replacement.
    # Existing feature tests check tags, but never read projectType. Exercise
    # the real command with existing client fixtures and no production seam.
    if adopted:
        client = _adopted_starter(repo)
    else:
        client, initialized = _fresh_client(repo, gh, tmp_path, "--starter", "react")
        assert initialized.returncode == 0, initialized.stdout + initialized.stderr
    built = repo.forge("task", "feature", "notes", "--one", "note", "--field", "title:text", cwd=client)
    assert built.returncode == 0, built.stdout + built.stderr
    for kind in ("contracts", "server"):
        project = json.loads((client / f"libs/notes/{kind}/project.json").read_text("utf-8"))
        assert project["projectType"] == "library"
        assert project["name"] == f"@app/notes-{kind}"
        assert project["sourceRoot"] == f"libs/notes/{kind}/src"
        assert project["tags"] == [f"type:{kind}", "scope:notes"]
        assert project["targets"]["lint"]["options"]["command"] == f"eslint libs/notes/{kind}"
