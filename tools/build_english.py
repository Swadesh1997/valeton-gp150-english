#!/usr/bin/env python3
"""
Build an English-UI GP-150 firmware from the stock V1.1.1 image.

Method: the stock image carries two complete language records (Chinese and
English), each 216 string pointers + 12 font pointers.  The Chinese unit is
pinned to record 0.  We copy the English record over the Chinese record, so
record 0 *is* English.  Two small "On"/"Off" literals that live in ITCM code
are translated in place.  Nothing else changes.  Section CRCs, LZO packing and
the whole-file CRC are then regenerated exactly as Valeton's own tool does.
"""
import sys, os, hashlib, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from htfw import HTFW, crc16_modbus

SRC, DST = sys.argv[1], sys.argv[2]

ITCM0, ITCM_LEN = 0x28, 0x353E9
SD0 = ITCM0 + ITCM_LEN
def addr(off): return off - ITCM0 if ITCM0 <= off < SD0 else 0x80000000 + off - SD0

CN_REC, EN_REC, REC_LEN = 0x290BC1, 0x290F51, 0x390   # body offsets
N_STR, N_FONT = 216, 12

fw = HTFW(open(SRC, 'rb').read())
assert fw.model == 'GP-150' and fw.ver == (1, 1, 1), f"expected GP-150 V1.1.1, got {fw.model} {fw.ver}"
assert fw.verify(), "stock image failed CRC verification"
body = bytearray(fw.body)

# --- sanity checks on the records before touching anything ---
cn = struct.unpack_from(f'<{N_STR+N_FONT}I', body, CN_REC)
en = struct.unpack_from(f'<{N_STR+N_FONT}I', body, EN_REC)
def cstr(o):
    e = body.index(b'\0', o); return bytes(body[o:e]).decode('utf-8')
def off_of(a): return a + ITCM0 if a < ITCM_LEN else a - 0x80000000 + SD0
assert cstr(off_of(cn[0])) == '中文' and cstr(off_of(en[0])) == 'English', "language records not where expected"
assert body[0xB4F0:0xB4F8] == '开启'.encode() + b'\0\0' and body[0xB4FC:0xB504] == '关闭'.encode() + b'\0\0'

# --- the patch ---
body[CN_REC:CN_REC + REC_LEN] = body[EN_REC:EN_REC + REC_LEN]
body[0xB4F0:0xB4F8] = b'On\0\0\0\0\0\0'
body[0xB4FC:0xB504] = b'Off\0\0\0\0\0'

# --- rebuild container (region CRCs, LZO pack, size, whole-file CRC) ---
out = fw.rebuild(bytes(body))
open(DST, 'wb').write(out)

# --- independent verification of the output ---
chk = HTFW(out)
assert chk.verify(), "output failed CRC verification"
assert chk.body == bytes(body)
diff = [i for i in range(len(fw.body)) if fw.body[i] != body[i]]
print(f"\nOutput: {DST}  ({len(out)} bytes, stock was {len(fw.blob)} bytes)")
print(f"SHA-256 stock : {hashlib.sha256(fw.blob).hexdigest()}")
print(f"SHA-256 output: {hashlib.sha256(out).hexdigest()}")
print(f"Payload bytes changed: {len(diff)}")
print(f"Record 0 entry 0 now reads: {cstr(off_of(struct.unpack_from('<I', body, CN_REC)[0]))!r}")
print(f"Header: model={chk.model} ver=V{'.'.join(map(str,chk.ver))} packed={chk.packed} regions={len(chk.sections)}")
