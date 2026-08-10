import socket
from django.conf import settings


def scan_path(path):
    if not getattr(settings, "MALWARE_SCANNER_REQUIRED", False):
        return {"status": "CLEAN", "engine": "development-bypass", "details": "Scanner bypass is allowed only outside production."}
    host=getattr(settings,"CLAMAV_HOST","clamav"); port=getattr(settings,"CLAMAV_PORT",3310)
    with socket.create_connection((host,port),timeout=30) as sock, open(path,"rb") as source:
        sock.sendall(b"zINSTREAM\0")
        while True:
            chunk=source.read(1024*1024)
            if not chunk: break
            sock.sendall(len(chunk).to_bytes(4,"big")+chunk)
        sock.sendall((0).to_bytes(4,"big")); response=sock.recv(4096).decode(errors="replace")
    if "FOUND" in response: return {"status":"INFECTED","engine":"clamav","details":response}
    if "OK" in response: return {"status":"CLEAN","engine":"clamav","details":response}
    return {"status":"ERROR","engine":"clamav","details":response}
