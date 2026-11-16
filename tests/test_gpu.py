"""The cards of a shared box: read from nvidia-smi and ps, and the rule for joining one."""

from demokit import gpu

GPUS = """0, NVIDIA RTX PRO 6000, 620, 97887, GPU-a, 3
1, NVIDIA RTX PRO 6000, 45954, 97887, GPU-b, 69
2, NVIDIA RTX PRO 6000, 3000, 97887, GPU-c, 0
3, NVIDIA RTX PRO 6000, 0, 97887, GPU-d, [N/A]
"""
APPS = """GPU-a, 11
GPU-b, 21
GPU-b, 22
"""
OWNERS = {"11": "me", "21": "someone", "22": "me"}


def test_each_card_names_its_users_and_its_use():
    a, b, _, d = gpu.parse(GPUS, APPS, OWNERS, "me")
    assert (a["index"], a["name"], a["used"], a["total"], a["util"]) == (
        0,
        "RTX PRO 6000",
        620,
        97887,
        3,
    )
    assert (a["users"], b["users"]) == (["me"], ["me", "someone"])
    assert d["util"] is None  # unreported under MIG or without permission


def test_a_run_never_joins_a_card_another_user_is_on():
    a, b, c, d = gpu.parse(GPUS, APPS, OWNERS, "me")
    assert a["free"] and a["mine"]  # only our own process: ours to use
    assert not b["free"]  # someone's job is there, ours beside it or not
    assert not c["free"]  # no process listed, yet 3 GB resident: someone is there
    assert d["free"] and not d["mine"]


def test_without_nvidia_smi_there_are_no_cards(monkeypatch):
    monkeypatch.setattr(gpu.shutil, "which", lambda _: None)
    assert gpu.cards() == []
