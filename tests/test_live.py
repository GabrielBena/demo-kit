"""The live half: chunks on the wire, and the server's routes."""

import json
import threading
import urllib.error
import urllib.request
from array import array
from pathlib import Path

import pytest

from demokit.live import chunk, decode, make_server

FIXTURE = Path(__file__).parent / "fixtures" / "chunk.bin"  # read back by tests/web/live.test.mjs


def sample() -> bytes:
    grid = memoryview(array("B", range(6))).cast("B", [2, 3])
    who, when = array("i", [1, 2, 3]), array("f", [5.5, 7.25, 14.0])
    return chunk(
        5.0, 15.0, key=True, meta={"tag": "x"}, who=who, when=when, grid=grid, none=array("f")
    )


def test_a_chunk_reads_back_whole():
    head, arrays = decode(sample())
    assert (head["t0"], head["t1"], head["key"], head["meta"]) == (5.0, 15.0, True, {"tag": "x"})
    assert arrays["who"].tolist() == [1, 2, 3] and arrays["when"].tolist() == [5.5, 7.25, 14.0]
    assert arrays["grid"].tolist() == [[0, 1, 2], [3, 4, 5]] and arrays["none"].tolist() == []


def test_the_wire_is_the_fixture_both_sides_read():
    assert sample() == FIXTURE.read_bytes()


def test_arrays_without_a_typed_array_or_not_contiguous_are_refused():
    with pytest.raises(ValueError, match="32 bits"):
        chunk(0, 1, big=array("q", [1]))
    with pytest.raises(ValueError, match="contiguous"):
        chunk(0, 1, every_other=memoryview(array("i", range(6)))[::2])


def test_the_server_streams_a_run_and_its_inbox(tmp_path):
    (tmp_path / "index.html").write_text("<p>page</p>")

    def start(inbox):  # two chunks, each telling what the inbox held
        for k in range(2):
            got = [inbox.get() for _ in range(inbox.qsize())]
            yield chunk(k, k + 1, meta={"got": got})

    server = make_server(start, page=tmp_path)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{server.server_address[1]}"

    def call(path, body=None):
        method = "GET" if body is None else "POST"
        request = urllib.request.Request(url + path, data=body, method=method)
        try:
            with urllib.request.urlopen(request) as res:
                return res.status, res.headers.get("Content-Type"), res.read()
        except urllib.error.HTTPError as error:
            return error.code, None, b""

    try:
        assert call("/start", b"")[0] == 204
        assert call("/act", json.dumps({"pick": [3, 4]}).encode())[0] == 204
        assert decode(call("/next")[2])[0]["meta"] == {"got": [{"pick": [3, 4]}]}
        assert decode(call("/next")[2])[0]["t0"] == 1
        assert call("/next")[0] == 204  # the source ended
        assert call("/")[2] == b"<p>page</p>"
        assert call("/kit/live.js")[1] == "text/javascript"
        assert call("/../pyproject.toml")[0] == 404 and call("/kit/../live.py")[0] == 404
    finally:
        server.shutdown()
        server.server_close()
