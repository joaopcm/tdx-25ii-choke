#!/usr/bin/env python3
import hashlib
import sys

OFFICIAL_SHA256 = "65965ef444a07a7d62cee9728b8a6dd05c4b0b2b5c1f58ef8c9fcbc66ade63e7"
PATCHED_SHA256 = "4c92d905a1baead7181ea6188fcac4a374721f5beb096e274579f3ec85c6802a"

INTERNAL_CHOKE_SEND = 0xC34D
CHOKE_CALL_OPERANDS = {0xCD71: 0xE3E1, 0xCD89: 0xE3E5, 0xCDA1: 0xE3E9}
STUB_ADDRESS = 0xE3E1
STUB = bytes.fromhex(
    "7431 8006 7439 8002 743b"
    "cd fc 12cf63 7fa9 7b00 12cf63 ec fd 7fa9 7b7f 02c34d"
)


def record(address, data):
    raw = bytes([len(data), address >> 8, address & 0xFF, 0]) + data
    return ":" + (raw + bytes([-sum(raw) & 0xFF])).hex().upper()


def patch(lines):
    patched = []
    for line in lines:
        count, address, kind = int(line[1:3], 16), int(line[3:7], 16), int(line[7:9], 16)
        if kind != 0:
            patched.append(line)
            continue
        data = bytearray.fromhex(line[9 : 9 + 2 * count])
        for operand, target in CHOKE_CALL_OPERANDS.items():
            for offset, byte in enumerate(target.to_bytes(2, "big")):
                if address <= operand + offset < address + count:
                    data[operand + offset - address] = byte
        patched.append(record(address, bytes(data)))
        if address + count == STUB_ADDRESS:
            patched.append(record(STUB_ADDRESS, STUB[:16]))
            patched.append(record(STUB_ADDRESS + 16, STUB[16:]))
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
