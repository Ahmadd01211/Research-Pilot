"""Synthetic figure smoke through real HTTP/background processing; no external AI."""
import hashlib
import secrets
import time
from uuid import uuid4
from smoke_documents import request

def figure_pdf():
    content=b"q 300 0 0 150 72 550 cm /Im1 Do Q\nBT /F1 12 Tf 72 520 Td (FIGURE 1 Synthetic source illustration.) Tj ET\nBT /F1 12 Tf 72 450 Td (Figure 1 provides a synthetic illustration for source evidence testing.) Tj ET"
    objects=[b"<< /Type /Catalog /Pages 2 0 R >>",b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> /XObject << /Im1 6 0 R >> >> /Contents 5 0 R >>",b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",b"<< /Length "+str(len(content)).encode()+b" >>\nstream\n"+content+b"\nendstream",b"<< /Type /XObject /Subtype /Image /Width 1 /Height 1 /ColorSpace /DeviceRGB /BitsPerComponent 8 /Length 3 >>\nstream\n\x30\x60\xa0\nendstream"]
    output=b"%PDF-1.4\n"; offsets=[0]
    for n,obj in enumerate(objects,1):
        offsets.append(len(output)); output+=f"{n} 0 obj\n".encode()+obj+b"\nendobj\n"
    xref=len(output); output+=f"xref\n0 {len(offsets)}\n0000000000 65535 f \n".encode()
    for offset in offsets[1:]:output+=f"{offset:010d} 00000 n \n".encode()
    return output+f"trailer\n<< /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()

if __name__=="__main__":
    email="figure-smoke-"+uuid4().hex+"@example.com"; password=secrets.token_urlsafe(24)
    request("/auth/register","POST",{"email":email,"display_name":"Figure smoke fixture","password":password})
    request("/auth/login","POST",{"email":email,"password":password})
    project=request("/projects","POST",{"title":"Synthetic figure check","description":"","research_questions":[],"objectives":[],"request_id":str(uuid4())})
    original=figure_pdf(); base="/projects/"+project["id"]+"/documents"
    document=request(base+"?filename=Synthetic-figure.pdf","POST",original,True)["document"]
    path=base+"/"+document["id"]; deadline=time.monotonic()+45
    while time.monotonic()<deadline:
        state=request(path)
        if state["status"] in {"extracted","failed"}:break
        time.sleep(1)
    assert state["status"]=="extracted",state["processing"]["error_code"]
    figures=request(path+"/figures")["items"]
    assert len(figures)==1 and figures[0]["box"] is not None,figures
    assert figures[0]["caption"]=="FIGURE 1 Synthetic source illustration."
    assert figures[0]["related_passages"] and figures[0]["source_sha256"]==hashlib.sha256(original).hexdigest()
    assert request(path+"/download")==original
    print("Figure smoke passed: real extraction, caption/image association, author discussion, source identity, owned endpoint and exact original.")
