"""Apply PlateLink's 70% opacity policy to its packaged PNGs, without dependencies."""
import struct
import zlib

def opacity70(data):
 if data[:8]!=b'\x89PNG\r\n\x1a\n':raise ValueError('PNG inválido')
 pos=8;compressed=[];header=None
 while pos<len(data):
  length=struct.unpack('>I',data[pos:pos+4])[0];kind=data[pos+4:pos+8];body=data[pos+8:pos+8+length];pos+=length+12
  if kind==b'IHDR':header=body
  elif kind==b'IDAT':compressed.append(body)
  elif kind==b'IEND':break
 w,h,depth,colour,compression,filtering,interlace=struct.unpack('>IIBBBBB',header)
 if not (0<w<=4096 and 0<h<=4096 and depth==8 and colour in (2,6) and compression==filtering==interlace==0):raise ValueError('Formato de textura no compatible')
 channels=4 if colour==6 else 3;stride=w*channels
 raw=zlib.decompress(b''.join(compressed));prior=bytearray(stride);output=bytearray()
 if len(raw)!=(stride+1)*h:raise ValueError('Datos PNG incompletos')
 for y in range(h):
  start=y*(stride+1);mode=raw[start];row=bytearray(raw[start+1:start+1+stride])
  for i in range(stride):
   left=row[i-channels] if i>=channels else 0;up=prior[i];corner=prior[i-channels] if i>=channels else 0
   if mode==0:predict=0
   elif mode==1:predict=left
   elif mode==2:predict=up
   elif mode==3:predict=(left+up)//2
   elif mode==4:
    p=left+up-corner;dist=(abs(p-left),abs(p-up),abs(p-corner));predict=(left,up,corner)[dist.index(min(dist))]
   else:raise ValueError('Filtro PNG inválido')
   row[i]=(row[i]+predict)&255
  prior=row;output.append(0)
  for x in range(w):output.extend(row[x*channels:x*channels+3]);output.append(179)
 def chunk(kind,body):return struct.pack('>I',len(body))+kind+body+struct.pack('>I',zlib.crc32(kind+body)&0xffffffff)
 return b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',w,h,8,6,0,0,0))+chunk(b'IDAT',zlib.compress(bytes(output),6))+chunk(b'IEND',b'')
