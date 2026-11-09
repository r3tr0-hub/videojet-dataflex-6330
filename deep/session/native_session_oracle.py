"""Offline execution of original ARM IRP serializers. No Windows or network calls.
Use VJ_BIN_ROOT and PYTHONPATH containing pefile + unicorn. Fixed SHA-256 only.
"""
from pathlib import Path
import sys, os, struct, hashlib
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'vj_continue'/'deps'))
import pefile
from unicorn import Uc, UC_ARCH_ARM, UC_MODE_ARM, UC_HOOK_CODE
from unicorn.arm_const import *
EXPECTED='df4136842b7da9b20f6fc37c851d74016116609694c2eb7f3477e13ba8568fb1'
class Oracle:
 def __init__(self):
  default=Path(__file__).resolve().parents[2]/'vj_continue/source/microSD 409720r12SP5/CLARiTY/BIN'
  p=Path(os.environ.get('ZBC2_DLL',str(Path(os.environ.get('VJ_BIN_ROOT',default))/'ZBC2.dll')))
  raw=p.read_bytes()
  if hashlib.sha256(raw).hexdigest()!=EXPECTED: raise ValueError('Unsupported DLL SHA256')
  pe=pefile.PE(data=raw); self.base=pe.OPTIONAL_HEADER.ImageBase
  self.u=Uc(UC_ARCH_ARM,UC_MODE_ARM);self.u.mem_map(self.base,0xb0000);self.u.mem_write(self.base,pe.get_memory_mapped_image())
  self.u.mem_map(0x10000000,0x100000);self.u.mem_map(0x20000000,0x200000)
  self.hooks={0x446e80b4:self.memcpy,0x446e81e0:self.wcslen,0x446e8328:self.strlen,0x446e816c:self.noop,0x446e7b10:self.noop,0x446e7b20:self.noop}
  self.hooks[0x446e89dc]=self.variant_to_system_time;self.hooks[0x10000050]=self.udiv;self.w(0x4470e17c,0x10000050)
  self.u.hook_add(UC_HOOK_CODE,self.oncode)
 def oncode(self,u,a,s,ud):
  if a in self.hooks:self.hooks[a]();u.reg_write(UC_ARM_REG_PC,u.reg_read(UC_ARM_REG_LR))
  elif a>=0x446e7900:raise RuntimeError('Unexpected runtime/import: %08x'%a)
 def r(self,i):return self.u.reg_read([UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3][i])
 def w(self,a,v):self.u.mem_write(a,struct.pack('<I',v))
 def v(self,a):return struct.unpack('<I',self.u.mem_read(a,4))[0]
 def udiv(self):
  divisor,dividend=self.r(0),self.r(1);self.u.reg_write(UC_ARM_REG_R0,dividend//divisor);self.u.reg_write(UC_ARM_REG_R1,dividend%divisor)
 def memcpy(self):self.u.mem_write(self.r(0),bytes(self.u.mem_read(self.r(1),self.r(2))))
 def strlen(self):
  a=self.r(0);n=0
  while self.u.mem_read(a+n,1)!=b'\0':n+=1
  self.u.reg_write(UC_ARM_REG_R0,n)
 def wcslen(self):
  a=self.r(0);n=0
  while self.u.mem_read(a+2*n,2)!=b'\0\0':n+=1
  self.u.reg_write(UC_ARM_REG_R0,n)
 def variant_to_system_time(self):
  # Stub of OLEAUT32 conversion, only serializer field extraction is tested.
  self.u.mem_write(self.r(2),struct.pack('<8H',*self.systemtime));self.u.reg_write(UC_ARM_REG_R0,1)
 def noop(self):self.u.reg_write(UC_ARM_REG_R0,0)
 def call(self,a,*args):
  sp=0x201ff000
  for i in range(4):self.u.reg_write([UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3][i],args[i] if i<len(args) else 0)
  for i,x in enumerate(args[4:]):self.w(sp+4*i,x)
  self.u.reg_write(UC_ARM_REG_SP,sp);self.u.reg_write(UC_ARM_REG_LR,0x10000010);self.u.emu_start(a,0x10000010,count=1000000)
  if self.u.reg_read(UC_ARM_REG_PC)!=0x10000010:raise RuntimeError('Instruction limit')
  return self.r(0)
 def start(self):
  self.ctx=0x10001000;self.buf=0x10010000;self.obj=0x10040000
  self.u.mem_write(self.ctx,bytes(0x238));self.u.mem_write(self.obj,bytes(0x400));self.u.mem_write(self.buf,bytes(0x10000))
  for off,v in [(4,0xffffffff),(0xc,self.buf),(0x10,0x10000),(0x14,0x10000)]:self.w(self.ctx+off,v)
  self.w(self.obj+4,self.ctx);self.call(0x446ac9d4,self.obj)
 def ptr(self,data,unicode=False,index=0):
  p=0x10050000+index*0x1000;raw=data.encode('utf-16-le') if unicode else bytes(data)
  self.u.mem_write(p,raw+(b'\0\0' if unicode else b'\0'));return p
 def append(self,tag,*values):
  if tag==1:a,b,c,t=values;self.call(0x446ad1c4,self.obj,a,b,c,self.ptr(t))
  elif tag==2:self.call(0x446ad2c0,self.obj,*values)
  elif tag in (3,8):t,a,b,*ts=values;self.call(0x446ad4cc if tag==8 else 0x446ad39c,self.obj,self.ptr(t,tag==8),a,b,*ts)
  elif tag==4:self.call(0x446ad5fc,self.obj,self.ptr(values[0]),self.ptr(values[1],index=1))
  elif tag==5:self.call(0x446ad718,self.obj,*values)
  elif tag==6:self.call(0x446ad780,self.obj,*values)
  elif tag==7:self.call(0x446ad82c,self.obj,*values)
  elif tag==9:
   free,total=values;self.call(0x446ad974,self.obj,free&0xffffffff,free>>32,total&0xffffffff,total>>32)
  elif tag==10:
   supported,enabled,prints,failures,h,m,s,d,month,y=values
   self.systemtime=(y,month,0,d,h,m,s,0);self.call(0x446ada00,self.obj,supported,enabled,prints,failures,0,0)
  else:raise ValueError('Unsupported tag')
 def bytes(self):return bytes(self.u.mem_read(self.buf,self.v(self.ctx+0x18)))
 def negotiation(self,version,features,compatibility=False):
  # Run original arithmetic and compatibility branch with parsed IRP fields.
  fp=0x201fe000;owner=0x10000000;worker=0x10080000;message=0x10070000
  self.u.mem_write(owner,bytes(0x53000));self.u.mem_write(worker,bytes(0x40));self.u.mem_write(message,bytes(0x900))
  self.w(worker+4,owner);self.u.mem_write(owner+0x520f4,bytes([bool(compatibility)]))
  self.u.mem_write(message+0x724,struct.pack('<H',version));self.w(message+0x728,features)
  self.u.reg_write(UC_ARM_REG_R3,message+0x600);self.u.reg_write(UC_ARM_REG_R5,worker)
  self.u.reg_write(UC_ARM_REG_FP,fp);self.u.reg_write(UC_ARM_REG_SP,fp-0x100)
  self.u.emu_start(0x446a4f40,0x446a4f9c,count=10000)
  return self.u.reg_read(UC_ARM_REG_R9),self.u.reg_read(UC_ARM_REG_R6)
 def idle_probe(self,compatibility=False):
  # Execute original idle scheduling block only; stop before any send.
  fp=0x201fe000;owner=0x10000000;worker=0x10080000;irq=0x10070000
  self.u.mem_write(owner,bytes(0x53000));self.u.mem_write(worker,bytes(0x40))
  self.w(worker+4,owner);self.w(worker+0x10,0x12345678);self.w(owner+0x51868,0x23456789)
  self.u.mem_write(owner+0x520f4,bytes([bool(compatibility)]));self.w(fp-0x3c,irq);self.w(fp-0x64,0)
  seen=[]
  def wait_stub():
   seen.append(tuple(self.r(i) for i in range(4)));self.u.reg_write(UC_ARM_REG_R0,258)
  self.hooks[0x446e7c90]=wait_stub
  self.u.reg_write(UC_ARM_REG_R5,worker);self.u.reg_write(UC_ARM_REG_FP,fp);self.u.reg_write(UC_ARM_REG_SP,fp-0x100)
  stop=0x446a54cc if compatibility else 0x446a5534
  self.u.emu_start(0x446a5410,stop,count=100000)
  if self.u.reg_read(UC_ARM_REG_PC)!=stop:raise RuntimeError('Idle slice did not stop')
  del self.hooks[0x446e7c90]
  return dict(wait_arguments=seen,selected_request=self.v(fp-0x6c) if not compatibility else None,expected_irq=irq)
 def message(self,records):
  self.start()
  for tag,values in records:self.append(tag,*values)
  return self.bytes()
if __name__=='__main__':
 o=Oracle();print(o.message([(7,(11,0xffedf)),(1,(0x11223344,0x55667788,9,b'OK'))]).hex())
