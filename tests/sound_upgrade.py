"""Test the v0.1.0 -> v0.1.1 copy-only upgrade with local, user-supplied images."""
from pathlib import Path
import argparse
import copy
import shutil
import sys
from unittest.mock import patch as mock_patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import patch


def rejected(action, output=None):
    try:
        action()
    except (ValueError, AssertionError):
        if output is not None:
            assert not output.exists() and not Path(str(output) + '.undo.zip').exists()
        return
    raise AssertionError('Expected operation to be rejected')


def damaged_copy(source, output, component):
    n = patch.NAND(source)
    try:
        address = n.dataaddr + (n.entries[component]['cluster'] - 2) * n.cluster_size
    finally:
        n.close()
    shutil.copyfile(source, output)
    with output.open('r+b') as f:
        f.seek(address)
        byte = f.read(1)
        f.seek(address)
        f.write(bytes([byte[0] ^ 1]))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--original', type=Path, required=True)
    parser.add_argument('--previous', type=Path, required=True)
    parser.add_argument('--reference', type=Path, required=True)
    parser.add_argument('--work', type=Path, required=True)
    args = parser.parse_args()
    args.work.mkdir(parents=True, exist_ok=False)
    out = args.work / 'MODIFIED_FILE.bin'
    before_hash = patch.file_hash(args.previous)
    patch.check_nand(args.previous, upgrade=True)
    patch.apply_nand(args.previous, out, upgrade=True)
    patch.check_nand(out, patched=True)

    info = patch.manifest()
    sound = next(item for item in info['nand'] if item['name'] == 'sound')
    a, b, reference = patch.NAND(args.previous), patch.NAND(out), patch.NAND(args.reference)
    try:
        assert a.fat == b.fat and a.entries == b.entries
        for item in info['nand']:
            actual = patch.boot_data(b, item) if item['kind'] == 'boot2' else b.file(item['path'])
            expected = patch.boot_data(reference, item) if item['kind'] == 'boot2' else reference.file(item['path'])
            assert actual == expected
        entry = a.entries[sound['path']]
        assert a.chain(entry['cluster'])[entry['size']:] == b.chain(entry['cluster'])[entry['size']:]
        allowed = set()
        for cluster in a.clusters(entry['cluster']):
            start = a.dataaddr + (cluster - 2) * a.cluster_size
            allowed.update(range(start, start + a.cluster_size, 512))
    finally:
        a.close()
        b.close()
        reference.close()
    changed = 0
    with args.previous.open('rb') as a, out.open('rb') as b:
        offset = 0
        while True:
            old, new = a.read(512), b.read(512)
            assert len(old) == len(new)
            if not old:
                break
            if old != new:
                assert offset in allowed
                changed += 1
            offset += len(old)
    assert changed > 0
    assert patch.file_hash(args.previous) == before_hash
    print(f'UPGRADE: only Sound file sectors changed ({changed}); existing apps, profiles, allocation, slack and footer preserved; PASS')

    restored = args.work / 'restored-v0.1.0.bin'
    patch.rollback(out, Path(str(out) + '.undo.zip'), restored)
    assert patch.file_hash(restored) == before_hash
    patch.check_nand(restored, upgrade=True)
    patch.check_nand(out, patched=True)
    print('ROLLBACK: previous-release NAND restored byte-for-byte; upgraded copy retained; PASS')

    for label, source in [('original', args.original), ('already-upgraded', out)]:
        bad_out = args.work / (label + '-rejected.bin')
        rejected(lambda s=source, o=bad_out: patch.apply_nand(s, o, upgrade=True), bad_out)
    rejected(lambda: patch.apply_nand(args.previous, out, upgrade=True))
    rejected(lambda: patch.apply_nand(args.previous, args.previous, upgrade=True))
    for label, item in [('other-component', info['nand'][0]), ('sound', sound)]:
        damaged = args.work / (label + '-damaged.bin')
        damaged_copy(args.previous, damaged, item['path'])
        bad_out = args.work / (label + '-rejected.bin')
        rejected(lambda s=damaged, o=bad_out: patch.apply_nand(s, o, upgrade=True), bad_out)
    bad_manifest = copy.deepcopy(info)
    next(item for item in bad_manifest['nand'] if item['name'] == 'sound')['patch_sha256'] = '0' * 64
    bad_out = args.work / 'bad-patch-rejected.bin'
    with mock_patch.object(patch, 'manifest', return_value=bad_manifest):
        rejected(lambda: patch.apply_nand(args.previous, bad_out, upgrade=True), bad_out)
    assert patch.file_hash(args.previous) == before_hash
    print('NEGATIVE: original, repeated upgrade, overwrite, in-place write, mismatched components and corrupt delta rejected before output; PASS')


if __name__ == '__main__':
    main()
