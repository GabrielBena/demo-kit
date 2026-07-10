"""GPU picker etiquette — allowlisted names only (never another card, even idle), never a card
with a running job (mine OR a co-tenant's), graceful empty results on any nvidia-smi hiccup.

Ported from the reference consumer's suite; the canned nvidia-smi/ps strings run fully offline."""

from __future__ import annotations

import demokit.gpu as gpu

# nvidia-smi --query-gpu=index,name,memory.used,uuid
# (a busy 4090, a busy A6000, a FREE A6000, an idle 4090)
_GPUS = (
    "0, NVIDIA GeForce RTX 4090, 12000, GPU-4090a\n"
    "1, NVIDIA RTX A6000, 4000, GPU-a6000busy\n"
    "2, NVIDIA RTX A6000, 12, GPU-a6000free\n"
    "3, NVIDIA GeForce RTX 4090, 20, GPU-4090idle"
)


def _canned(gpus=_GPUS, apps="GPU-4090a\nGPU-a6000busy"):
    def fake_smi(args):
        return gpus if "index,name" in " ".join(args) else apps

    return fake_smi


def test_picks_the_free_allowlisted_card_not_the_idle_other(monkeypatch):
    monkeypatch.setattr(gpu.shutil, "which", lambda _: "/usr/bin/nvidia-smi")
    monkeypatch.setattr(gpu, "_smi", _canned())
    r = gpu.pick_free_gpu(name_match="A6000")
    # the free A6000 — NOT the idle 4090 (allowlist beats idleness)
    assert r == {"uuid": "GPU-a6000free", "index": "2", "label": "A6000 #2"}


def test_allowlist_is_a_parameter(monkeypatch):
    monkeypatch.setattr(gpu.shutil, "which", lambda _: "/usr/bin/nvidia-smi")
    monkeypatch.setattr(gpu, "_smi", _canned())
    # A different policy (allowlist the 4090s) picks the idle 4090 — etiquette is caller-owned.
    r = gpu.pick_free_gpu(name_match="4090")
    assert r == {"uuid": "GPU-4090idle", "index": "3", "label": "4090 #3"}


def test_none_when_all_allowlisted_busy(monkeypatch):
    monkeypatch.setattr(gpu.shutil, "which", lambda _: "/usr/bin/nvidia-smi")
    # both A6000s have a live compute proc → hands off → None (even though a 4090 is idle)
    monkeypatch.setattr(gpu, "_smi", _canned(apps="GPU-a6000busy\nGPU-a6000free"))
    assert gpu.pick_free_gpu(name_match="A6000") is None


def test_none_when_card_has_residual_memory(monkeypatch):
    # no compute proc listed, but > ceiling resident → treat as busy (conservative on a shared box)
    gpus = "2, NVIDIA RTX A6000, 8000, GPU-a6000resid"
    monkeypatch.setattr(gpu.shutil, "which", lambda _: "/usr/bin/nvidia-smi")
    monkeypatch.setattr(gpu, "_smi", _canned(gpus=gpus, apps=""))
    assert gpu.pick_free_gpu(name_match="A6000") is None


def test_graceful_none_without_nvidia_smi(monkeypatch):
    monkeypatch.setattr(gpu.shutil, "which", lambda _: None)  # GPU-less box
    assert gpu.pick_free_gpu() is None


# --- list_gpus / gpu_by_index (the "who's on what" panel + force picker) -------------------------

# 5-col (index,name,mem_used,mem_total,uuid) for list_gpus; 3-col (index,name,uuid) for
# gpu_by_index.
_GPUS5 = (
    "0, NVIDIA GeForce RTX 4090, 12000, 24564, GPU-4090a\n"
    "1, NVIDIA RTX A6000, 4000, 49140, GPU-a6000mine\n"
    "2, NVIDIA RTX A6000, 12, 49140, GPU-a6000free\n"
    "3, NVIDIA GeForce RTX 4090, 20, 24564, GPU-4090idle"
)
_GPUS3 = (
    "0, NVIDIA GeForce RTX 4090, GPU-4090a\n"
    "1, NVIDIA RTX A6000, GPU-a6000mine\n"
    "2, NVIDIA RTX A6000, GPU-a6000free\n"
    "3, NVIDIA GeForce RTX 4090, GPU-4090idle"
)
_APPS3 = "GPU-4090a, 111, 12000\nGPU-a6000mine, 222, 4000"  # a co-tenant + me


def _canned_full(monkeypatch, owners=None):
    """Wire the two nvidia-smi shapes + the ps owner lookup so list_gpus/gpu_by_index run offline."""
    monkeypatch.setattr(gpu.shutil, "which", lambda _: "/usr/bin/nvidia-smi")

    def fake_smi(args):
        s = " ".join(args)
        if "gpu_uuid" in s:
            return _APPS3
        return _GPUS5 if "memory.total" in s else _GPUS3

    monkeypatch.setattr(gpu, "_smi", fake_smi)
    monkeypatch.setattr(
        gpu,
        "_proc_info",
        lambda pids: (
            owners or {"111": ("alice", "python run_train.py"), "222": ("bob", "python -m expe")}
        ),
    )


def test_list_gpus_maps_processes_to_owners(monkeypatch):
    _canned_full(monkeypatch)
    gs = gpu.list_gpus(eligible_name_match="A6000")
    assert [g["index"] for g in gs] == ["0", "1", "2", "3"]
    # only the allowlisted cards are auto-eligible
    assert [g["is_eligible"] for g in gs] == [False, True, True, False]
    assert gs[0]["mem_used"] == 12000 and gs[0]["mem_total"] == 24564  # parsed as ints
    # The busy 4090 names its co-tenant owner (via ps, not nvidia-smi).
    assert gs[0]["procs"] == [
        {"pid": "111", "user": "alice", "cmd": "python run_train.py", "mem": 12000}
    ]
    assert gs[1]["procs"][0]["user"] == "bob"
    assert gs[2]["procs"] == [] and gs[3]["procs"] == []  # idle cards


def test_list_gpus_empty_without_nvidia_smi(monkeypatch):
    monkeypatch.setattr(gpu.shutil, "which", lambda _: None)
    assert gpu.list_gpus() == []


def test_gpu_by_index_forces_any_card_no_etiquette_filter(monkeypatch):
    _canned_full(monkeypatch)
    # Forcing #0 returns the 4090 UNFILTERED — the deliberate per-use override
    # (pick_free_gpu with the A6000 allowlist would refuse it).
    assert gpu.gpu_by_index("0") == {"uuid": "GPU-4090a", "index": "0", "label": "RTX 4090 #0"}
    assert gpu.gpu_by_index("2") == {
        "uuid": "GPU-a6000free",
        "index": "2",
        "label": "RTX A6000 #2",
    }


def test_gpu_by_index_none_for_missing(monkeypatch):
    _canned_full(monkeypatch)
    assert gpu.gpu_by_index("9") is None  # no such card


def test_proc_info_parses_widened_columns(monkeypatch):
    # `user:20=` avoids ps's 8-char truncation; split(None, 2) collapses the padding.
    class _CP:
        returncode = 0
        stdout = (
            "111 alexandrina          python run_sweep.py sweep.yaml\n"
            "222 bob                  python -u -m expe\n"
        )

    monkeypatch.setattr(gpu.subprocess, "run", lambda *a, **k: _CP())
    info = gpu._proc_info(["111", "222"])
    assert info["111"] == ("alexandrina", "python run_sweep.py sweep.yaml")  # NOT "alexandr+"
    assert info["222"] == ("bob", "python -u -m expe")


def test_proc_info_empty_pids_no_subprocess(monkeypatch):
    # No PIDs → no ps call at all (guard against an empty `-p` arg listing every process).
    def _boom(*a, **k):
        raise AssertionError("ps should not run for an empty pid list")

    monkeypatch.setattr(gpu.subprocess, "run", _boom)
    assert gpu._proc_info([]) == {}
