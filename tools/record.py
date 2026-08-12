#!/usr/bin/env python3
"""Record a whole session to disk so it can be replayed offline.

    sudo python3 -m tools.record

Writes to `recordings/<timestamp>-<name>/`, or wherever MKW_RECORDINGS points.
Keep the screen recording of the same race alongside it - the video is often
the only ground truth available.
"""
from mkw.capture.recorder import main

if __name__ == "__main__":
    main()
