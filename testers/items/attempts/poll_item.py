#!/usr/bin/env python3
"""
Poll one or more addresses and log the byte value as item ID. Use to verify
which address tracks your held item. Ctrl+C to stop.

  sudo python3 poll_item.py 0x81243757 0x81399943
  sudo python3 poll_item.py < item_addrs.txt
"""

import dolphin_memory_engine as dme
import sys
import time

dme.hook()
BASE = 0x80000000

ITEM_NAMES = {
    0: "Green Shell", 1: "Red Shell", 2: "Banana", 3: "Fake Item Box",
    4: "Mushroom", 5: "Triple Mushroom", 6: "Bob-omb", 7: "Spiny Shell",
    8: "Lightning", 9: "Star", 10: "Golden Mushroom", 11: "Mega Mushroom",
    12: "Blooper", 13: "POW Block", 14: "Thunder Cloud", 15: "Bullet Bill",
    16: "Triple Green", 17: "Triple Red", 18: "Triple Banana",
    19: "(unused)", 20: "empty",
}


def main():
    if sys.stdin.isatty():
        addrs = []
        for a in sys.argv[1:]:
            try:
                addrs.append(int(a, 0))
            except ValueError:
                pass
        if not addrs:
            print("Usage: poll_item.py <addr> [addr ...]   or   poll_item.py < addrs.txt")
            return
    else:
        addrs = []
        for line in sys.stdin:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            try:
                addrs.append(int(line, 0))
            except ValueError:
                pass
        if not addrs:
            print("No addresses on stdin.")
            return

    print("Polling %s every 0.3s. Change item to see which address tracks it. Ctrl+C to stop." % [hex(a) for a in addrs])
    print()
    last = {}
    while True:
        out = []
        for addr in addrs:
            try:
                b = dme.read_bytes(addr - BASE, 1)[0]
                name = ITEM_NAMES.get(b, "?%d" % b)
                key = addr
                if last.get(key) != b:
                    out.append("%s -> %d (%s)" % (hex(addr), b, name))
                    last[key] = b
            except Exception:
                out.append("%s -> (read failed)" % hex(addr))
        if out:
            print("%s  %s" % (time.strftime("%H:%M:%S"), "  |  ".join(out)))
        time.sleep(0.3)


if __name__ == "__main__":
    main()
