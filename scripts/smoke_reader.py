"""Local reader contract/asset checks with a real background-processed fixture."""
import hashlib
import re
import secrets
import time
import urllib.request
from uuid import uuid4
from smoke_documents import request, opener
from smoke_processing import pdf_bytes

def static(path):
    with opener.open(urllib.request.Request("http://127.0.0.1:3100"+path,headers={"Host":"localhost:3100"}),timeout=15) as response:
        return response.read(), response.headers

if __name__ == "__main__":
    email="reader-smoke-"+uuid4().hex+"@example.com"
    password=secrets.token_urlsafe(24)
    request("/auth/register","POST",{"email":email,"display_name":"Reader smoke fixture","password":password})
    request("/auth/login","POST",{"email":email,"password":password})
    project=request("/projects","POST",{"title":"Synthetic reader check","description":"","research_questions":[],"objectives":[],"request_id":str(uuid4())})
    path="/projects/"+project["id"]+"/documents"
    original=pdf_bytes()
    document=request(path+"?filename=Reader-source.pdf","POST",original,True)["document"]
    document_path=path+"/"+document["id"]
    deadline=time.monotonic()+40
    while time.monotonic()<deadline:
        state=request(document_path)
        if state["status"] in {"extracted","failed"}:break
        time.sleep(1)
    assert state["status"]=="extracted",state["processing"]["error_code"]
    page=request(document_path+"/pages/1")
    assert page["source_sha256"]==hashlib.sha256(original).hexdigest()
    assert page["layout"]["passages"] and page["layout"]["words"]
    assert len(page["layout"]["passages"][0]["id"])==64
    assert request(document_path+"/download")==original
    html,headers=static(f"/projects/{project['id']}/library/{document['id']}")
    assert "unsafe-eval" not in headers["Content-Security-Policy"]
    main=re.search(rb'src="(/assets/[^"]+\.js)"',html).group(1).decode()
    script,_=static(main)
    reader_chunk=re.search(rb'pdf-canvas-[A-Za-z0-9_-]+\.js',script).group(0).decode()
    chunk,_=static("/assets/"+reader_chunk)
    worker=re.search(rb'pdf\.worker\.min-[A-Za-z0-9_-]+\.mjs',chunk).group(0).decode()
    _,worker_headers=static("/assets/"+worker)
    assert "javascript" in worker_headers["Content-Type"]
    for asset in ["standard_fonts/FoxitSerif.pfb","cmaps/Adobe-Japan1-UCS2.bcmap","decoders/openjpeg_nowasm_fallback.js"]:
        body,_=static("/pdf-assets/"+asset)
        assert body and not body.startswith(b"<!doctype html>")
    print("Reader smoke passed: raw text + measured passages, source checksum, exact original, deep route, local PDF worker/fonts/decoders and strict CSP.")
