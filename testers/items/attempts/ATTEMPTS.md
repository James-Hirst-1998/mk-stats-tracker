# Item Tracking Attempts Log

Use this as memory. Keep entries short.

## Known Failed / Unstable Approaches
- Block+offset from player block: works in one race, breaks next race due to allocation changes.
- Single/short pointer-chain from position block to held-item byte: not stable; do not retry same chain strategy.
- Scanning MEM1 for pointers to per-race item addresses: no stable pointer path found.
- "Item used" transition matching (old->new): misses held/cart states (for example triple bananas while held), so not reliable.
- Neighbour-pointer scans near `0x809c27f8`: not proven stable across races/restarts.

## Entry Format (append for each new attempt)
- `YYYY-MM-DD`: method -> result -> keep/stop.
