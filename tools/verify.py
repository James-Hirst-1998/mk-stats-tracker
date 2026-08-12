#!/usr/bin/env python3
"""Check that a recording reproduces what the live reads said at the time.

    python3 -m tools.verify [recording-substring]

Run this before treating any recording as evidence. It re-reads the anchors
that were captured live and reports how many frames agree.
"""
from mkw.capture.session import main

if __name__ == "__main__":
    main()
