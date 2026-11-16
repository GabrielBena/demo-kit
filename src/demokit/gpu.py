"""The cards of a shared box, live: who is on each one, and whether a run may move there.

A live page shows these cards and moves its run to a card clicked on (`live.serve`'s ``move``).
On a shared machine that move has a rule: **never join a card another user's job is on**. A card
is *free* when no other user has a compute process on it and little memory is resident, which also
catches a job tearing down or a context the process query missed. A card holding only our own
processes is *ours*, and a run may move there too. The owner of each process comes from ``ps``:
``nvidia-smi`` gives a process's id and memory, not who started it.

Best effort, never raising: without ``nvidia-smi``, or on any error or unreadable line, there are
no cards, and a run stays on the CPU. A card is named by its UUID wherever a run is pinned to it
(``CUDA_VISIBLE_DEVICES=GPU-...``), so the CUDA and driver index orders cannot disagree.
"""

from __future__ import annotations

import getpass
import shutil
import subprocess

FREE_BELOW_MIB = 2000  # more resident than this with no process listed: someone is there


def _run(command: list[str]) -> str | None:
    try:
        out = subprocess.run(command, capture_output=True, text=True, timeout=8)
    except Exception:
        return None
    return out.stdout if out.returncode == 0 else None


def _number(text: str) -> int | None:
    try:
        return int(float(text))
    except ValueError:
        return None  # "[N/A]" under MIG or without permission


def parse(gpus: str, apps: str, owners: dict[str, str], me: str) -> list[dict]:
    """The cards, from ``nvidia-smi``'s two CSV queries and each process's owner.

    ``gpus`` holds ``index, name, memory.used, memory.total, uuid, utilization.gpu`` a line, and
    ``apps`` holds ``gpu_uuid, pid`` a line. A card is::

        {"index": 0, "uuid": "GPU-...", "name": "RTX 4090", "used": 620, "total": 24564,
         "util": 3, "users": ["me"], "mine": True, "free": True}

    with memory in MiB and ``util`` in percent (``None`` where unreported).
    """
    users: dict[str, set[str]] = {}
    for line in apps.splitlines():
        parts = [p.strip() for p in line.split(",")]
        if len(parts) >= 2 and parts[1]:
            users.setdefault(parts[0], set()).add(owners.get(parts[1], "?"))
    cards = []
    for line in gpus.splitlines():
        parts = [p.strip() for p in line.split(",")]
        if len(parts) < 6 or _number(parts[0]) is None:
            continue
        index, name, used, total, uuid, util = parts[:6]
        on = users.get(uuid, set())
        used_mib, mine = _number(used), me in on
        others = bool(on - {me})
        quiet = used_mib is not None and used_mib < FREE_BELOW_MIB
        cards.append(
            {
                "index": int(index),
                "uuid": uuid,
                "name": name.replace("NVIDIA", "").replace("GeForce", "").strip() or name,
                "used": used_mib,
                "total": _number(total),
                "util": _number(util),
                "users": sorted(on),
                "mine": mine,
                "free": not others and (mine or quiet),
            }
        )
    return cards


def cards(me: str | None = None) -> list[dict]:
    """Every card on the machine as it stands, each with its users (see `parse`); never raises."""
    if shutil.which("nvidia-smi") is None:
        return []
    query = "index,name,memory.used,memory.total,uuid,utilization.gpu"
    gpus = _run(["nvidia-smi", f"--query-gpu={query}", "--format=csv,noheader,nounits"])
    apps = _run(["nvidia-smi", "--query-compute-apps=gpu_uuid,pid", "--format=csv,noheader"])
    if gpus is None or apps is None:
        return []
    pids = [line.split(",")[1].strip() for line in apps.splitlines() if line.count(",") >= 1]
    owners: dict[str, str] = {}
    if pids:  # `user:32` widens ps's owner column past its 8 characters ("someuse+")
        listing = _run(["ps", "-o", "pid=,user:32=", "-p", ",".join(pids)]) or ""
        owners = dict(line.split()[:2] for line in listing.splitlines() if len(line.split()) >= 2)
    return parse(gpus, apps, owners, me or getpass.getuser())
