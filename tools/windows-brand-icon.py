"""只修改新便携副本的图标资源，保留并复核其他PE资源。"""
import ctypes as c
from ctypes import wintypes as w
import struct,hashlib,json,sys
from pathlib import Path
k=c.WinDLL('kernel32',use_last_error=True)
k.LoadLibraryExW.argtypes=[w.LPCWSTR,w.HANDLE,w.DWORD];k.LoadLibraryExW.restype=w.HMODULE
k.FreeLibrary.argtypes=[w.HMODULE]
k.FindResourceExW.argtypes=[w.HMODULE,c.c_void_p,c.c_void_p,w.WORD];k.FindResourceExW.restype=w.HANDLE
k.LoadResource.argtypes=[w.HMODULE,w.HANDLE];k.LoadResource.restype=w.HANDLE
k.LockResource.argtypes=[w.HANDLE];k.LockResource.restype=c.c_void_p
k.SizeofResource.argtypes=[w.HMODULE,w.HANDLE];k.SizeofResource.restype=w.DWORD
TYPE=c.WINFUNCTYPE(w.BOOL,w.HMODULE,c.c_void_p,w.LPARAM)
NAME=c.WINFUNCTYPE(w.BOOL,w.HMODULE,c.c_void_p,c.c_void_p,w.LPARAM)
LANG=c.WINFUNCTYPE(w.BOOL,w.HMODULE,c.c_void_p,c.c_void_p,w.WORD,w.LPARAM)
k.EnumResourceTypesW.argtypes=[w.HMODULE,TYPE,w.LPARAM]
k.EnumResourceNamesW.argtypes=[w.HMODULE,c.c_void_p,NAME,w.LPARAM]
k.EnumResourceLanguagesW.argtypes=[w.HMODULE,c.c_void_p,c.c_void_p,LANG,w.LPARAM]
k.BeginUpdateResourceW.argtypes=[w.LPCWSTR,w.BOOL];k.BeginUpdateResourceW.restype=w.HANDLE
k.UpdateResourceW.argtypes=[w.HANDLE,c.c_void_p,c.c_void_p,w.WORD,c.c_void_p,w.DWORD];k.UpdateResourceW.restype=w.BOOL
k.EndUpdateResourceW.argtypes=[w.HANDLE,w.BOOL];k.EndUpdateResourceW.restype=w.BOOL
def identity(pointer):return pointer if pointer<=65535 else c.wstring_at(pointer)
def pointer(value):return c.c_void_p(value) if isinstance(value,int) else c.cast(c.c_wchar_p(value),c.c_void_p)
def resources(file):
    handle=k.LoadLibraryExW(str(file),None,2|32)
    if not handle:raise c.WinError(c.get_last_error())
    found={}
    @TYPE
    def types(module,kind,param):
        @NAME
        def names(module,kind,name,param):
            @LANG
            def languages(module,kind,name,language,param):
                entry=k.FindResourceExW(module,kind,name,language)
                raw=c.string_at(k.LockResource(k.LoadResource(module,entry)),k.SizeofResource(module,entry))
                found[(identity(kind),identity(name),language)]=raw
                return True
            k.EnumResourceLanguagesW(module,kind,name,languages,0);return True
        k.EnumResourceNamesW(module,kind,names,0);return True
    try:k.EnumResourceTypesW(handle,types,0)
    finally:k.FreeLibrary(handle)
    assert found,'PE_RESOURCES_MISSING'
    return found
def stamp(executable,icon,expected):
    executable=executable.resolve();icon=icon.resolve()
    assert executable.name=='DAWLoop.exe' and Path('D:/1DAWLoop/Desktop').resolve() in executable.parents,'NEW_CANDIDATE_ONLY'
    assert hashlib.sha256(executable.read_bytes()).hexdigest()==expected,'ORIGINAL_EXECUTABLE_HASH_MISMATCH'
    before=resources(executable);groups=[key for key in before if key[0]==14]
    assert len(groups)==1,'ICON_GROUP_AUDIT_REQUIRED'
    raw=icon.read_bytes();reserved,kind,count=struct.unpack_from('<HHH',raw)
    assert reserved==0 and kind==1 and 1<=count<=32,'ICO_REJECTED'
    images=[];directory=bytearray(struct.pack('<HHH',0,1,count))
    for i in range(count):
        width,height,colors,reserved,planes,bits,size,offset=struct.unpack_from('<BBBBHHII',raw,6+i*16)
        assert offset>=6+16*count and offset+size<=len(raw),'ICO_REJECTED'
        images.append(raw[offset:offset+size]);directory.extend(struct.pack('<BBBBHHIH',width,height,colors,reserved,planes,bits,size,i+1))
    handle=k.BeginUpdateResourceW(str(executable),False)
    if not handle:raise c.WinError(c.get_last_error())
    committed=False
    def update(kind,name,language,data):
        block=c.create_string_buffer(data) if data else None
        if not k.UpdateResourceW(handle,pointer(kind),pointer(name),language,block,len(data)):raise c.WinError(c.get_last_error())
    try:
        for kind,name,language in before:
            if kind in (3,14):update(kind,name,language,b'')
        _,group,language=groups[0]
        for i,data in enumerate(images,1):update(3,i,language,data)
        update(14,group,language,bytes(directory))
        if not k.EndUpdateResourceW(handle,False):raise c.WinError(c.get_last_error())
        committed=True
    finally:
        if not committed:k.EndUpdateResourceW(handle,True)
    after=resources(executable)
    assert {key:value for key,value in before.items() if key[0] not in (3,14)}=={key:value for key,value in after.items() if key[0] not in (3,14)},'NON_ICON_RESOURCE_CHANGED'
    assert after[(14,group,language)]==bytes(directory)
    assert all(after[(3,i,language)]==data for i,data in enumerate(images,1))
    return dict(status='PASS',frames=count,iconSha256=hashlib.sha256(raw).hexdigest(),exeSha256=hashlib.sha256(executable.read_bytes()).hexdigest(),otherResourcesUnchanged=True)
if __name__=='__main__':
    print(json.dumps(stamp(Path(sys.argv[1]),Path(sys.argv[2]),sys.argv[3])))
