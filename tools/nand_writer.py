"""FAT16 sector writer. The caller supplies a read-only NAND image."""
import struct

class Writer:
    def __init__(self,n):self.n=n;self.sectors={}
    def write_plain(self,address,data):
        while data:
            sector=address&~511;offset=address-sector;size=min(512-offset,len(data))
            if sector not in self.sectors:self.sectors[sector]=bytearray(self.n.read(sector,512))
            self.sectors[sector][offset:offset+size]=data[:size]
            address+=size;data=data[size:]
    def file_entry_address(self,path):
        parent,name=path.rsplit('/',1);chain=list(self.n.clusters(self.n.entries[parent]['cluster']))
        data=self.n.chain(chain[0]);found=[]
        for off in range(0,len(data),32):
            e=data[off:off+32]
            if e[0]==0:break
            if e[0]==0xe5 or e[11] in (15,8):continue
            short=e[:8].decode('ascii').rstrip()+'.'+e[8:11].decode('ascii').rstrip()
            if short.lower()==name:found.append(self.n.dataaddr+(chain[off//self.n.cluster_size]-2)*self.n.cluster_size+off%self.n.cluster_size)
        assert len(found)==1,(path,found)
        return found[0]
    def replace_file(self, path, data):
        """Replace an equal-sized file without changing its allocation or slack."""
        assert len(data) == self.n.entries[path]['size'], 'replacement size differs'
        for i, cluster in enumerate(self.n.clusters(self.n.entries[path]['cluster'])):
            chunk = data[i*self.n.cluster_size:(i+1)*self.n.cluster_size]
            if not chunk:
                break
            self.write_plain(self.n.dataaddr+(cluster-2)*self.n.cluster_size, chunk)
    def put_file(self,path,data,fat,used):
        old=list(self.n.clusters(self.n.entries[path]['cluster']));chain=old[:]
        need=(len(data)+self.n.cluster_size-1)//self.n.cluster_size
        need = max(need, len(chain))  # retain existing slack clusters; never free user data
        boot=self.n.read(self.n.base,512)
        sectors=struct.unpack_from('<H',boot,19)[0] or struct.unpack_from('<I',boot,32)[0]
        clusters=(sectors-self.n.reserved-self.n.nfats*self.n.spf-self.n.rootbytes//512)//self.n.spc
        for c in range(2,clusters+2):
            if len(chain)==need:break
            if c not in used and struct.unpack_from('<H',fat,c*2)[0]==0:chain.append(c);used.add(c)
        assert len(chain)==need,'not enough verified free clusters'
        if chain != old:
            for i,c in enumerate(chain):struct.pack_into('<H',fat,c*2,chain[i+1] if i+1<len(chain) else 0xffff)
        for i,c in enumerate(chain):
            chunk=data[i*self.n.cluster_size:(i+1)*self.n.cluster_size]
            self.write_plain(self.n.dataaddr+(c-2)*self.n.cluster_size,chunk.ljust(self.n.cluster_size,b'\0'))
        self.write_plain(self.file_entry_address(path)+28,struct.pack('<I',len(data)))
        return {'old_clusters':len(old),'new_clusters':len(chain),'first_cluster':chain[0],'old_size':self.n.entries[path]['size'],'new_size':len(data)}
