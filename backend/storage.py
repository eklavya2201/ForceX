import hashlib, mimetypes, os, re, secrets, shutil, zipfile
from datetime import datetime
from .extensions import db
from .models import utcnow

_CTRL=re.compile(r"[\x00-\x1f\x7f]")
def safe_relpath(raw,max_depth=20):
    p=(raw or "file").replace("\\","/"); p=re.sub(r"^[A-Za-z]:", "", p); parts=[]
    for part in p.split("/"):
        part=_CTRL.sub("",part).strip()
        if part in ("","."): continue
        if part=="..": raise ValueError("path traversal")
        parts.append(part[:200])
    if not parts or len(parts)>max_depth: raise ValueError("invalid path")
    return "/".join(parts)

def _dedupe(rel,seen):
    if rel not in seen: seen.add(rel); return rel
    folder,name=os.path.split(rel); stem,ext=os.path.splitext(name); i=1
    while True:
        candidate=os.path.join(folder,f"{stem} ({i}){ext}").replace("\\","/")
        if candidate not in seen: seen.add(candidate); return candidate
        i+=1

def _sha256(path):
    h=hashlib.sha256()
    with open(path,"rb") as f:
        for block in iter(lambda:f.read(1024*1024),b""): h.update(block)
    return h.hexdigest()
def _blob_path(app,key): return os.path.join(app.config["STORAGE_DIR"],"blobs",key)

def save_upload(app,files,paths):
    if not files or len(files)>app.config["MAX_FILES"]: raise ValueError("bad file count")
    root=os.path.join(app.config["STORAGE_DIR"],"tmp",secrets.token_hex(8)); os.makedirs(root,exist_ok=False); saved=[]
    try:
        seen=set()
        for i,f in enumerate(files):
            rel=safe_relpath(paths[i] if i<len(paths) else f.filename or "file",app.config["MAX_PATH_DEPTH"]); rel=_dedupe(rel,seen)
            part=os.path.join(root,f"{i}.part"); f.save(part); saved.append((part,rel,os.path.getsize(part)))
        os.makedirs(os.path.join(app.config["STORAGE_DIR"],"blobs"),exist_ok=True); key=secrets.token_hex(16); dest=_blob_path(app,key)
        manifest=[{"name":r,"size":s} for _,r,s in saved]
        single=len(saved)==1 and "/" not in saved[0][1]
        if single:
            part,rel,_=saved[0]; shutil.move(part,dest)
            try:
                import filetype
                kind=filetype.guess(dest)
            except ImportError: kind=None
            mime=kind.mime if kind else ("text/plain" if os.path.splitext(rel)[1].lower() in (".txt",".md",".log",".csv") else "application/octet-stream")
            display=rel; archive=False
        else:
            with zipfile.ZipFile(dest,"w",zipfile.ZIP_DEFLATED) as z:
                for part,rel,_ in saved: z.write(part,arcname=rel)
            mime="application/zip"; display="forcex-share.zip"; archive=True
        return {"storage_key":key,"display_name":display,"mime":mime,"size":os.path.getsize(dest),"sha256":_sha256(dest),"is_archive":archive,"manifest":manifest}
    finally: shutil.rmtree(root,ignore_errors=True)

def delete_share_blobs(share):
    for f in share.files:
        if f.deleted_at: continue
        path=_blob_path(__import__('flask').current_app,f.storage_key)
        try:
            if os.path.exists(path): os.remove(path)
            f.deleted_at=utcnow()
        except OSError: pass
    db.session.commit()

def enforce_mode(mode,info,app):
    note=""
    if len(info["manifest"])>1 or "/" in info["manifest"][0]["name"]:
        if mode!="download": note="Folders and multiple files are shared as a one-time download."
        mode="download"
    elif mode=="view" and info["mime"] not in app.config["INLINE_MIMES"]:
        mode="download"; note="This file type cannot be previewed safely, so download mode was selected."
    return mode,note
