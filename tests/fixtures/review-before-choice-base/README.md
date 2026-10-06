# Review implementation before saved choice bases

`close.py` and `review.py` are the unmodified source files from Forge commit
`ead5fa3b90b590e25c99f387b6e660e07bc8376b`, before this fix. The upgrade command
tests copy these text files over a temporary Forge package and run its real
entry point to record stopped reviews. They then switch to the current command
to apply the owner's choice; no review fingerprints or bases are fabricated.
