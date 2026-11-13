"""A live demo in a few lines: dots that wander and flash, streamed as chunks.

    python -m demokit.example [--port 8170]

Each chunk covers 100 ms of world time and is a keyframe: where every dot is at its start, then
its flashes (which dot, when). A click on the page makes the nearest dot flash as the next chunk
starts: the inbox at work.
"""

import argparse
import random
from array import array
from pathlib import Path

from demokit import chunk, serve

N, SPAN, RATE = 48, 100.0, 0.004  # dots; ms of world time a chunk; flashes a ms per dot


def dots(inbox):
    rng = random.Random(0)
    x = array("f", (rng.uniform(8, 312) for _ in range(N)))
    y = array("f", (rng.uniform(16, 160) for _ in range(N)))
    t = 0.0
    while True:
        who, when = array("i"), array("f")
        while not inbox.empty():  # a click: the nearest dot flashes now
            px, py = inbox.get()["pick"]
            who.append(min(range(N), key=lambda i: (x[i] - px) ** 2 + (y[i] - py) ** 2))
            when.append(t)
        for i in range(N):
            s = t + rng.expovariate(RATE)
            while s < t + SPAN:
                who.append(i)
                when.append(s)
                s += rng.expovariate(RATE)
        yield chunk(t, t + SPAN, key=True, x=x, y=y, who=who, when=when)
        for i in range(N):  # a step of wandering, kept on the screen
            x[i] = min(max(x[i] + rng.gauss(0, 1.5), 4), 314)
            y[i] = min(max(y[i] + rng.gauss(0, 1.5), 16), 166)
        t += SPAN


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="dots that wander and flash, served live")
    parser.add_argument("--port", type=int, default=8170)
    serve(dots, page=Path(__file__).parent, port=parser.parse_args().port)
