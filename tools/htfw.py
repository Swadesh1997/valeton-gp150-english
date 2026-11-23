#!/usr/bin/env python3
"""Minimal HTFW (Valeton GP-150) container helpers: parse, unpack, repack, CRC."""
import struct, ctypes, hashlib

# ---------- CRC-16/MODBUS (poly 0x8005, init 0xFFFF, refin/refout, xorout 0) ----------
_T = []
for i in range(256):
    c = i
    for _ in range(8):
        c = (c >> 1) ^ 0xA001 if c & 1 else c >> 1
    _T.append(c)

def crc16_modbus(b):
    c = 0xFFFF
    for x in b:
        c = (c >> 8) ^ _T[(c ^ x) & 0xFF]
    return c

# ---------- LZO1X via system liblzo2 (reference implementation) ----------
_lzo = ctypes.CDLL("liblzo2.so.2")
_lzo.__lzo_init_v2.restype = ctypes.c_int
_lzo.__lzo_init_v2.argtypes = [ctypes.c_uint] + [ctypes.c_int] * 9
LZO_VERSION = 0x20a0
r = _lzo.__lzo_init_v2(LZO_VERSION, 2, 4, 8, 4, 8, -1, 8, 8, -1)
assert r == 0, "lzo_init failed"

def lzo1x_1_compress(data):
    out = ctypes.create_string_buffer(len(data) + len(data) // 16 + 64 + 3)
    out_len = ctypes.c_size_t(0)
    wrk = ctypes.create_string_buffer(16384 * 8)
    r = _lzo.lzo1x_1_compress(data, ctypes.c_size_t(len(data)), out, ctypes.byref(out_len), wrk)
    assert r == 0, f"lzo1x_1_compress failed {r}"
    return out.raw[:out_len.value]

def lzo1x_decompress_safe(data, out_size):
    out = ctypes.create_string_buffer(out_size)
    out_len = ctypes.c_size_t(out_size)
    r = _lzo.lzo1x_decompress_safe(data, ctypes.c_size_t(len(data)), out, ctypes.byref(out_len), None)
    assert r == 0, f"lzo1x_decompress_safe failed {r}"
    return out.raw[:out_len.value]

# ---------- container ----------
class Section:
    def __init__(self, rec_off, rec):
        self.rec_off = rec_off
        self.crc = (rec[0] << 8) | rec[1]
        self.tag = chr(rec[3])
        self.flash, self.off, self.len = struct.unpack_from('<III', rec, 4)
    def __repr__(self):
        return f"<{self.tag} crc=0x{self.crc:04X} flash=0x{self.flash:08X} off=0x{self.off:08X} len=0x{self.len:08X}>"

class HTFW:
    def __init__(self, blob):
        assert blob[:4] == b'HTFW'
        self.blob = bytes(blob)
        self.file_crc = (blob[4] << 8) | blob[5]
        self.size = struct.unpack_from('<I', blob, 8)[0]
        self.model = blob[0x0C:0x1C].split(b'\0')[0].decode()
        self.ver = tuple(blob[0x1D:0x20])
        self.image_size = struct.unpack_from('<I', blob, 0x24)[0]
        self.sections = []
        off = 0x38
        while True:
            rec = blob[off:off + 16]
            if len(rec) < 16 or not (0x61 <= rec[3] <= 0x7A) or rec[:4] == b'\xff' * 4:
                break
            self.sections.append(Section(off, rec)); off += 16
        self.table_end = off
        self.packed = (len(blob) - self.image_size) < self.table_end
        if self.packed:
            self.raw_len = struct.unpack_from('<I', blob, self.table_end)[0]
            self.stream_off = self.table_end + 4
            self.body = lzo1x_decompress_safe(blob[self.stream_off:], self.raw_len)
        else:
            self.stream_off = len(blob) - self.image_size
            self.body = blob[self.stream_off:]

    def verify(self):
        ok = True
        for s in self.sections:
            c = crc16_modbus(self.body[s.off:s.off + s.len])
            print(f"  region {s.tag}: stored 0x{s.crc:04X} computed 0x{c:04X} {'OK' if c == s.crc else 'MISMATCH'}")
            ok &= (c == s.crc)
        fc = crc16_modbus(self.blob[6:])
        print(f"  whole file: stored 0x{self.file_crc:04X} computed 0x{fc:04X} {'OK' if fc == self.file_crc else 'MISMATCH'}")
        return ok and fc == self.file_crc

    def rebuild(self, new_body):
        """Return a new sealed image containing new_body (same length as the original body)."""
        assert len(new_body) == len(self.body), "body length must not change"
        hdr = bytearray(self.blob[:self.table_end])
        for s in self.sections:
            c = crc16_modbus(new_body[s.off:s.off + s.len])
            hdr[s.rec_off] = c >> 8; hdr[s.rec_off + 1] = c & 0xFF
        if self.packed:
            stream = lzo1x_1_compress(new_body)
            out = bytearray(hdr + struct.pack('<I', len(new_body)) + stream)
        else:
            out = bytearray(hdr + self.blob[self.table_end:self.stream_off] + new_body)
        struct.pack_into('<I', out, 8, len(out))
        fc = crc16_modbus(out[6:])
        out[4] = fc >> 8; out[5] = fc & 0xFF
        return bytes(out)

if __name__ == '__main__':
    import sys
    fw = HTFW(open(sys.argv[1], 'rb').read())
    print(f"model={fw.model} ver=V{fw.ver[0]}.{fw.ver[1]}.{fw.ver[2]} size={fw.size} packed={fw.packed} body={len(fw.body)}")
    for s in fw.sections: print(" ", s)
    print("CRC check:"); print("  all OK" if fw.verify() else "  PROBLEM")
    if len(sys.argv) > 2:
        open(sys.argv[2], 'wb').write(fw.body); print("body written to", sys.argv[2])
    rebuilt = fw.rebuild(fw.body)
    print("round trip identical:", hashlib.sha256(rebuilt).hexdigest() == hashlib.sha256(fw.blob).hexdigest(),
          f"(orig {len(fw.blob)} bytes, rebuilt {len(rebuilt)} bytes)")
    rt_body = HTFW(rebuilt).body
    print("rebuilt decompresses to same body:", rt_body == fw.body)
