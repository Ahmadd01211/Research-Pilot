"""Live source-link and quality smoke using only an explicitly supplied synthetic fixture."""
import hashlib
import secrets
import sys
import time
from pathlib import Path
from uuid import uuid4

from smoke_documents import request

if __name__=="__main__":
    original=Path(sys.argv[1]).read_bytes()
    email="links-smoke-"+uuid4().hex+"@example.com";password=secrets.token_urlsafe(24)
    request("/auth/register","POST",{"email":email,"display_name":"Link quality fixture","password":password})
    request("/auth/login","POST",{"email":email,"password":password})
    project=request("/projects","POST",{"title":"Synthetic link-quality check","description":"","research_questions":[],"objectives":[],"request_id":str(uuid4())})
    base="/projects/"+project["id"]+"/documents"
    document=request(base+"?filename=Synthetic-links.pdf","POST",original,True)["document"]
    path=base+"/"+document["id"];deadline=time.monotonic()+45
    while time.monotonic()<deadline:
        state=request(path)
        if state["status"] in {"extracted","failed"}:break
        time.sleep(1)
    assert state["status"]=="extracted",state["processing"]["error_code"]
    page=request(path+"/pages/1");links=page["layout"]["links"]
    assert any(link["target"]=="https://example.org/dataset?source=paper" for link in links)
    assert sum(link["status"]=="internal" and link["target_page"]==2 for link in links)==2
    assert any(link["status"]=="blocked" for link in links)
    assert page["layout"]["quality"]["state"]=="needs_review"
    report=request(path+"/quality")
    assert report["not_assessed_pages"]==0 and report["review_pages"]==1 and report["link_count"]>=6
    assert report["source_sha256"]==hashlib.sha256(original).hexdigest()
    assert request(path+"/download")==original
    print("Link/quality smoke passed: real worker extraction, hidden URL, direct/named internal destinations, blocked action, versioned owned report and exact original.")
