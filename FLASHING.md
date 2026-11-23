# Flashing and diagnostics procedure

This document is the full procedure for the English UI patch. It separates
three levels of certainty throughout:

- **CONFIRMED**: checked by us on the file itself, read out of Valeton's own
  code or documentation, or reproduced by two independent sources.
- **EVIDENCE-BASED**: reported by independent users or developers and
  consistent with everything else we know, but not reproduced by us.
- **HYPOTHESIS**: plausible, not verified. Treat as a question, not an answer.

The priority is to keep the pedal working and to learn something from every
attempt, success or failure.

---

## 1. File identities (CONFIRMED)

| File | Size (bytes) | SHA-256 |
|---|---|---|
| Stock `GP-150 Firmware V1.1.1.bin` (from valeton.net) | 5,001,052 | `6f1d4357086aa869c4856afa0279feb892ff72124a094d7d40a417fe641236d3` |
| Patched `GP-150 Firmware V1.1.1 - English UI.bin` | 5,000,248 | `206e120d44b6c66fe9aaa5b56893be146fd0a9fd0ee1d3a4d13054d61abc68bf` |

The stock hash has been computed three times independently and agrees each
time: twice by the author of this patch (October and November 2026, from the
zip downloaded from valeton.net) and once by the
[gp150-htfw](https://github.com/egorcipa8-debug/gp150-htfw) project
(FINDINGS §14, the same value). If your download hashes differently, it is a
different file and this patch does not apply. `make_english_firmware.py`
refuses it automatically.

The patched hash is the result of a deterministic build. Rebuilding from the
same stock file produced the same bytes a month apart.

A hash of `35d6c045...` has circulated in discussion of this project. It has
no known source; it does not belong to either file above.

Check your own copies:

```
shasum -a 256 "GP-150 Firmware V1.1.1.bin" "GP-150 Firmware V1.1.1 - English UI.bin"   # macOS / Linux
certutil -hashfile "GP-150 Firmware V1.1.1.bin" SHA256                                  # Windows
```

## 2. What the patched file changes (CONFIRMED)

Measured by unpacking both files and comparing them byte for byte.

**Header (0x00 to 0xA8): 6 bytes differ**

| Offset | Field | Stock | Patched | Why |
|---|---|---|---|---|
| 0x04-0x05 | whole-file CRC-16 | `E28A` | `817D` | re-stamped |
| 0x08-0x09 | file size | 5,001,052 | 5,000,248 | LZO stream of the new payload is 804 bytes shorter |
| 0x38-0x39 | region `b` CRC-16 | `EFA4` | `4FE7` | region `b` content changed |

Model string `GP-150`, version label `V1.1.1`, the body `V111` tag, the image
size and all other header fields are identical.

**Payload (8,031,920 bytes after LZO unpack): 448 bytes differ, all in region `b`**

| Region | Flash destination | Length | Stock CRC | Patched CRC | Bytes changed |
|---|---|---|---|---|---|
| `b` RT1064 main image | `0x00038000` | 5,229,444 | `EFA4` | `4FE7` | **448** |
| `c` | `0x00740000` | 339,968 | `5137` | `5137` | 0 |
| `d` DSP | `0x00800000` | 1,238,000 | `AE63` | `AE63` | 0 |
| `e` | `0x009C0000` | 299,008 | `A367` | `A367` | 0 |
| `f` | `0x00A80000` | 262,144 | `0FB6` | `0FB6` | 0 |
| `g` Bluetooth SoC firmware | separate chip | 647,036 | `0D22` | `0D22` | 0 |
| `h` USB-PD controller | separate chip | 16,320 | `6F93` | `6F93` | 0 |

The 448 bytes sit in two clusters:

| Body offset | Flash address | Bytes | What |
|---|---|---|---|
| `0x00B4F0..0x00B501` | `0x0434F0` | 12 | the two string literals `开启`/`关闭` become `On`/`Off` (data in the code image, not instructions) |
| `0x290BC1..0x290F42` | `0x2C8BC1` | 436 | the Chinese language record overwritten with the English record (pointer table) |

**Not in the file at all**: flash `0x000000..0x037FFF` (224 KB). The
bootloader lives there, below region `b`, and no update writes it.

Validation performed on the patched file: our own CRC-16/MODBUS code, the
independent `htfw_tool.py verify` from gp150-htfw, and a Python port of the
vendor library's `checkCrc()` (gp150-htfw `seal()`), all agree.

## 3. How a firmware update actually works

**CONFIRMED** (read out of Valeton's own update library by gp150-htfw, §20):

1. Before anything is sent, the Suite library parses the container,
   LZO-decompresses the payload in memory, recomputes every region's
   CRC-16/MODBUS and **refuses the file on the first mismatch**. It also reads
   the model string out of the file and refuses a mismatch against the
   connected unit. Units with newer boot software refuse a changed version
   label, silently.
2. The transfer is one message per region (`0x11, <region id>, <data>`), cut
   into 42-byte blocks, each wrapped as a 94-byte SysEx frame over USB-MIDI.
   For GP-150 V1.1.1 that is 191,240 frames and about 17.6 MB on the wire for
   a 5 MB file.
3. The library writes a log while it works (see §8).

**EVIDENCE-BASED**:

- The main progress bar is regions `b` to `f` going to the RT1064's flash. The
  second bar, captioned **"BT And PD Updating"**, is regions `g` and `h` going
  to the Bluetooth SoC and the USB-PD controller, which are separate chips
  (gp150-htfw §16, by watching the updater). Several sources note the second
  phase is normal and can look stuck for a while.
- During an update the pedal shows a "Firmware Update / Restore" screen and
  re-enumerates as a **different USB device** (a bootloader instance with a
  different product ID). Reported for the GP-200 family in
  [microsoft/MIDI #944](https://github.com/microsoft/MIDI/issues/944) and the
  [hotone-family-firmware-fix](https://cesardamien.github.io/hotone-family-firmware-fix/)
  page; the GP-150 shares the vendor ID and update method. Not yet confirmed
  on a GP-150 by us.

**Consequences for reading a failure**:

- A file that fails the CRC, model or version checks is refused **before the
  bar moves**. A stall partway through the main bar is therefore not one of
  those three checks failing.
- Whether the pedal acknowledges each block, what (if anything) it verifies
  on its own side, and what it does on a timeout are **not known**
  (HYPOTHESIS territory). This is exactly why a mid-transfer stall cannot be
  attributed to the USB link by default. It could be the link, or the pedal
  stopping accepting data. §7 explains how to tell them apart.

## 4. Recovery mode: what is actually verified

| Statement | Level | Source |
|---|---|---|
| GP-200: with power off, hold footswitches 2 + 3 and the PARA knob, then power on, to enter Firmware Update mode | CONFIRMED (documented) | [Sweetwater, from Valeton's procedure](https://www.sweetwater.com/sweetcare/articles/valeton-gp-200-firmware-update/) |
| GP-150: with power off, hold **A + B + PARA**, then power on, then flash with Valeton Suite | EVIDENCE-BASED | Published by [Simonas](https://simonas.uk/valeton), an independent developer whose GP-150 firmware "has received user hardware testing" and who writes that he has "flashed over a hundred times" and that "everything's roll backable with stock" ([forum thread](https://thegearforum.com/threads/custom-firmware-for-gp-150-and-gp-180.12050/); the device those flashes were on is not named). Follows the same pattern as the GP-200. **Not found in Valeton's GP-150 documentation by us** (the manual PDF on valeton.net could not be retrieved). |
| The bootloader is in flash `0x000000..0x037FFF`, which no region of the update file writes, so a failed update of regions `b` to `h` cannot remove it | CONFIRMED | section table of the file (§2) |
| Suite's library has no software call to put the pedal in bootloader mode (`deviceStartBoot` is a stub) | CONFIRMED | gp150-htfw README |
| The Bluetooth SoC and PD controller (regions `g`, `h`) have their own recovery path if their update fails | HYPOTHESIS | nothing known either way |

**Gate 0 (do this before any flash, including stock): confirm the recovery
combination on your own unit.**

1. Back up presets first (some pedals use power-on combinations for factory
   reset; if A + B + PARA turned out to do that on your unit you would lose
   presets, not the pedal).
2. Pedal off. Hold A + B + PARA. Power on.
3. Observe: does the pedal show an update/restore screen rather than booting
   normally? On a Mac, does it appear in Audio MIDI Setup or in
   `system_profiler SPUSBDataType`?
4. Power off without flashing anything. Power on normally and check it boots.

Entering the bootloader and leaving again writes nothing to flash on the
GP-200, where users do this routinely (EVIDENCE-BASED). We have not confirmed
this on a GP-150; it is the lowest-risk step in this document, but it is not
zero.

If step 3 shows **no** special screen, stop. You have no verified way back,
and nothing modified should be flashed.

## 5. Go / no-go gates

Proceed to the next gate only when the current one passes. Any **no-go** means
stop, keep the stock firmware, and report what you saw.

| Gate | Pass condition | No-go |
|---|---|---|
| 0 Recovery | A + B + PARA puts the pedal in an update/restore screen and it returns to normal boot afterwards | no such screen |
| 1 Stock file | `shasum -a 256` of the stock `.bin` equals the value in §1 | any other hash |
| 2 Backup | presets backed up in Suite; stock zip kept in two places | not done |
| 3 Control flash | **stock** V1.1.1 flashed with the exact setup of §9: main bar reaches 100%, "BT And PD Updating" completes, pedal reboots by itself, version shows V1.1.1, audio passes, Bluetooth pairs | any stall, refusal, error, or misbehaviour afterwards |
| 4 Patched file | produced by `make_english_firmware.py` from the file that passed gate 1; script printed `OK` and the §1 hash | anything else |
| 5 Patched flash | same computer, cable, port and session as gate 3 | setup changed since gate 3 |

If the stock firmware does not flash and boot cleanly (gate 3), the patched
firmware must **not** be attempted. A link that cannot carry Valeton's own file
will not carry this one either, and a failure then would teach nothing.

## 6. What each stock-test outcome means

**A. Both bars complete, pedal reboots and works.** The link and the pedal's
update path are good. Gate 3 passed.

**B. Suite refuses the file, or nothing starts.** Not a transport failure.
Either Suite cannot see the pedal (Windows 11 driver, see §9; on a Mac check
Audio MIDI Setup and the cable), or the file failed the host-side checks of
§3 (wrong model, modified version label, bad CRC). With a stock file whose hash
matches §1, the file is not the cause. Fix detection; nothing modified is
involved yet.

**C. Main bar stops partway.** Something between Suite and the RT1064's flash
failed, and it happened with Valeton's own file. Collect the diagnostics of §7
and §8 **before** touching the pedal. Possible causes, in no assumed order:
USB link dropped (hub, cable, sleep), the pedal stopped accepting data, a flash
write failed, the Mac's app or MIDI stack stalled. A stock stall at the **same
percentage** on a second attempt points away from the link and towards the
pedal or its boot software; that is a case for Valeton support, not for a patch.

**D. "BT And PD Updating" stops.** This phase writes the Bluetooth SoC and the
PD controller, separate chips, via regions `g` and `h`. The patch does not
touch those regions (identical bytes, identical CRCs), so a failure here is
unrelated to the English UI change. This phase is known to look stuck for
several minutes; wait at least ten before concluding anything. If it has
genuinely failed, the recovery path for those chips is unknown (HYPOTHESIS).
Contact Valeton with the log.

**E. Completes, but the pedal misbehaves.** Try a factory reset per the
manual, then re-flash stock. If that does not help, Valeton support.

Only outcome A clears the way to the patched file.

## 7. Telling a USB failure from a pedal-side failure (macOS)

**Mechanism (CONFIRMED for the class of device, EVIDENCE-BASED for the
details):** on macOS, Valeton Suite talks to the pedal through CoreMIDI as a
USB-MIDI class device. There is no vendor driver on the Mac, which is why the
Windows 11 driver problem does not apply here. During the update the pedal
switches to its update screen and re-enumerates as a different USB device.

**Before the flash, record the baseline** (standard macOS tools):

```
system_profiler SPUSBDataType 2>/dev/null | grep -i -B2 -A12 "valeton\|GP-150" > ~/Desktop/gp150-usb-normal.txt
```

Note the Vendor ID and Product ID. Open Audio MIDI Setup, Window, Show MIDI
Studio, and confirm the GP-150 appears.

**During the flash, in a second Terminal window, before you press Update:**

```
log stream --style compact --predicate 'process == "Valeton Suite" OR eventMessage CONTAINS[c] "usb"' > ~/Desktop/gp150-live.log
```

Leave it running until the pedal has rebooted or the bar has been stopped for
ten minutes.

**Optional but decisive:** [MIDI Monitor](https://www.snoize.com/MIDIMonitor/)
(free) can spy on the GP-150's MIDI ports while Suite uses them. It shows
whether SysEx frames are still being sent when the bar stops.

**Reading the result**

| What you observe at the moment the bar stops | Conclusion | Level |
|---|---|---|
| Pedal disappears from the USB list / MIDI Studio; `log stream` shows a USB disconnect or re-enumeration | USB communication failure | CONFIRMED category |
| Pedal still enumerated; Suite's frames stopped (MIDI Monitor); same percentage on a repeat | the pedal stopped accepting data: a pedal-side rejection or a flash write problem. Which of the two needs the Suite log | HYPOTHESIS between the two |
| Pedal still enumerated; frames still flowing; bar frozen | Suite or macOS display/app issue; wait, do not touch the pedal | HYPOTHESIS |
| Stops at a different percentage each attempt | consistent with transport | EVIDENCE-BASED |
| Stops at the same percentage each attempt | deterministic: file or pedal, not the cable | EVIDENCE-BASED |

If the bar stalls: do **not** power-cycle the pedal immediately. Wait ten
minutes, collect §8, and only then use recovery mode (§4) to flash stock.
Power loss while the RT1064 is writing is the moment with the most unknowns.

## 8. Log collection

**Windows (CONFIRMED, from the library):** `%TEMP%\HTCache\logfile.txt`. The
library **truncates this file every time Suite starts**, so copy it before you
relaunch Suite. More than 99% of its lines are `scanInDevice` polling; the
update entries are the rest.

**macOS (location NOT verified):** the same library exists as a `.dylib`, and
it is likely to use the same `HTCache/logfile.txt` name under one of the
macOS temporary or cache folders. Immediately after a failure, **before
relaunching Suite**, run:

```
find /tmp "$TMPDIR" ~/Library/Caches ~/Library/Application\ Support ~/Library/Containers ~/Library/Logs -iname 'logfile.txt' 2>/dev/null
find /tmp "$TMPDIR" ~/Library -type d -iname 'HTCache' 2>/dev/null
log show --last 2h --predicate 'process == "Valeton Suite" OR eventMessage CONTAINS[c] "usb"' > ~/Desktop/gp150-system.log
```

Copy any `logfile.txt` found to the Desktop at once. If nothing is found,
report that too: it tells us where the Mac build does not write.

**What matters in the logs**

- Timestamps of the last update entries, against the clock time you saw the
  bar stop.
- Which region was being sent (order `b, c, d, e, f`, then `g, h`) and any
  block or progress counter.
- Any return codes. From the vendor's `checkCrc()`: `0` accepted, `-1`
  checksum mismatch, `-2` truncated file.
- `scanInDevice` results changing from "device found" to "not found" around
  the stall: that is a disconnect.
- Words like `timeout`, `retry`, `fail`, `error`, `resend`.
- From the system log: USB disconnect/connect events, product ID changes,
  Suite crash or hang reports.

The exact wording of the update entries is not yet known to us (nobody has
shared a Suite log from a GP-150 update). The first person to attach one will
let this section be made precise.

**What to include in a report** (the Issue templates ask for these): Mac model
and macOS version, Suite version, port used and whether direct, cable, pedal
firmware version shown before the attempt, the stall percentage, whether it
repeated at the same percentage, the three files above.

## 9. Setup for every flash

- Pedal on **mains power**, not battery.
- USB cable **straight into the computer**: no hub, dock, monitor port or
  adapter chain.
- A cable you know carries data (one that already works for editing presets).
- Suite in the foreground, laptop lid open and on charger, no sleep.
- Quit DAWs, Audio MIDI Setup (after checking), and browser tabs using WebMIDI.
- **Windows 11**: apply Valeton's driver fix first (Device Manager, Sound video
  and game controllers, GP-150, Update driver, Browse my computer, Let me pick,
  **USB Audio Device**), per the
  [Valeton notice](https://www.valeton.net/win11-technical-notice/). The
  pedal re-enumerates in update mode, so the fix may be needed a second time
  on the update screen (EVIDENCE-BASED, from the hotone-family-firmware-fix page).
- Do not touch the pedal, the cable or the computer until the second phase
  has finished and the pedal has rebooted by itself.

## 10. The one data point so far

One attempt with the patched file, macOS, Suite over USB, October 2026: the
main bar stopped partway. The stock control test had not been run, the
percentage and the Suite log were not recorded, and the USB connection
details were not noted, and what the pedal did afterwards was not recorded.
That attempt therefore distinguishes nothing, which is why this document exists.
