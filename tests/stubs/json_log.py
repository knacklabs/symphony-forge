"""Publish complete JSON log snapshots when third-party stubs run concurrently."""
import json
import os
import time


def append_json(path, value):
    # Windows append mode seeks before each write; concurrent handles can overwrite
    # each other. Lock a separate file so readers see only complete old/new snapshots.
    with path.with_suffix(path.suffix + ".lock").open("a+b") as lock:
        lock.seek(0)
        if os.name == "nt":
            import msvcrt
            msvcrt.locking(lock.fileno(), msvcrt.LK_LOCK, 1)
        else:
            import fcntl
            fcntl.flock(lock, fcntl.LOCK_EX)
        try:
            previous = path.read_text("utf-8") if path.exists() else ""
            temp = path.with_suffix(path.suffix + f".{os.getpid()}.tmp")
            temp.write_text(previous + json.dumps(value) + "\n", encoding="utf-8", newline="\n")
            # Windows readers can briefly hold the destination open.
            for attempt in range(100):
                try:
                    temp.replace(path)
                    break
                except PermissionError:
                    if attempt == 99:
                        raise
                    time.sleep(0.05)
        finally:
            if os.name == "nt":
                lock.seek(0)
                msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(lock, fcntl.LOCK_UN)
