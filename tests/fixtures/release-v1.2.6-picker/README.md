The replay records the changed paths from v1.2.6's parent to v1.2.6.
Python files, forge.toml, uv.lock and pyproject.toml retain their exact text.
Other non-Python files use before/after markers because their content does
not enter selection. Missing parent files remain null.

The test copies the current candidate suite, then applies these changes.
This deliberately measures the release against the current suite and works
in shallow CI checkouts without historical tags or binary archives.
