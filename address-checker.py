import dolphin_memory_engine as dme
import time

dme.hook()

addr = 0x8138195c

while True:
    val = dme.read_bytes(addr - 0x80000000, 1)[0]
    print(val)
    time.sleep(0.2)