"""Local image tests. Inputs and generated images are never release assets."""
from pathlib import Path
import argparse
import contextlib
import io
import json
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import patch
from tools.nand_writer import Writer


def main():
    p = argparse.ArgumentParser()
    p.add_argument('mode', choices=['baseline', 'modified', 'rollback', 'negative'])
    p.add_argument('--original', type=Path, required=True)
    p.add_argument('--reference', type=Path, required=True)
    p.add_argument('--emulator', type=Path, required=True)
    p.add_argument('--work', type=Path, default=ROOT / 'local-tests')
    args = p.parse_args()
    work = args.work
    work.mkdir(parents=True, exist_ok=True)
    out = work / 'MODIFIED_FILE.bin'
    if args.mode == 'baseline':
        patch.check_nand(args.original)
        print('BASELINE: original component hashes match; input opened read-only; PASS')
    elif args.mode == 'modified':
        patch.apply_nand(args.original, out)
        m, ref = patch.NAND(out), patch.NAND(args.reference)
        try:
            for item in patch.manifest()['nand']:
                a = patch.boot_data(m, item) if item['kind'] == 'boot2' else m.file(item['path'])
                b = patch.boot_data(ref, item) if item['kind'] == 'boot2' else ref.file(item['path'])
                assert a == b
        finally:
            m.close()
            ref.close()
        patch.apply_emulator(args.emulator, work / 'MODIFIED_FILE.exe')
        # A second original image with another valid saved profile must keep that profile.
        variant = work / 'variant-original.bin'
        shutil.copyfile(args.original, variant)
        a, b = patch.NAND(variant), patch.NAND(args.reference)
        writer = Writer(a)
        for name in ('/shared1/twlcfg0.dat', '/shared1/twlcfg1.dat'):
            data = b.file(name)
            entry = a.entries[name]
            for i, cluster in enumerate(a.clusters(entry['cluster'])):
                writer.write_plain(a.dataaddr + (cluster - 2) * a.cluster_size,
                                   data[i * a.cluster_size:(i + 1) * a.cluster_size])
        with variant.open('r+b') as f:
            for address, plain in writer.sectors.items():
                f.seek(address)
                f.write(a.crypt(address, bytes(plain)))
        a.close()
        b.close()
        patch.apply_nand(variant, work / 'variant-patched.bin')
        print('MODIFIED: approved components reproduced; unrelated files, profiles and footer preserved; emulator delta verified; PASS')
    elif args.mode == 'rollback':
        patch.rollback(out, Path(str(out) + '.undo.zip'), work / 'restored-original.bin')
        assert patch.file_hash(work / 'restored-original.bin') == patch.file_hash(args.original)
        exe = work / 'MODIFIED_FILE.exe'
        patch.rollback(exe, Path(str(exe) + '.undo.zip'), work / 'restored-emulator.exe')
        assert patch.file_hash(work / 'restored-emulator.exe') == patch.file_hash(args.emulator)
        patch.check_nand(out, patched=True)
        print('ROLLBACK: NAND and emulator restored byte-for-byte to new files; modified deliverables retained; PASS')
    else:
        def rejected(action):
            try:
                action()
            except (ValueError, AssertionError):
                return
            raise AssertionError('Expected operation to be rejected')
        rejected(lambda: patch.apply_nand(out, work / 'unsupported.bin'))
        assert not (work / 'unsupported.bin').exists()
        rejected(lambda: patch.apply_nand(args.original, out))
        rejected(lambda: patch.apply_nand(args.original, args.original))
        rejected(lambda: patch.rollback(out, Path(str(out) + '.undo.zip'), args.original))
        manifest = patch.manifest()
        bad = dict(manifest['nand'][0])
        bad['patch_sha256'] = '0' * 64
        n = patch.NAND(args.original)
        try:
            rejected(lambda: patch.transform(n.file(bad['path']), bad))
        finally:
            n.close()
        print('NEGATIVE: wrong version, overwrite, in-place write, rollback overwrite and corrupt patch rejected; PASS')


if __name__ == '__main__':
    main()
