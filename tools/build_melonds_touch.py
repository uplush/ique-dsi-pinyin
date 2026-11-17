#!/usr/bin/env python3
"""Reproduce the verified Windows 1.1 x64 touch-reset delta from an original exe.

Equivalent source change: emulator/touch-reset.patch (GPL-3.0-or-later).
All addresses and field offsets below are specific to the SHA-256 pinned build.
The original is read-only. Output must be a new file.
"""
from pathlib import Path
import argparse
import hashlib
import struct

BEFORE = '04738277ba1d7ea0b7408608755d746193a68a9bfa628e2759140a9f2d5ab109'
AFTER = 'b4dc25f7a43ce9a7a132095012bc775494e215e7b2226eb5f01f7d0903d7eea6'


def require(ok, message):
    if not ok:
        raise ValueError(message)


def build(data):
    require(hashlib.sha256(data).hexdigest() == BEFORE, 'Original executable version mismatch')
    u16 = lambda at: struct.unpack_from('<H', data, at)[0]
    u32 = lambda at: struct.unpack_from('<I', data, at)[0]
    pe = u32(0x3c)
    opt = pe + 24
    base = struct.unpack_from('<Q', data, opt + 24)[0]
    sections = opt + u16(pe + 20)
    size, va, raw_size, raw_offset = struct.unpack_from('<4I', data, sections + 8)
    require(data[sections:sections + 8].rstrip(b'\0') == b'.text', 'Unexpected PE layout')
    hook = 0x140021672
    at = raw_offset + hook - base - va
    cave = base + va + size
    cave_offset = raw_offset + size
    original = bytes.fromhex('488d8bc8ae9e05')
    require(data[at:at + 7] == original, 'Unexpected SoftReset instruction')

    # Native DSi_TSC::Reset field writes, inline in a leaf helper. No stack use.
    # Preserve the original RCX setup for I2S.Reset after resetting the TSC.
    stub = bytearray.fromhex(
        '488b8ba0a95b05 c6411000 c7411800000000 c7411400000000 66c741200000 0f57c0')
    for offset in range(0x22, 0xa2, 16):
        stub += (bytes.fromhex('0f1141') + bytes([offset]) if offset < 128
                 else bytes.fromhex('0f1181') + struct.pack('<I', offset))
    stub += bytes.fromhex(
        'c7412418872204 c6412820 c6412b40 c74130ada08881 c681a200000001 488d8bc8ae9e05 c3')
    require(len(stub) <= raw_size - size, 'Insufficient executable padding')
    require(data[cave_offset:cave_offset + len(stub)] == bytes(len(stub)), 'Padding is not empty')
    result = bytearray(data)
    result[at:at + 7] = b'\xe8' + struct.pack('<i', cave - hook - 5) + b'\x90\x90'
    result[cave_offset:cave_offset + len(stub)] = stub
    struct.pack_into('<I', result, sections + 8, size + len(stub))

    # Extend VirtualSize within existing .text raw padding; update the PE checksum.
    struct.pack_into('<I', result, opt + 64, 0)
    checksum = 0
    for pos in range(0, len(result), 2):
        checksum += int.from_bytes(result[pos:pos + 2], 'little')
        checksum = (checksum & 65535) + (checksum >> 16)
    checksum = (checksum & 65535) + (checksum >> 16)
    struct.pack_into('<I', result, opt + 64, (checksum & 65535) + len(result))
    require(hashlib.sha256(result).hexdigest() == AFTER, 'Reproduction checksum mismatch')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('original', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    require(args.original.resolve() != args.output.resolve(), 'Use a new output file')
    result = build(args.original.read_bytes())
    with args.output.open('xb') as f:
        f.write(result)
    require(hashlib.sha256(args.output.read_bytes()).hexdigest() == AFTER, 'Written file mismatch')
    print('BUILD: touch-reset executable exactly reproduced; original unchanged; PASS')


if __name__ == '__main__':
    main()
