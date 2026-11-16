# tdx-25ii-choke

the Aroma TDX-25 II chokes its cymbals when you grab the edge, but only on the internal sound. over USB MIDI nothing comes out, so a plugin keeps ringing. the hi-hat pedal has the same problem: the module reads its position but only sends open or closed. this repo has a firmware patch that sends both over USB, and a macOS converter that turns them into notes ML Drums understands.

## what was broken

with a MIDI monitor on `DDRUM`, hitting crash 1 and grabbing the edge only shows the hit:

```
 43.247 99 31 7F
 43.320 99 31 00
```

the module runs on a Megawin 8051. the firmware (ver 7.3) is a plain Intel hex, not encrypted, and its checksum is a 16-bit sum of the data bytes. the choke routine already builds a poly aftertouch `A9 <note> 7F`, but it only sends it to the sound chip, never to the USB MIDI queue.

## the choke patch

37 bytes on top of `TDX-25II_Ver7.3_260509_DFU_0xC609_ICP_0x3F55.hex`. the three choke calls at `0xCD70` (crash 1), `0xCD88` (crash 2) and `0xCDA0` (ride) now call a 31-byte stub at `0xE3E1`, in flash that was empty. the stub sends `A9 <note> 7F` and `A9 <note> 00` to USB, then runs the original sound chip choke:

```
E3E1  74 31     mov   a,#31h     ; crash 1 entry
E3E3  80 06     sjmp  E3EB
E3E5  74 39     mov   a,#39h     ; crash 2 entry
E3E7  80 02     sjmp  E3EB
E3E9  74 3B     mov   a,#3Bh     ; ride entry
E3EB  CD        xch   a,r5       ; r5 = USB note, a = sound chip note
E3EC  FC        mov   r4,a
E3ED  12 CF 63  lcall CF63       ; USB: A9 note 7F
E3F0  7F A9     mov   r7,#A9h
E3F2  7B 00     mov   r3,#00h
E3F4  12 CF 63  lcall CF63       ; USB: A9 note 00
E3F7  EC        mov   a,r4
E3F8  FD        mov   r5,a
E3F9  7F A9     mov   r7,#A9h
E3FB  7B 7F     mov   r3,#7Fh
E3FD  02 C3 4D  ljmp  C34D       ; original sound chip send
```

the `00` right after the `7F` is the release. some Medeli-based kits leave the cymbal muted for the rest of the session when it never comes ([toontrack forum](https://www.toontrack.com/forums/topic/when-i-mute-choke-the-crash-it-stays-muted-for-the-rest-of-the-session-sd3-millenium/page/2/)).

after flashing, 9 grabs across the three cymbals gave 9 chokes, and plain hits gave none:

```
 27.822 99 31 7F
 29.030 A9 31 7F
 29.030 A9 31 00
```

| cymbal | hit | choke |
|---|---|---|
| crash 1 (left) | `49` | `A9 31 7F`, `A9 31 00` |
| crash 2 (right) | `57` | `A9 39 7F`, `A9 39 00` |
| ride | `59` | `A9 3B 7F`, `A9 3B 00` |

the choke notes are fixed at 49, 57 and 59. changing `Note` for a cymbal on the module doesn't move them.

## the hi-hat patch

the pedal never sent anything but note 44. the scan loop at `0x3AC4` reads the pedal position every pass, compares it to two thresholds and keeps only a flag at `0x0522`: 0 plays HH OPEN (46), 2 plays HH CLOSE (42). nothing in between.

the patch replaces the 9 bytes at `0x3ACB` that load the reading with a call to a 57-byte routine at `0xEE20`, right after the end of the original code. it runs those 9 bytes, then sends the reading over USB as CC4:

```
3ACB  12 EE 20  lcall EE20       ; was: mov dptr,#0AE8 / movx / add / mov r0 / mov a,@r0 / mov r5,a
EE20  90 0A E8  mov   dptr,#0AE8 ; the 9 original bytes
EE23  E0        movx  a,@dptr
EE24  24 5B     add   a,#5Bh
EE26  F8        mov   r0,a
EE27  E6        mov   a,@r0      ; pedal reading
EE28  FD        mov   r5,a
EE29  C3 13     rrc   a          ; reading / 2, fits in 7 bits
EE2B  F5 F0     mov   b,a
EE2D  90 0C 1D  mov   dptr,#0C1D ; last value sent
EE30  E0 C3 95 F0 24 01 B4 03 00 ; carry when last and new differ by 1 or less
EE39  40 18     jc    EE53
EE3B  E5 F0 F0  movx  @dptr,b    ; remember it
EE3E  EE C0 E0 EF C0 E0          ; save r6, r7
EE44  AB F0     mov   r3,b
EE46  7D 04     mov   r5,#04h
EE48  7F B0     mov   r7,#B0h
EE4A  12 CF 63  lcall CF63       ; USB: B9 04 value
EE4D  D0 E0 FF D0 E0 FE          ; restore r7, r6
EE53  E6 FD     mov   a,@r0 / mov r5,a
EE55  90 0A E8  mov   dptr,#0AE8
EE58  22        ret
```

it only sends when the value moves by 2 or more, so a pedal at rest sends nothing. moving the pedal slowly from open to closed:

```
 39.038 B9 04 33
 39.276 B9 04 35
 ...
 41.096 B9 04 4B
```

the reading isn't linear. held still at each height:

| pedal | CC4 |
|---|---|
| open | 50 to 52 |
| 1/4 | 60 to 62 |
| 1/2 | 66 to 68 |
| 3/4 | 76 |
| closed | 76 |

the module also still decides open or closed on its own, and it switches to 42 around half travel. so the converter remaps CC4 and picks the hi-hat note itself (see below).

### build the patched hex

Aroma's firmware isn't in this repo. get `260511_TDX-25II_Ver7.3.zip` from Aroma, unzip it, then:

```
python3 firmware/patch.py binary/TDX-25II_Ver7.3_260509_DFU_0xC609_ICP_0x3F55.hex TDX-25II_Ver7.3_chokeusb_hhcc_v2_DFU_0xF490.hex
```

it applies both patches, 102 bytes in total. it refuses any input that isn't that exact file (sha256) and checks the output against the build I flashed.

## flashing from a mac

the upgrader (`TDX-Drum_Upgrader.exe`) is Windows only. it talks to the module over plain HID, so it runs on Windows 11 ARM in UTM without drivers.

1. `brew install --cask utm crystalfetch`, then download Windows 11, Apple Silicon, English (United States) with CrystalFetch.
2. build a second ISO with the upgrader, both hex files and `flash/autounattend.xml`. that file installs Windows with no questions: no TPM, Secure Boot or Microsoft account check, local user `drum` with password `drum`, and it copies the `TDX` folder to the desktop. the product key in it is Microsoft's generic Windows Pro install key.

   ```
   mkdir -p iso/TDX
   cp binary/* TDX-25II_Ver7.3_chokeusb_hhcc_v2_DFU_0xF490.hex iso/TDX/
   cp flash/autounattend.xml iso/
   hdiutil makehybrid -iso -joliet -default-volume-name TDXSETUP -o tdx-setup.iso iso
   ```

3. new UTM VM: ARM64, 4 cores, 8 GB, 64 GB NVMe disk, no network, both ISOs attached as removable USB drives. press a key at "Press any key to boot from CD" and leave it alone. it took about 20 minutes to reach the desktop.
4. turn the module off, hold `METRO` and turn it on. it shows `UPGRADE VER` / `CONNECT TO USB` and comes up as `0E6A:030B` (normal mode is `0E6A:0050`). connect it to the VM from the UTM USB menu.
5. open `TDX-Drum_Upgrader.exe`, `Load` the hex and check `CheckSum`: `0xC609` for the original, `0xF490` for the patch. `CodeSize` is `0xEE1C` for the original and `0xEE59` for the patch. then `Upgrade`.
6. after "Upgraded successfully!" the module reboots, but USB MIDI only comes back after a normal power cycle. if Logic still sees nothing: Settings, MIDI, `Reset All MIDI Drivers`.

I flashed the original first to prove the path, then the patch. to go back, flash the original the same way.

the original hex ends at `0xEE1B` and doesn't include the bootloader, and update mode is entered with buttons at power on, so a bad patch shouldn't lock you out of reflashing. I haven't proven that on a bricked unit. the hi-hat routine lives past `0xEE1B`, and the bootloader accepted it.

## the converter

ML Drums doesn't choke on poly aftertouch, it has a choke note per cymbal. a Scripter in Logic did that translation live, but the choke never showed up in the recorded region. so `tdx-choke` does it before Logic:

```
DDRUM ──A9 31/39/3B──► tdx-choke ──note 80/81/82──► TDX Choke ──► Logic ──► ML Drums
```

it forwards everything from `DDRUM` to a virtual input called `TDX Choke` and swaps `A9 <note> 7F` for a 50 ms note at velocity 100. `A9 <note> 00` is dropped.

| choke | note |
|---|---|
| crash 1 `A9 31` | 80 (G#4) |
| crash 2 `A9 39` | 81 (A4) |
| ride `A9 3B` | 82 (A#4) |

for the hi-hat, it remaps CC4 so the measured pedal heights spread evenly over 0 to 127 (open 52 is 0, 1/4 61 is 42, 1/2 67 is 85, 76 is 127), then swaps the module's 42 and 46 for a note picked from the pedal position:

| CC4 after remap | note | ML Drums row |
|---|---|---|
| 0 to 19 | 46 (A#1) | Hihat Open |
| 20 to 49 | 70 (A#3) | Hihat Semi Open 3 |
| 50 to 79 | 69 (A3) | Hihat Semi Open 2 |
| 80 to 109 | 68 (G#3) | Hihat Semi Open 1 |
| 110 to 127 | 42 (F#1) | Hihat Closed Edge |

each note-off goes to the note its hit used, so a pedal move in between doesn't leave a note hanging. until the first CC4 arrives, like on the stock firmware, hi-hat notes pass through untouched.

it reconnects on its own when the module goes away and comes back, like after a power cycle.

```
make install
```

builds it, puts it in `~/.local/bin` and loads a launch agent that starts it at login and restarts it if it dies. logs go to `~/Library/Logs/tdx-choke.log`. `make uninstall` removes both.

in Logic, Settings, MIDI, Inputs: uncheck `DDRUM` and keep `TDX Choke`, otherwise every hit gets recorded twice.

in ML Drums, MIDI tab: set `Crash 1 EKit Choke` to G#4, `Crash 2 EKit Choke` to A4 and `Ride EKit Choke` to A#4. use the `EKit Choke` rows, not `Crash 1 Choke`. those play a choked hit sample, so every grab sounds like an extra hit. keep `MIDI HIHAT CC` off, the converter already picks the hi-hat sound.

## module settings

- ride bell: in this kit `RIDE CUP` sends 51, same as the bow. `QUICK`, `Note`, hit the bell, set 53 (Ride Bell in ML Drums).
- the ride bow fires a weak 51 about 100 ms after a hard edge hit, and 23 to 53 ms after a bell hit. `Mask` didn't fix it since it's a different zone of the same cymbal. `XTALK SETUP` is the next thing to try.
