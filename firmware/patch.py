#!/usr/bin/env python3
import hashlib
import sys

OFFICIAL_SHA256 = "65965ef444a07a7d62cee9728b8a6dd05c4b0b2b5c1f58ef8c9fcbc66ade63e7"
PATCHED_SHA256 = "7a5e79cea7255e35a4e9c1b20fa164e01689867c46c3280df00434340c393c9c"

REPLACEMENTS = {
    0xCD71: bytes.fromhex("e3e1"),
    0xCD89: bytes.fromhex("e3e5"),
    0xCDA1: bytes.fromhex("e3e9"),
    0x3ACB: bytes.fromhex("12ee20 000000000000"),
}
CHOKE_STUB_ADDRESS = 0xE3E1
CHOKE_STUB = bytes.fromhex(
    "7431 8006 7439 8002 743b"
    "cd fc 12cf63 7fa9 7b00 12cf63 ec fd 7fa9 7b7f 02c34d"
)
HIHAT_STUB_ADDRESS = 0xEE20
HIHAT_STUB = bytes.fromhex(
    "900ae8 e0 245b f8 e6 fd"
    "c3 13 f5f0 900c1d e0 c3 95f0 2401 b40300 4018"
    "e5f0 f0 ee c0e0 ef c0e0 abf0 7d04 7fb0 12cf63 d0e0 ff d0e0 fe"
    "e6 fd 900ae8 22"
)


def record(address, data):
    raw = bytes([len(data), address >> 8, address & 0xFF, 0]) + data
    return ":" + (raw + bytes([-sum(raw) & 0xFF])).hex().upper()


def records(address, data):
    return [record(address + offset, data[offset : offset + 16]) for offset in range(0, len(data), 16)]


def patch(lines):
    patched = []
    for line in lines:
        count, address, kind = int(line[1:3], 16), int(line[3:7], 16), int(line[7:9], 16)
        if kind != 0:
            patched.extend(records(HIHAT_STUB_ADDRESS, HIHAT_STUB))
            patched.append(line)
            continue
        data = bytearray.fromhex(line[9 : 9 + 2 * count])
        for start, replacement in REPLACEMENTS.items():
            for offset, byte in enumerate(replacement):
                if address <= start + offset < address + count:
                    data[start + offset - address] = byte
        patched.append(record(address, bytes(data)))
        if address + count == CHOKE_STUB_ADDRESS:
            patched.extend(records(CHOKE_STUB_ADDRESS, CHOKE_STUB))
    return patched


def checksum(lines):
    total = 0
    for line in lines:
        if line[7:9] == "00":
            total += sum(bytes.fromhex(line[9 : 9 + 2 * int(line[1:3], 16)]))
    return total & 0xFFFF


def main():
    if len(sys.argv) != 3:
        sys.exit("usage: patch.py <official .hex> <output .hex>")
    source = open(sys.argv[1], "rb").read()
    if hashlib.sha256(source).hexdigest() != OFFICIAL_SHA256:
        sys.exit(f"{sys.argv[1]}: sha256 doesn't match TDX-25II_Ver7.3_260509_DFU_0xC609_ICP_0x3F55.hex")
    lines = patch(source.decode("ascii").splitlines())
    output = ("\r\n".join(lines) + "\r\n").encode("ascii")
    if hashlib.sha256(output).hexdigest() != PATCHED_SHA256:
        sys.exit("patched output doesn't match the tested build, nothing written")
    open(sys.argv[2], "wb").write(output)
    print(f"wrote {sys.argv[2]}, the upgrader should show CheckSum 0x{checksum(lines):04X}")


if __name__ == "__main__":
    main()
