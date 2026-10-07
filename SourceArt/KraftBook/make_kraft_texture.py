import random,struct,zlib
from pathlib import Path
random.seed(31);n=512
def chunk(t,b):return struct.pack('>I',len(b))+t+b+struct.pack('>I',zlib.crc32(t+b)&0xffffffff)
rows=[]
for y in range(n):
 row=bytearray([0])
 for x in range(n):
  v=random.gauss(0,7);row.extend(max(0,min(255,int(c+v))) for c in (155,119,77))
 rows.append(row)
data=b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',n,n,8,2,0,0,0))+chunk(b'IDAT',zlib.compress(b''.join(rows)))+chunk(b'IEND',b'')
Path(__file__).with_name('T_Book_Kraft.png').write_bytes(data)
