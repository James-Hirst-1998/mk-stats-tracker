"""A minimal PowerPC disassembler, enough to read MKW's own code.

The method that solved damage types was to disassemble the game out of a
recording rather than search memory for a field. That was done by hand; this
makes it repeatable. Only the instruction forms that actually turn up in the
game's item and collision code are decoded - anything else prints as `.long`,
which is honest rather than wrong.
"""

import struct


def _s16(v):
    return v - 0x10000 if v & 0x8000 else v


def _bits(w, lo, hi):
    """PowerPC bit numbering: bit 0 is the most significant."""
    return (w >> (31 - hi)) & ((1 << (hi - lo + 1)) - 1)


D_FORM = {
    32: "lwz", 33: "lwzu", 34: "lbz", 35: "lbzu", 36: "stw", 37: "stwu",
    38: "stb", 39: "stbu", 40: "lhz", 41: "lhzu", 42: "lha", 43: "lhau",
    44: "sth", 45: "sthu", 46: "lmw", 47: "stmw",
}
F_FORM = {48: "lfs", 49: "lfsu", 50: "lfd", 51: "lfdu",
          52: "stfs", 53: "stfsu", 54: "stfd", 55: "stfdu"}
ARITH = {7: "mulli", 8: "subfic", 12: "addic", 13: "addic."}
LOGIC = {24: "ori", 25: "oris", 26: "xori", 27: "xoris",
         28: "andi.", 29: "andis."}
X_FORM = {
    0: "cmp", 32: "cmpl", 23: "lwzx", 87: "lbzx", 279: "lhzx", 343: "lhax",
    151: "stwx", 215: "stbx", 407: "sthx", 20: "lwarx",
    266: "add", 10: "addc", 138: "adde", 40: "subf", 8: "subfc",
    235: "mullw", 75: "mulhw", 11: "mulhwu", 491: "divw", 459: "divwu",
    28: "and", 444: "or", 316: "xor", 476: "nand", 124: "nor", 60: "andc",
    24: "slw", 536: "srw", 792: "sraw", 824: "srawi",
    954: "extsb", 922: "extsh", 26: "cntlzw", 104: "neg",
    339: "mfspr", 467: "mtspr", 19: "mfcr", 144: "mtcrf",
}
SPR = {1: "xer", 8: "lr", 9: "ctr"}

# bc encodings the compiler actually emits, as (BO, BI & 3) -> mnemonic
BRANCH = {(4, 0): "bge", (4, 1): "ble", (4, 2): "bne", (4, 3): "bns",
          (12, 0): "blt", (12, 1): "bgt", (12, 2): "beq", (12, 3): "bso"}


def disasm(word, addr=0):
    """One instruction as text. `addr` only affects branch targets."""
    op = _bits(word, 0, 5)
    d, a, b = _bits(word, 6, 10), _bits(word, 11, 15), _bits(word, 16, 20)
    imm = _s16(word & 0xFFFF)

    if op in D_FORM or op in F_FORM:
        name = D_FORM.get(op) or F_FORM[op]
        reg = "f%d" % d if op in F_FORM else "r%d" % d
        return "%-8s %s,%d(r%d)" % (name, reg, imm, a)
    if op == 14:
        if a == 0:
            return "%-8s r%d,%d" % ("li", d, imm)
        return "%-8s r%d,r%d,%d" % ("addi", d, a, imm)
    if op == 15:
        if a == 0:
            return "%-8s r%d,0x%x" % ("lis", d, word & 0xFFFF)
        return "%-8s r%d,r%d,0x%x" % ("addis", d, a, word & 0xFFFF)
    if op in ARITH:
        return "%-8s r%d,r%d,%d" % (ARITH[op], d, a, imm)
    if op in LOGIC:
        return "%-8s r%d,r%d,0x%x" % (LOGIC[op], a, d, word & 0xFFFF)
    if op in (10, 11):
        name = "cmplwi" if op == 10 else "cmpwi"
        return "%-8s cr%d,r%d,%d" % (name, d >> 2, a, imm)
    if op in (20, 21, 23):
        name = {20: "rlwimi", 21: "rlwinm", 23: "rlwnm"}[op]
        return "%-8s r%d,r%d,%d,%d,%d" % (name, a, d, b,
                                          _bits(word, 21, 25),
                                          _bits(word, 26, 30))
    if op == 16:
        bo, bi = d, a
        target = _s16(word & 0xFFFC) + (0 if word & 2 else addr)
        name = BRANCH.get((bo & 0x1E, bi & 3), "bc")
        if name == "bc":
            return "%-8s %d,%d,0x%08x" % ("bc", bo, bi, target & 0xFFFFFFFF)
        return "%-8s cr%d,0x%08x" % (name + ("l" if word & 1 else ""),
                                     bi >> 2, target & 0xFFFFFFFF)
    if op == 18:
        off = word & 0x03FFFFFC
        if off & 0x02000000:
            off -= 0x04000000
        target = off + (0 if word & 2 else addr)
        return "%-8s 0x%08x" % ("bl" if word & 1 else "b", target & 0xFFFFFFFF)
    if op == 19:
        xo = _bits(word, 21, 30)
        if xo == 16:
            return "blr" if d == 20 else "bclr %d,%d" % (d, a)
        if xo == 528:
            return "bctrl" if word & 1 else "bctr"
        return ".long    0x%08x" % word
    if op == 31:
        xo = _bits(word, 21, 30)
        name = X_FORM.get(xo)
        if name is None:
            return ".long    0x%08x" % word
        dot = "." if (word & 1) and name not in ("mfspr", "mtspr") else ""
        if name in ("mfspr", "mtspr"):
            spr = ((a >> 0) & 0x1F) | (b << 5)
            spr = (spr >> 5) | ((spr & 0x1F) << 5)
            reg = SPR.get(spr, "spr%d" % spr)
            return ("%-8s r%d" % ("mf" + reg, d) if name == "mfspr"
                    else "%-8s r%d" % ("mt" + reg, d))
        if name in ("cmp", "cmpl"):
            return "%-8s cr%d,r%d,r%d" % (name + "w", d >> 2, a, b)
        if name in ("extsb", "extsh", "cntlzw", "neg"):
            return "%-8s%s r%d,r%d" % (name, dot, a, d)
        if name == "srawi":
            return "%-8s r%d,r%d,%d" % (name + dot, a, d, b)
        if name.startswith(("lwz", "lbz", "lhz", "lha", "stw", "stb", "sth",
                            "lwar")):
            return "%-8s r%d,r%d,r%d" % (name, d, a, b)
        if name == "or" and d == b:
            return "%-8s r%d,r%d" % ("mr" + dot, a, d)
        if name in ("and", "or", "xor", "nand", "nor", "andc", "slw", "srw",
                    "sraw"):
            return "%-8s r%d,r%d,r%d" % (name + dot, a, d, b)
        return "%-8s r%d,r%d,r%d" % (name + dot, d, a, b)
    return ".long    0x%08x" % word


def block(read_u32, start, count):
    """[(addr, word, text)] for `count` instructions from `start`."""
    out = []
    for i in range(count):
        addr = start + i * 4
        word = read_u32(addr)
        if word is None:
            break
        out.append((addr, word, disasm(word, addr)))
    return out


def show(read_u32, start, count, mark=()):
    for addr, word, text in block(read_u32, start, count):
        print("  %s0x%08x  %08x  %s"
              % ("*" if addr in mark else " ", addr, word, text))


def from_session(session, frame=0):
    """A read_u32 for `block`/`show` backed by a recording."""
    def read(addr):
        b = session.read(frame, addr, 4)
        return None if b is None else struct.unpack(">I", b)[0]
    return read
