#!/usr/bin/env python3
"""Apply component-level patches to a copy of a user-supplied iQue DSi NAND."""
from pathlib import Path
import argparse
import hashlib
import json
import shutil
import struct
import sys
import zipfile

import bsdiff4
import numpy as np
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from tools.nand_image import NAND
from tools.nand_writer import Writer

ROOT = Path(__file__).resolve().parent
BOOT_KEY = bytes.fromhex('ad34ecf9626ec23af6b46c008080ee98')


def require(ok, message):
    if not ok:
        raise ValueError(message)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def file_hash(path):
    with Path(path).open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def manifest():
    return json.loads((ROOT / 'patches/manifest.json').read_text(encoding='utf-8'))


def boot_crypt(data):
    size = len(data)
    iv = struct.pack('<4I', size, (-size) & 0xffffffff, (~size) & 0xffffffff, 0)[::-1]
    blocks = np.frombuffer(data, dtype=np.uint8).reshape(-1, 16)[:, ::-1].tobytes()
    ctx = Cipher(algorithms.AES(BOOT_KEY), modes.CTR(iv)).encryptor()
    result = ctx.update(blocks) + ctx.finalize()
    return np.frombuffer(result, dtype=np.uint8).reshape(-1, 16)[:, ::-1].tobytes()


def transform(data, item):
    require(digest(data) == item['before_sha256'], 'Component version mismatch: ' + item['name'])
    delta = (ROOT / item['patch']).read_bytes()
    require(digest(delta) == item['patch_sha256'], 'Patch checksum mismatch: ' + item['name'])
    result = bsdiff4.patch(data, delta)
    require(len(result) == item['after_size'] and digest(result) == item['after_sha256'],
            'Patched component checksum mismatch: ' + item['name'])
    return result


def boot_data(nand, item):
    nand.f.seek(0x220)
    parameters = list(struct.unpack('<4I', nand.f.read(16)))
    require(parameters == item['parameters'], 'Unsupported boot2 header/version')
    nand.f.seek(parameters[0])
    return boot_crypt(nand.f.read(parameters[3]))


def check_nand(path, patched=False):
    n = NAND(path)
    try:
        key = 'after_sha256' if patched else 'before_sha256'
        for item in manifest()['nand']:
            data = boot_data(n, item) if item['kind'] == 'boot2' else n.file(item['path'])
            require(digest(data) == item[key], 'Component version mismatch: ' + item['name'])
    finally:
        n.close()
    print('VERIFY: patched components match; PASS' if patched else 'CHECK: supported original components; PASS')


def write_copy(source, output, sectors, validator=None):
    """Write a new image and private undo archive; never open source for writing."""
    source, output = Path(source).resolve(), Path(output).resolve()
    undo = Path(str(output) + '.undo.zip')
    require(source != output, 'Input and output must be different files')
    require(not output.exists() and not undo.exists(), 'Output or undo archive already exists')
    before_hash = file_hash(source)
    old = bytearray()
    ranges = []
    with source.open('rb') as src, output.open('xb') as dst:
        shutil.copyfileobj(src, dst, 1024 * 1024)
        for address, replacement in sorted(sectors.items()):
            src.seek(address)
            previous = src.read(len(replacement))
            require(len(previous) == len(replacement), 'Patch exceeds input image')
            if previous == replacement:
                continue
            ranges.append({'offset': address, 'length': len(previous), 'undo_offset': len(old)})
            old.extend(previous)
            dst.seek(address)
            dst.write(replacement)
    # Save recovery data before deeper validation; it stays on the user's machine.
    record = {'format': 1, 'original_sha256': before_hash, 'patched_sha256': file_hash(output),
              'undo_sha256': digest(old), 'ranges': ranges}
    with zipfile.ZipFile(undo, 'x', compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr('undo.json', json.dumps(record, indent=2))
        z.writestr('sectors.dat', old)
    require(file_hash(source) == before_hash, 'Input changed during operation')
    if validator:
        validator(output)
    print('APPLY: output verified; original unchanged; undo archive created; PASS')


def apply_nand(source, output):
    n = NAND(source)
    try:
        writer = Writer(n)
        fat = bytearray(n.fat)
        for i in range(n.nfats):
            require(n.read(n.fataddr + i * len(fat), len(fat)) == fat, 'FAT copies differ')
        used = set()
        for entry in n.entries.values():
            if entry['cluster'] >= 2:
                for cluster in n.clusters(entry['cluster']):
                    require(cluster not in used, 'Cross-linked FAT chain')
                    used.add(cluster)
        raw_sectors = {}
        changed_files = set()
        # Preflight every component before creating any output file.
        for item in manifest()['nand']:
            if item['kind'] == 'boot2':
                before = boot_data(n, item)
                after = boot_crypt(transform(before, item))
                offset = item['parameters'][0]
                for pos in range(0, len(after), 512):
                    raw_sectors[offset + pos] = after[pos:pos + 512]
            else:
                path = item['path']
                writer.put_file(path, transform(n.file(path), item), fat, used)
                changed_files.add(path)
        for i in range(n.nfats):
            writer.write_plain(n.fataddr + i * len(fat), fat)
        for address, plain in writer.sectors.items():
            require(address not in raw_sectors, 'Overlapping boot2/filesystem patch')
            raw_sectors[address] = n.crypt(address, bytes(plain))

        def verify_copy(path):
            check_nand(path, patched=True)
            m = NAND(path)
            try:
                require(n.entries.keys() == m.entries.keys(), 'Filesystem entries changed')
                for name, entry in n.entries.items():
                    if not entry['directory'] and name not in changed_files:
                        require(n.file(name) == m.file(name), 'Unexpected file change: ' + name)
                n.f.seek(-64, 2)
                m.f.seek(-64, 2)
                require(n.f.read(64) == m.f.read(64), 'NAND footer changed')
            finally:
                m.close()
        write_copy(source, output, raw_sectors, verify_copy)
    finally:
        n.close()


def apply_emulator(source, output):
    original = Path(source).read_bytes()
    modified = transform(original, manifest()['emulator'])
    require(len(original) == len(modified), 'Unexpected executable size change')
    sectors = {p: modified[p:p + 512] for p in range(0, len(modified), 512)
               if original[p:p + 512] != modified[p:p + 512]}
    write_copy(source, output, sectors,
               lambda p: require(file_hash(p) == digest(modified), 'Executable verification failed'))


def rollback(source, undo, output):
    source, undo, output = [Path(x).resolve() for x in (source, undo, output)]
    require(output not in (source, undo) and not output.exists(), 'Choose a new rollback output path')
    with zipfile.ZipFile(undo) as z:
        record = json.loads(z.read('undo.json'))
        original = z.read('sectors.dat')
    require(record['format'] == 1, 'Unsupported undo format')
    require(file_hash(source) == record['patched_sha256'],
            'Image changed after patching; keep it and restore from your original backup instead')
    require(digest(original) == record['undo_sha256'], 'Undo data checksum mismatch')
    size = source.stat().st_size
    for row in record['ranges']:
        a, length, pos = row['offset'], row['length'], row['undo_offset']
        require(0 <= a <= size and 0 < length <= size - a and 0 <= pos <= len(original) - length,
                'Invalid undo range')
    with source.open('rb') as src, output.open('xb') as dst:
        shutil.copyfileobj(src, dst, 1024 * 1024)
        for row in record['ranges']:
            dst.seek(row['offset'])
            dst.write(original[row['undo_offset']:row['undo_offset'] + row['length']])
    require(file_hash(output) == record['original_sha256'], 'Rollback checksum mismatch')
    print('ROLLBACK: byte-identical original restored to a new file; patched input retained; PASS')


def main():
    require(__debug__, 'Run Python without -O; input validation must remain enabled')
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    for name in ('check', 'verify'):
        p = sub.add_parser(name)
        p.add_argument('input', type=Path)
    for name in ('apply', 'emulator'):
        p = sub.add_parser(name)
        p.add_argument('input', type=Path)
        p.add_argument('output', type=Path)
    p = sub.add_parser('rollback')
    p.add_argument('input', type=Path)
    p.add_argument('undo', type=Path)
    p.add_argument('output', type=Path)
    args = parser.parse_args()
    if args.command in ('check', 'verify'):
        check_nand(args.input, args.command == 'verify')
    elif args.command == 'apply':
        apply_nand(args.input, args.output)
    elif args.command == 'emulator':
        apply_emulator(args.input, args.output)
    else:
        rollback(args.input, args.undo, args.output)


if __name__ == '__main__':
    try:
        main()
    except (ValueError, AssertionError, KeyError, OSError, zipfile.BadZipFile) as error:
        print('ERROR: ' + str(error), file=sys.stderr)
        sys.exit(1)
