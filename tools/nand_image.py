"""Read-only DSi NAND inspection. Never opens the input for writing.

Format references: melonDS src/DSi_NAND.cpp and src/DSi_AES.cpp;
https://dsibrew.org/wiki/Title_database
"""
from pathlib import Path
import hashlib
import json
import struct
import sys
import numpy as np
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

ROOT = Path(__file__).resolve().parent
SOURCE = None
MASK = (1 << 128) - 1

def sha256(path):
    with open(path, 'rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()

class NAND:
    def __init__(self, path):
        self.path = Path(path)
        self.f = self.path.open('rb')
        self.f.seek(-64, 2)
        footer = self.f.read(64)
        assert footer[:16] == b'DSi eMMC CID/CPU', 'missing NAND footer'
        lo, hi = struct.unpack_from('<II', footer, 32)
        kx = int.from_bytes(struct.pack('<IIII', lo, lo ^ 0x24ee6906, hi ^ 0xe65b601d, hi), 'little')
        ky = int.from_bytes(struct.pack('<IIII', 0x0ab9dc76, 0xbd4dc4d3, 0x202ddd1d, 0xe1a00005), 'little')
        v = ((kx ^ ky) + 0xfffefb4e295902582a680f5f1a4f3e79) & MASK
        self.key = (((v << 42) | (v >> 86)) & MASK).to_bytes(16, 'big')
        self.iv = int.from_bytes(hashlib.sha1(footer[16:32]).digest()[:16], 'little')
        self.base = 0x10ee00
        boot = self.read(self.base, 512)
        assert boot[510:512] == b'\x55\xaa', 'decrypted boot sector invalid'
        self.bps = struct.unpack_from('<H', boot, 11)[0]
        self.spc = boot[13]
        self.reserved = struct.unpack_from('<H', boot, 14)[0]
        self.nfats = boot[16]
        self.root_count = struct.unpack_from('<H', boot, 17)[0]
        self.spf = struct.unpack_from('<H', boot, 22)[0]
        assert self.bps == 512 and self.spc and self.spf and self.root_count, 'unexpected FAT format'
        self.fataddr = self.base + self.reserved * self.bps
        self.fat = self.read(self.fataddr, self.spf * self.bps)
        self.rootaddr = self.fataddr + self.nfats * self.spf * self.bps
        self.rootbytes = ((self.root_count * 32 + self.bps - 1) // self.bps) * self.bps
        self.dataaddr = self.rootaddr + self.rootbytes
        self.cluster_size = self.bps * self.spc
        self.entries = {}
        self.walk('', self.read(self.rootaddr, self.rootbytes))

    def crypt(self, address, data):
        assert address % 16 == 0 and len(data) % 16 == 0
        iv = ((self.iv + address // 16) & MASK).to_bytes(16, 'big')
        ctx = Cipher(algorithms.AES(self.key), modes.CTR(iv)).encryptor()
        reversed_blocks = np.frombuffer(data, dtype=np.uint8).reshape(-1, 16)[:, ::-1].tobytes()
        result = ctx.update(reversed_blocks) + ctx.finalize()
        return np.frombuffer(result, dtype=np.uint8).reshape(-1, 16)[:, ::-1].tobytes()

    def read(self, address, size):
        self.f.seek(address)
        data = self.f.read(size)
        assert len(data) == size, 'short read'
        return self.crypt(address, data)

    def clusters(self, first):
        seen = set()
        c = first
        while 2 <= c < 0xfff8:
            assert c not in seen, 'FAT cycle'
            assert 2*c + 2 <= len(self.fat), 'cluster out of range'
            seen.add(c)
            yield c
            c = struct.unpack_from('<H', self.fat, c*2)[0]

    def chain(self, first):
        return b''.join(self.read(self.dataaddr + (c-2)*self.cluster_size, self.cluster_size) for c in self.clusters(first))

    def walk(self, parent, buf):
        longname = {}
        for off in range(0, len(buf), 32):
            e = buf[off:off+32]
            if e[0] == 0:
                break
            if e[0] == 0xe5:
                longname = {}
                continue
            attr = e[11]
            if attr == 15:
                longname[e[0] & 31] = e[1:11] + e[14:26] + e[28:32]
                continue
            name = e[:8].decode('ascii', 'replace').rstrip()
            ext = e[8:11].decode('ascii', 'replace').rstrip()
            if ext:
                name += '.' + ext
            if longname:
                name = b''.join(longname[k] for k in sorted(longname)).decode('utf-16le').split('\0')[0].rstrip('\uffff')
            longname = {}
            if name in ('.', '..') or attr & 8:
                continue
            path = parent + '/' + name.lower()
            cluster = struct.unpack_from('<H', e, 26)[0]
            size = struct.unpack_from('<I', e, 28)[0]
            self.entries[path] = {'cluster': cluster, 'size': size, 'directory': bool(attr & 16)}
            if attr & 16:
                self.walk(path, self.chain(cluster))

    def file(self, name):
        e = self.entries[name.lower()]
        assert not e['directory']
        return self.chain(e['cluster'])[:e['size']]

    def close(self):
        self.f.close()
