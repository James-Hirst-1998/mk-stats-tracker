import dolphin_memory_engine as dme

dme.hook()

START = 0x80000000
END   = 0x81800000   # MEM1
STEP  = 0x4000       # larger chunk for speed

def full_scan(value):
    matches = set()
    addr = START
    while addr < END:
        try:
            chunk = dme.read_bytes(addr - 0x80000000, STEP)
            for i, b in enumerate(chunk):
                if b == value:
                    matches.add(addr + i)
        except:
            pass
        addr += STEP
    return matches

print("Enter current position:")
current = int(input("> "))

candidates = full_scan(current)
print("Initial candidates:", len(candidates))

while True:
    print("\nMove to new position, then enter it.")
    new_val = int(input("> "))

    new_candidates = set()

    for addr in candidates:
        try:
            val = dme.read_bytes(addr - 0x80000000, 1)[0]
            if val == new_val:
                new_candidates.add(addr)
        except:
            pass

    candidates = new_candidates
    print("Remaining candidates:", len(candidates))

    if len(candidates) <= 7:
        print("Likely addresses:")
        for c in candidates:
            print(hex(c))
        break