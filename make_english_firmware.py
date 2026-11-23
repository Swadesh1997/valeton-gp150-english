#!/usr/bin/env python3
"""
make_english_firmware.py  -  Valeton GP-150 V1.1.1: build the English-UI firmware

Usage
    python3 make_english_firmware.py "GP-150 Firmware V1.1.1.zip"
    python3 make_english_firmware.py "GP-150 Firmware V1.1.1.bin"

Takes the OFFICIAL firmware zip (or the .bin inside it) that you downloaded
from valeton.net, checks it is the exact file this patch was made for, applies
a 397-byte binary patch and writes:

    GP-150 Firmware V1.1.1 - English UI.bin

The output is verified against a known SHA-256 before it is written, so you
either get the exact tested file or nothing.

No third-party modules are needed; only Python 3.6 or newer.
No Valeton firmware is contained in this script, only the differences.
"""
import sys, os, io, bz2, struct, base64, hashlib, zipfile

STOCK_SHA256  = "6f1d4357086aa869c4856afa0279feb892ff72124a094d7d40a417fe641236d3"
STOCK_SIZE    = 5001052
OUTPUT_SHA256 = "206e120d44b6c66fe9aaa5b56893be146fd0a9fd0ee1d3a4d13054d61abc68bf"
OUTPUT_SIZE   = 5000248
OUTPUT_NAME   = "GP-150 Firmware V1.1.1 - English UI.bin"

# bsdiff (BSDIFF40) patch, stock -> English UI, 397 bytes, base64
PATCH_B64 = (
    "QlNESUZGNDCAAAAAAAAAAIQAAAAAAAAAOExMAAAAAABCWmg5MUFZJlNZYbcIVgAAXn3u/NxyMAGI"
    "FBAEgAQAAgJAAGCBACAABAAYAAQgAEhlTTRoGmjTQaMjQBoFAAAAAeosSVJRzMA24btxWy9lsnZa"
    "Se4kgh7UEiHHSIxlBQBVycmFIMjqoUeAzP3IBhGSM7I7/L+LuSKcKEgw24QrAEJaaDkxQVkmU1lN"
    "wbBVAAAAf/rQACBAAhAQoAkAIABAAIACQABEAIIgIAQABAwKIAByGVD1MgNNGI2KCKSamajGiGmn"
    "oKV66Cf6RrCii1hRQQApAigCJW9EEQUOYFFBBQ0j5a3+ZvGXuX3aUu3ZEX5UbAkggEAkB3/F3JFO"
    "FCQTcGwVQEJaaDkxQVkmU1kIkdm0AAAIf/ngAQEAcgBEBAAAgCABBQBARAAAEAAEPAAABAAEIABU"
    "UAA0ADINT0TUNDEDR6JHJlqWNSKohlKcZ4QO97hfRagzpZIFvBAqX+wJE0fi7kinChIBEjs2gA=="
)


def _offtin(b):
    """bsdiff's 8-byte sign-magnitude integer."""
    y = int.from_bytes(b[:7], "little") | ((b[7] & 0x7F) << 56)
    return -y if b[7] & 0x80 else y


def bspatch(old, patch):
    """Pure-Python applier for the BSDIFF40 format (bzip2 blocks)."""
    if patch[:8] != b"BSDIFF40":
        raise ValueError("not a BSDIFF40 patch")
    ctrl_len = _offtin(patch[8:16]); diff_len = _offtin(patch[16:24]); new_size = _offtin(patch[24:32])
    ctrl  = bz2.decompress(patch[32:32 + ctrl_len])
    diff  = bz2.decompress(patch[32 + ctrl_len:32 + ctrl_len + diff_len])
    extra = bz2.decompress(patch[32 + ctrl_len + diff_len:])
    new = bytearray(new_size); oldpos = newpos = dpos = epos = cpos = 0
    while newpos < new_size:
        x, y, z = (_offtin(ctrl[cpos + i * 8: cpos + i * 8 + 8]) for i in range(3)); cpos += 24
        for i in range(x):
            new[newpos + i] = (old[oldpos + i] + diff[dpos + i]) & 0xFF
        newpos += x; oldpos += x; dpos += x
        new[newpos:newpos + y] = extra[epos:epos + y]
        newpos += y; epos += y; oldpos += z
    return bytes(new)


def load_stock(path):
    data = open(path, "rb").read()
    if data[:2] == b"PK":                       # it is the zip from valeton.net
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            bins = [n for n in z.namelist() if n.lower().endswith(".bin")]
            if len(bins) != 1:
                sys.exit(f"ERROR: expected exactly one .bin inside the zip, found {bins}")
            print(f"Found inside zip: {bins[0]}")
            data = z.read(bins[0])
    return data


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    stock = load_stock(sys.argv[1])
    sha = hashlib.sha256(stock).hexdigest()
    print(f"Input : {len(stock)} bytes, SHA-256 {sha}")
    if stock[:4] != b"HTFW":
        sys.exit("ERROR: this is not a Valeton HTFW firmware file")
    model = stock[0x0C:0x1C].split(b"\0")[0].decode(errors="replace"); ver = tuple(stock[0x1D:0x20])
    print(f"Header: model={model} version=V{ver[0]}.{ver[1]}.{ver[2]}")
    if len(stock) != STOCK_SIZE or sha != STOCK_SHA256:
        sys.exit("ERROR: this is not the stock GP-150 V1.1.1 file this patch was made for.\n"
                 "       Download 'GP-150 Firmware V1.1.1' from valeton.net and try again.\n"
                 "       If Valeton has released a newer version, this patch does not apply to it.")
    out = bspatch(stock, base64.b64decode(PATCH_B64))
    osha = hashlib.sha256(out).hexdigest()
    print(f"Output: {len(out)} bytes, SHA-256 {osha}")
    if len(out) != OUTPUT_SIZE or osha != OUTPUT_SHA256:
        sys.exit("ERROR: patched result does not match the expected checksum. Nothing written.")
    dest = os.path.join(os.path.dirname(os.path.abspath(sys.argv[1])), OUTPUT_NAME)
    with open(dest, "wb") as f:
        f.write(out)
    print(f"\nOK  wrote: {dest}")
    print("Read README.md (recovery mode, flashing checklist) before you flash this.")


if __name__ == "__main__":
    main()
