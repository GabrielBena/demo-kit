"""GPU occupancy + etiquette for shared boxes — reporting, and a *polite* auto-picker.

Live-demo servers stay on CPU; when a user opts a heavier job onto a GPU, the demo may auto-pick
a card only under strict shared-workstation etiquette:

* **Allowlisted names only.** ``pick_free_gpu`` matches cards by NAME (robust to CUDA-vs-driver
  index reordering); cards outside the allowlist are never auto-picked, even when idle.
* **Never step on a running job.** A card is "free" only with **no compute processes** *and* low
  used-memory — never pile onto a co-tenant's job (or your own). An idle card is yours to take; an
  occupied one is hands-off.
* **Forcing is human-only.** ``gpu_by_index`` resolves any card with **no** etiquette filter — a
  deliberate per-use choice, informed by the :func:`list_gpus` occupancy panel (which names each
  process's owner via ``ps``).
* **Best-effort.** Any ``nvidia-smi`` hiccup (missing binary, non-zero exit, parse error) → empty
  result → the caller falls back to CPU. Never raises.

Pinning is by **UUID** (``CUDA_VISIBLE_DEVICES=GPU-…`` in the launched job) — unambiguous, no
index-order trap.
"""

from __future__ import annotations

import shutil
import subprocess

# A card with more than this resident (MiB) is treated as busy even if the compute-apps query
# missed it (residual contexts, a job mid-teardown, MIG, …) — conservative on a shared box.
_DEFAULT_FREE_MEM_CEIL_MIB = 2000.0


def _smi(args: list[str]) -> str | None:
    try:
        out = subprocess.run(["nvidia-smi", *args], capture_output=True, text=True, timeout=8)
    except Exception:
        return None
    return out.stdout.strip() if out.returncode == 0 else None


def pick_free_gpu(
    *, name_match: str | None = None, free_mem_ceil_mib: float = _DEFAULT_FREE_MEM_CEIL_MIB
) -> dict | None:
    """The first genuinely-free allowlisted card as ``{'uuid', 'index', 'label'}``, else ``None``.

    "Free" = a card whose name contains ``name_match``, with no compute processes and
    < ``free_mem_ceil_mib`` resident — safe to use without disturbing anyone. Deterministic
    (lowest index first). Never raises.

    ``name_match`` has **no default policy** (``None`` → return ``None``, never auto-pick): a generic
    kit must not bake one workstation's sanctioned-card name into every consumer. State the allowlist
    explicitly at the call site (e.g. ``name_match="A6000"`` on this box's A6000-only policy).
    """
    if name_match is None or shutil.which("nvidia-smi") is None:
        return None
    gpus = _smi(["--query-gpu=index,name,memory.used,uuid", "--format=csv,noheader,nounits"])
    if not gpus:
        return None
    # UUIDs with a live compute process → busy (map is independent of the per-GPU query order).
    apps = _smi(["--query-compute-apps=gpu_uuid", "--format=csv,noheader"]) or ""
    busy = {u.strip() for u in apps.splitlines() if u.strip()}
    for line in gpus.splitlines():
        parts = [p.strip() for p in line.split(",")]
        if len(parts) < 4:
            continue
        index, name, mem_used, uuid = parts[0], parts[1], parts[2], parts[3]
        if name_match not in name:  # allowlisted names only — others are off-limits even idle
            continue
        try:
            used = float(mem_used)
        except ValueError:
            continue
        if uuid in busy or used > free_mem_ceil_mib:  # someone's job → hands off
            continue
        return {"uuid": uuid, "index": index, "label": f"{name_match} #{index}"}
    return None


def _short_name(name: str) -> str:
    """Drop vendor noise for a compact UI label; falls back to the raw name if stripping leaves
    nothing (e.g. "NVIDIA GeForce RTX 4090" → "RTX 4090")."""
    n = name.replace("NVIDIA", "").replace("GeForce", "").strip()
    return n or name


def _proc_info(pids: list[str]) -> dict[str, tuple[str, str]]:
    """Map each PID → ``(owner_user, cmdline)`` via a single ``ps`` call. ``nvidia-smi`` reports
    the PID + its VRAM but not *who* owns it (and often not the command for another user's
    process) — ``ps`` sees every user's processes, so this is how a co-tenant's job gets a name.
    Best-effort: any hiccup → ``{}``."""
    if not pids:
        return {}
    try:
        # `user:20` widens the owner column past ps's 8-char default (else long names truncate to
        # "someuse+"), so the full name matches the server's whoami; split(None) collapses padding.
        out = subprocess.run(
            ["ps", "-o", "pid=,user:20=,args=", "-p", ",".join(pids)],
            capture_output=True,
            text=True,
            timeout=8,
        )
    except Exception:
        return {}
    info: dict[str, tuple[str, str]] = {}
    if out.returncode == 0:
        for line in out.stdout.splitlines():
            parts = line.split(None, 2)  # pid, user, <rest = full argv>
            if len(parts) >= 2:
                info[parts[0]] = (parts[1], parts[2] if len(parts) > 2 else "")
    return info


def list_gpus(*, eligible_name_match: str | None = None) -> list[dict]:
    """Every GPU on the box with its live occupancy — for a "who's on what" panel (and the force
    picker). Per card: ``index``, short ``name`` (+ ``full_name``), ``uuid``, ``mem_used`` /
    ``mem_total`` (MiB), ``is_eligible`` (may the auto-picker take it?), and ``procs`` — each
    compute process as ``{pid, user, cmd, mem}`` with the **owner username** resolved via ``ps``
    (so a co-tenant's job is named, not just numbered). Empty list on a GPU-less box or any
    ``nvidia-smi`` hiccup. Never raises.

    This is *reporting only* — it applies no busy filtering; the etiquette lives in
    :func:`pick_free_gpu`, and forcing a specific card is a deliberate human choice this panel
    informs."""
    if shutil.which("nvidia-smi") is None:
        return []
    gpus_raw = _smi(
        ["--query-gpu=index,name,memory.used,memory.total,uuid", "--format=csv,noheader,nounits"]
    )
    if not gpus_raw:
        return []
    # Compute processes, grouped by the GPU UUID they run on (order-independent of the per-card
    # query).
    apps_raw = (
        _smi(["--query-compute-apps=gpu_uuid,pid,used_memory", "--format=csv,noheader,nounits"])
        or ""
    )
    procs_by_uuid: dict[str, list[dict]] = {}
    pids: list[str] = []
    for line in apps_raw.splitlines():
        parts = [p.strip() for p in line.split(",")]
        if len(parts) < 3 or not parts[1]:
            continue
        uuid, pid, mem = parts[0], parts[1], parts[2]
        try:
            memi: int | None = int(float(mem))
        except ValueError:
            memi = (
                None  # nvidia-smi reports "N/A" (MIG / permission) — show the proc, drop the number
            )
        procs_by_uuid.setdefault(uuid, []).append({"pid": pid, "mem": memi})
        pids.append(pid)
    owners = _proc_info(pids)  # one ps call maps every PID → (user, cmd)
    gpus: list[dict] = []
    for line in gpus_raw.splitlines():
        parts = [p.strip() for p in line.split(",")]
        if len(parts) < 5:
            continue
        index, name, mem_used, mem_total, uuid = parts[:5]
        try:
            used: int | None = int(float(mem_used))
        except ValueError:
            used = None
        try:
            total: int | None = int(float(mem_total))
        except ValueError:
            total = None
        procs = [
            {
                "pid": p["pid"],
                "user": owners.get(p["pid"], ("?", ""))[0],
                "cmd": owners.get(p["pid"], ("?", ""))[1],
                "mem": p["mem"],
            }
            for p in procs_by_uuid.get(uuid, [])
        ]
        gpus.append(
            {
                "index": index,
                "name": _short_name(name),
                "full_name": name,
                "uuid": uuid,
                "mem_used": used,
                "mem_total": total,
                # No policy stated (``eligible_name_match=None``) → nothing is auto-eligible.
                "is_eligible": bool(eligible_name_match) and eligible_name_match in name,
                "procs": procs,
            }
        )
    return gpus


def gpu_by_index(index: str) -> dict | None:
    """Resolve a FORCE-selected card (any GPU) by its nvidia-smi index → a ``{'uuid', 'index',
    'label'}`` device dict, else ``None``. Deliberately does **no** etiquette filtering (unlike
    :func:`pick_free_gpu`): a forced pick is an explicit per-use human decision — the live GPU
    panel shows who's on each card so the user avoids stepping on a co-tenant. Pins by UUID
    (index-order-safe)."""
    if shutil.which("nvidia-smi") is None:
        return None
    gpus = _smi(["--query-gpu=index,name,uuid", "--format=csv,noheader,nounits"])
    if not gpus:
        return None
    want = str(index).strip()
    for line in gpus.splitlines():
        parts = [p.strip() for p in line.split(",")]
        if len(parts) < 3:
            continue
        idx, name, uuid = parts[0], parts[1], parts[2]
        if idx == want:
            return {"uuid": uuid, "index": idx, "label": f"{_short_name(name)} #{idx}"}
    return None
