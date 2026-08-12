#!/usr/bin/env python3
"""Check the capture settings suit this machine before recording anything.

    sudo python3 -m tools.probe

Run once on a new machine, and again after changing the captured regions.
"""
from mkw.capture.probe import main

if __name__ == "__main__":
    main()
