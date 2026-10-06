"""Windows Credential Manager storage with a small injectable test seam."""
import ctypes
from ctypes import wintypes


class WindowsCredentialBackend:
    CRED_TYPE_GENERIC=1
    CRED_PERSIST_LOCAL_MACHINE=2

    class CREDENTIALW(ctypes.Structure):
        _fields_=[('Flags',wintypes.DWORD),('Type',wintypes.DWORD),('TargetName',wintypes.LPWSTR),
                  ('Comment',wintypes.LPWSTR),('LastWritten',wintypes.FILETIME),('CredentialBlobSize',wintypes.DWORD),
                  ('CredentialBlob',ctypes.c_void_p),('Persist',wintypes.DWORD),('AttributeCount',wintypes.DWORD),
                  ('Attributes',ctypes.c_void_p),('TargetAlias',wintypes.LPWSTR),('UserName',wintypes.LPWSTR)]

    def __init__(self):
        self.advapi=ctypes.WinDLL('advapi32',use_last_error=True)
        self.advapi.CredWriteW.argtypes=[ctypes.POINTER(self.CREDENTIALW),wintypes.DWORD]
        self.advapi.CredWriteW.restype=wintypes.BOOL
        self.advapi.CredReadW.argtypes=[wintypes.LPCWSTR,wintypes.DWORD,wintypes.DWORD,ctypes.POINTER(ctypes.POINTER(self.CREDENTIALW))]
        self.advapi.CredReadW.restype=wintypes.BOOL
        self.advapi.CredDeleteW.argtypes=[wintypes.LPCWSTR,wintypes.DWORD,wintypes.DWORD]
        self.advapi.CredDeleteW.restype=wintypes.BOOL
        self.advapi.CredFree.argtypes=[ctypes.c_void_p]

    def set(self,name,secret):
        raw=secret.encode('utf-16-le');buffer=ctypes.create_string_buffer(raw)
        cred=self.CREDENTIALW(Type=self.CRED_TYPE_GENERIC,TargetName=name,CredentialBlobSize=len(raw),
                              CredentialBlob=ctypes.cast(buffer,ctypes.c_void_p),Persist=self.CRED_PERSIST_LOCAL_MACHINE,
                              UserName='GermanJobRadar')
        if not self.advapi.CredWriteW(ctypes.byref(cred),0):
            raise OSError(ctypes.get_last_error(),'无法写入 Windows 凭据保险库')

    def get(self,name):
        pointer=ctypes.POINTER(self.CREDENTIALW)()
        if not self.advapi.CredReadW(name,self.CRED_TYPE_GENERIC,0,ctypes.byref(pointer)):
            if ctypes.get_last_error()==1168:return None
            raise OSError(ctypes.get_last_error(),'无法读取 Windows 凭据保险库')
        try:
            raw=ctypes.string_at(pointer.contents.CredentialBlob,pointer.contents.CredentialBlobSize)
            return raw.decode('utf-16-le')
        finally:self.advapi.CredFree(pointer)

    def delete(self,name):
        if not self.advapi.CredDeleteW(name,self.CRED_TYPE_GENERIC,0) and ctypes.get_last_error()!=1168:
            raise OSError(ctypes.get_last_error(),'无法删除 Windows 凭据')


class CredentialStore:
    def __init__(self,backend=None):self.backend=backend or WindowsCredentialBackend()
    def set(self,name,secret):
        if not isinstance(name,str) or not name or not isinstance(secret,str):raise ValueError('凭据无效')
        secret=secret.strip()
        if not secret or len(secret)>4096 or any(c in secret for c in '\r\n\0'):raise ValueError('凭据无效')
        self.backend.set(name,secret)
    def get(self,name):return self.backend.get(name)
    def delete(self,name):self.backend.delete(name)
    def status(self,name):return {'configured':bool(self.get(name))}
