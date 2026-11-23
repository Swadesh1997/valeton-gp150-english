# Valeton GP-150: English UI for Chinese-market units

Turn the menus of a Chinese-market Valeton GP-150 into English by making the
pedal use the English text that is **already inside** its own V1.1.1 firmware.

> **Status: experimental, not yet confirmed on hardware.**
> The firmware file has been built and verified on disk by two independent
> tools, **If you try this, please report the result**, success or
> failure, through the Issues tab. That is what this repository is for.

Not affiliated with Valeton or Hotone. Use at your own risk. See
[Risks](#risks) and [Recovery mode](#recovery-mode) before doing anything.

---

## How it works

The official `GP-150 Firmware V1.1.1` file contains **two complete language
records**: 216 UI strings plus 12 font pointers each, one Chinese and one
English. Chinese-market units are pinned to record 0 (Chinese) and the Language
menu does nothing.

This patch copies the English record over the Chinese record, so record 0 *is*
English, and translates the two `On`/`Off` labels that live outside the table.
That is all. In numbers:

| | |
|---|---|
| Payload bytes changed | 448 of 8,031,920 |
| Code changed | none |
| Strings shortened or rewritten | none (Valeton's own English text and fonts) |
| Model string and version label | untouched |
| Region CRC-16s, LZO packing, whole-file CRC | regenerated and verified |

Because the firmware is only re-pointed at text and fonts it already ships
with, you get the same interface an international GP-150 shows.

## What you need

- A Valeton GP-150 on firmware **V1.1.1** (check the system/about menu).
- The official firmware zip from valeton.net:
  **GP-150 Firmware V1.1.1 (compatible with computer software V2.1.0 and mobile software V2.1.0)**.
  This repository does not contain Valeton's firmware, only a 397-byte patch.
- Python 3.6 or newer (Windows: python.org installer; macOS and Linux: already there).
- Valeton Suite on a computer, and a USB cable that carries data.

## Step by step

### 1. Build the English firmware file

Put the official zip next to `make_english_firmware.py` and run:

```
python3 make_english_firmware.py "GP-150 Firmware V1.1.1.zip"
```

(On Windows use `python` instead of `python3`.) The script checks the zip is
the exact stock file this patch was made for, applies the patch, verifies the
result against a known checksum and writes:

```
GP-150 Firmware V1.1.1 - English UI.bin
SHA-256 206e120d44b6c66fe9aaa5b56893be146fd0a9fd0ee1d3a4d13054d61abc68bf
```

If anything does not match, it writes nothing and tells you why.

### 2. Follow the flashing procedure

**Read [FLASHING.md](FLASHING.md) in full before you flash anything.** It is
built as a set of go/no-go gates:

| Gate | What it establishes |
|---|---|
| 0 | the recovery combination works on **your** unit (checked without flashing) |
| 1 | your stock file is the exact one this patch was made for |
| 2 | presets backed up, stock zip kept |
| 3 | the **stock** file flashes and boots cleanly with your computer, cable and port |
| 4 | the patched file was produced by the script and matches the published hash |
| 5 | the patched file is flashed with the same setup, in the same session |

If the stock firmware does not flash and boot cleanly, the patched firmware
must not be attempted. FLASHING.md also explains what each kind of failure
means, how to tell a USB drop from the pedal refusing data, and which logs to
collect on macOS and Windows, with each statement marked as confirmed,
evidence-based or hypothesis.

### 3. Report back

Open an issue using the **Success report** or **Failure report** template,
whatever the outcome. The templates ask for the details that actually
distinguish causes (did stock flash on the same setup, stall percentage, same
place twice, logs).

## Recovery mode

With the pedal **off**, hold **A + B + PARA**, switch it **on**, then flash the
**stock** file from Valeton Suite.

What is known about this, precisely: the bootloader lives in flash below the
first region any update writes, so a failed update cannot remove it
(confirmed from the file's section table). The A + B + PARA combination itself
is published by an independent developer whose GP-150 firmware has been
user-tested, follows the same pattern Valeton documents for the GP-200, and has
**not** been found by us in Valeton's own GP-150 documentation. That is why
FLASHING.md asks you to confirm it on your unit, without flashing, before
anything else.

## Risks

- Any firmware change can leave a device unusable. This one changes 448 bytes
  of pointer data and two labels inside one region, and leaves the model
  string and version label alone, which are the two things the updater is
  known to check. The risk is low but not zero, and it has **not** yet been
  proven on a real unit.
- The one hardware-confirmed rebuild with the same toolchain changed a graphics
  region, not the code/data region this patch touches.
- The single attempt so far (macOS, over USB) stopped partway through the main
  progress bar. No control test and no logs were taken, so it distinguishes
  nothing. FLASHING.md is written so the next attempt does.
- In practice this voids the warranty.

## Known limits

- The Language menu will show "English" for both entries.
- Every official firmware update overwrites the change, and this patch only
  applies to V1.1.1. A new version needs a new patch (see Rebuilding below).
- This changes the pedal only. The Valeton Suite **app** on a Chinese unit may
  still show Chinese. See [flameshikari/valeton-suite-en](https://github.com/flameshikari/valeton-suite-en)
  (Android) or use the English browser editor
  [lucanenni/valeton-gp150-editor](https://github.com/lucanenni/valeton-gp150-editor).

## Technical details

The firmware is an `HTFW` container: header, section table of seven regions
(`b` to `h`) each with a CRC-16/MODBUS, then the LZO1X-packed payload with a
CRC-16 over the whole file. Region `b` is the main RT1064 image: a 0x28-byte
load table, an ITCM image (0x353E9 bytes), then the SDRAM image loaded at
`0x80000000`.

| What | Body offset | Address |
|---|---|---|
| Chinese language record (216 + 12 pointers) | `0x290BC1` | `0x8025B7B0` |
| English language record | `0x290F51` | `0x8025BB40` |
| Chinese string block | `0x28F629` .. `0x290140` | |
| English string block | `0x290145` .. `0x290A00` | |
| `开启` / `关闭` literals in ITCM code | `0x00B4F0`, `0x00B4FC` | `0x0000B4C8`, `0x0000B4D4` |

The patch: `body[0x290BC1:0x290F51] = body[0x290F51:0x2912E1]`, then the two
literals become `On` and `Off`, then region CRCs, size field and whole-file CRC
are re-stamped and the payload re-packed with LZO1X-1.

`make_english_firmware.py` does not do any of that itself. It applies a
pre-computed bsdiff of the final files, so it needs no LZO library and cannot
produce anything other than the exact verified output.

## Rebuilding from source

`tools/htfw.py` parses, unpacks, re-packs and seals the container.
`tools/build_english.py` applies the record swap and rebuilds. They need
`liblzo2` (the reference LZO library), so run them on Linux or in WSL:

```
sudo apt install liblzo2-2
python3 tools/build_english.py "GP-150 Firmware V1.1.1.bin" out.bin
```

Unpacking and re-packing the untouched stock file reproduces it byte for byte,
which is how the toolchain was proven. For a future firmware version the two
record offsets will move; `tools/find_language_records.py` locates them.

## Credits

- Container format, CRCs, LZO packing and the first hardware-confirmed rebuild:
  [egorcipa8-debug/gp150-htfw](https://github.com/egorcipa8-debug/gp150-htfw)
- The original idea of patching Chinese Valeton firmware to English:
  [kosmo-sys/valeton-english-patch](https://github.com/kosmo-sys/valeton-english-patch),
  [lshug/valeton-gp200-english-patch](https://github.com/lshug/valeton-gp200-english-patch)
- GP-150 recovery mode: [Simonas, Valeton Matrix firmware](https://simonas.uk/valeton)

## Licence

Scripts and documentation: MIT (see `LICENSE`). The 397-byte patch contains
only the differences between two files and no Valeton code. Valeton and GP-150
are trademarks of their owners.
