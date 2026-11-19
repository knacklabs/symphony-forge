These plain text files are copied from the named git release tags. They keep the
historical command, checks, review, pin-dispatch and queue code in the command
regression. The harness supplies other modules from the current checkout, and
supplies the existing Python fixture for v1.2.2.

The test runs the installed launcher's actual bootstrap and the released command
entry points. Its uv stub replaces package acquisition only. It does not replace
CI waiting or command behavior. This proves the historical boundaries named in
the regression; it does not test downloading or installing a historical package.
