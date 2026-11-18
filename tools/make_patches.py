"""Author component deltas from locally supplied original and approved images.

No NAND, BIOS, user configuration, or device footer is copied into the package.
"""
from pathlib import Path
import argparse
import hashlib
import json
import struct
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import bsdiff4
from patch import NAND, boot_crypt, require

FILES = [
    ('settings', '/title/00030015/484e4243/content/00000001.app'),
    ('menu', '/title/00030017/484e4143/content/00000005.app'),
    ('pictochat', '/title/00030005/484e4543/content/00000000.app'),
    ('sound', '/title/00030005/484e4b43/content/00000000.app'),
]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('original-nand', 'modified-nand', 'original-emulator', 'modified-emulator'):
        p.add_argument('--' + name, type=Path, required=True)
    args = p.parse_args()
    require(not (ROOT / 'patches/manifest.json').exists(), 'Existing patch manifest is protected')
    sha = lambda data: hashlib.sha256(data).hexdigest()

    def delta(name, before, after):
        binary = bsdiff4.diff(before, after)
        require(bsdiff4.patch(before, binary) == after, 'Delta roundtrip failed')
        filename = 'patches/' + name + '.bsdiff'
        (ROOT / filename).write_bytes(binary)
        print(name + ': delta roundtrip PASS; patch bytes=' + str(len(binary)))
        return dict(name=name, before_sha256=sha(before), after_sha256=sha(after),
                    before_size=len(before), after_size=len(after), patch=filename,
                    patch_sha256=sha(binary))

    a, b = NAND(args.original_nand), NAND(args.modified_nand)
    try:
        items = []
        for name, path in FILES:
            item = delta(name, a.file(path), b.file(path))
            item.update(kind='file', path=path)
            items.append(item)
        a.f.seek(0x220)
        parameters = list(struct.unpack('<4I', a.f.read(16)))
        b.f.seek(0x220)
        require(b.f.read(16) == struct.pack('<4I', *parameters), 'boot2 parameters changed')
        for n in (a, b):
            n.f.seek(parameters[0])
        item = delta('boot2-arm9', boot_crypt(a.f.read(parameters[3])), boot_crypt(b.f.read(parameters[3])))
        item.update(kind='boot2', parameters=parameters)
        items.append(item)
    finally:
        a.close()
        b.close()
    emulator = delta('melonds-1.1-windows-x64-touch-reset', args.original_emulator.read_bytes(),
                     args.modified_emulator.read_bytes())
    data = dict(format=1, version='0.1.1', target='iQue DSi Chinese system components; emulator use',
                nand=items, emulator=emulator,
                upgrade={'from_version': '0.1.0', 'components': ['sound']},
                privacy='No full NAND, BIOS, footer, settings, saves, or local undo data included')
    (ROOT / 'patches/manifest.json').write_text(json.dumps(data, indent=2) + '\n', encoding='utf-8')
    print('BUILD: component deltas only; all roundtrips PASS')


if __name__ == '__main__':
    main()
