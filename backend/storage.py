import hashlib, mimetypes, os, re, secrets, shutil, zipfile
from datetime import datetime
from flask import current_app
from .extensions import db
from .models import utcnow
from . import blobstore

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
def _cache_path(app,key): return os.path.join(app.config["STORAGE_DIR"],"cache",key)

def blob():
    """The Vercel Blob client when files live in Blob storage (hosts without a disk), else None."""
    return blobstore.client() if current_app.config["STORAGE_BACKEND"]=="blob" else None

def blob_name(raw):
    # Last path segment, reduced to characters that need no URL encoding; it becomes the download filename.
    name=re.sub(r"[^A-Za-z0-9._-]+","_",os.path.basename((raw or "").replace("\\","/"))).strip("._-")
    return (name or "file")[-100:]

class BlobUpload:
    """A file the browser uploaded straight to Blob storage, shaped like the FileStorage save_upload expects."""
    def __init__(self,client,pathname,filename): self.client,self.pathname,self.filename=client,pathname,filename
    def save(self,dest): self.client.download(self.pathname,dest)

def save_upload(app,files,paths):
    if not files or len(files)>app.config["MAX_FILES"]: raise ValueError("bad file count")
    root=os.path.join(app.config["STORAGE_DIR"],"tmp",secrets.token_hex(8)); os.makedirs(root,exist_ok=False); saved=[]
    try:
        seen=set()
        for i,f in enumerate(files):
            rel=safe_relpath(paths[i] if i<len(paths) else f.filename or "file",app.config["MAX_PATH_DEPTH"]); rel=_dedupe(rel,seen)
            part=os.path.join(root,f"{i}.part"); f.save(part); saved.append((part,rel,os.path.getsize(part)))
        key=secrets.token_hex(16)
        manifest=[{"name":r,"size":s} for _,r,s in saved]
        single=len(saved)==1 and "/" not in saved[0][1]
        if single:
            built,rel,_=saved[0]
            try:
                import filetype
                kind=filetype.guess(built)
            except ImportError: kind=None
            mime=kind.mime if kind else ("text/plain" if os.path.splitext(rel)[1].lower() in (".txt",".md",".log",".csv") else "application/octet-stream")
            display=rel; archive=False
        else:
            built=os.path.join(root,"archive.zip")
            with zipfile.ZipFile(built,"w",zipfile.ZIP_DEFLATED) as z:
                for part,rel,_ in saved: z.write(part,arcname=rel)
            mime="application/zip"; display="forcex-share.zip"; archive=True
        size,sha=os.path.getsize(built),_sha256(built)
        client=blob(); blob_path=None
        if client:
            if single and isinstance(files[0],BlobUpload):
                # Already in place: the upload URL was signed for f/<key>/<name>.
                blob_path=files[0].pathname; key=blob_path.split("/")[1]
            else:
                blob_path=f"f/{key}/{blob_name(display)}"; client.put_file(blob_path,built,mime)
            leftovers=[f.pathname for f in files if isinstance(f,BlobUpload) and f.pathname!=blob_path]
            if leftovers: client.delete(leftovers)
            os.makedirs(os.path.dirname(_cache_path(app,key)),exist_ok=True); shutil.move(built,_cache_path(app,key))
        else:
            os.makedirs(os.path.join(app.config["STORAGE_DIR"],"blobs"),exist_ok=True); shutil.move(built,_blob_path(app,key))
        return {"storage_key":key,"blob_path":blob_path,"display_name":display,"mime":mime,"size":size,"sha256":sha,"is_archive":archive,"manifest":manifest}
    finally: shutil.rmtree(root,ignore_errors=True)

def local_path(app,f):
    """A path on this machine holding the stored file, fetched from Blob storage into a per-instance cache if needed."""
    client=blob()
    if not client: return _blob_path(app,f.storage_key)
    path=_cache_path(app,f.storage_key)
    if not os.path.exists(path):
        os.makedirs(os.path.dirname(path),exist_ok=True)
        part=f"{path}.{secrets.token_hex(4)}.part"
        try: client.download(f.blob_path,part); os.replace(part,path)
        finally:
            if os.path.exists(part): os.remove(part)
    return path

def signed_url(f,valid_seconds):
    """Short-lived direct URL to the stored file in Blob storage."""
    return blob().presign_get(f.blob_path,valid_seconds)

def delete_share_blobs(share):
    app=current_app; client=blob()
    for f in share.files:
        if f.deleted_at: continue
        try:
            if client:
                if f.blob_path: client.delete([f.blob_path])
                if os.path.exists(_cache_path(app,f.storage_key)): os.remove(_cache_path(app,f.storage_key))
            else:
                path=_blob_path(app,f.storage_key)
                if os.path.exists(path): os.remove(path)
            f.deleted_at=utcnow()
        except (OSError,blobstore.BlobError): app.logger.exception("Could not delete stored file %s",f.id)
    db.session.commit()

def enforce_mode(mode,info,app):
    note=""
    if len(info["manifest"])>1 or "/" in info["manifest"][0]["name"]:
        if mode!="download": note="Folders and multiple files are shared as a one-time download."
        mode="download"
    elif mode=="view" and info["mime"] not in app.config["INLINE_MIMES"]:
        mode="download"; note="This file type cannot be previewed safely, so download mode was selected."
    return mode,note
