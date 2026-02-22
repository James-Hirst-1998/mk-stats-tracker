import dolphin_memory_engine as dme
import time

dme.hook()

candidates = [
    0x8112a460,
    0x81120a88,
    0x81129b75,
    0x8138195c,
    0x81113ebe,
    0x8112b35f,
]

print("Monitoring... Ctrl+C to stop")

last = {}

while True:
    for addr in candidates:
        try:
            val = dme.read_bytes(addr - 0x80000000, 1)[0]
            if addr not in last or last[addr] != val:
                print(hex(addr), "->", val)
                last[addr] = val
        except:
            pass
    time.sleep(0.1)