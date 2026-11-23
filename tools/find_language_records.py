#!/usr/bin/env python3
"""
find_language_records.py  -  locate the Chinese and English UI language records
in a GP-150 firmware, for porting the patch to a new firmware version.

    python3 tools/find_language_records.py "GP-150 Firmware Vx.y.z.bin"

Prints the body offsets of both records and how many entries they hold.
Needs tools/htfw.py (and liblzo2 for packed images).
"""
import sys, os, struct, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from htfw import HTFW

fw = HTFW(open(sys.argv[1], 'rb').read())
d = fw.body
print(f"model={fw.model} version=V{'.'.join(map(str, fw.ver))} body={len(d)} bytes")

# Region b load table: 0x14 ITCM length, 0x20 SDRAM length, 0x24 SDRAM base
ITCM0 = 0x28
ITCM_LEN = struct.unpack_from('<I', d, 0x14)[0]
SD_BASE = struct.unpack_from('<I', d, 0x24)[0]
SD0 = ITCM0 + ITCM_LEN
print(f"load table: ITCM len 0x{ITCM_LEN:X}, SDRAM image at body 0x{SD0:X} -> 0x{SD_BASE:08X}")

def addr(off): return off - ITCM0 if ITCM0 <= off < SD0 else SD_BASE + off - SD0
def off_of(a): return a + ITCM0 if a < ITCM_LEN else a - SD_BASE + SD0
def cstr(o):
    e = d.index(b'\0', o); return d[o:e].decode('utf-8', 'replace')

def find_record(first_string):
    """A language record starts with a pointer to its language-name string."""
    hits = []
    for m in re.finditer(re.escape(b'\0' + first_string.encode() + b'\0'), d):
        s = m.start() + 1
        for r in re.finditer(re.escape(struct.pack('<I', addr(s))), d):
            rec = r.start()
            # count consecutive pointers that land on NUL-terminated strings
            n = 0
            while True:
                v = struct.unpack_from('<I', d, rec + 4 * n)[0]
                try:
                    o = off_of(v)
                    if not (0 <= o < len(d)): break
                    t = cstr(o)
                    # a UI string: short, printable, valid UTF-8 (tail-merged
                    # pointers into the middle of a longer string are fine)
                    if not (0 < len(t) <= 100 and all(c.isprintable() or c == '\n' for c in t)): break
                    d[o:o + len(t.encode())].decode('utf-8')
                except Exception:
                    break
                n += 1
            if n >= 50:
                hits.append((rec, n, s))
    return hits

for name in ('中文', 'English'):
    for rec, n, s in find_record(name):
        print(f"\n{name!r} string at body 0x{s:X}; record at body 0x{rec:X} (addr 0x{addr(rec):08X}), "
              f"{n} consecutive string pointers")
        print("   first entries:", [cstr(off_of(struct.unpack_from('<I', d, rec + 4 * i)[0])) for i in range(4)])
