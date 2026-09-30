"""Vercel Blob (private store) over its HTTP API, for hosts without a persistent disk.

The official SDK is JavaScript; the Python SDK cannot presign URLs. Signing follows
@vercel/blob 2.8 (src/signed-token.ts): the server asks the API once for a delegation
token plus a client signing key, then signs each URL locally with HMAC-SHA256.
"""
import base64, hashlib, hmac, json, os, secrets, threading, time
import urllib.error, urllib.parse, urllib.request

API_URL = os.getenv("VERCEL_BLOB_API_URL", "https://vercel.com/api/blob")
API_VERSION = "12"

# Query keys that are part of the signature, in the SDK's order (it sorts the lines anyway).
_SIGNED_KEYS = ("vercel-blob-add-random-suffix", "vercel-blob-allow-overwrite", "vercel-blob-allowed-content-types",
                "vercel-blob-cache-control-max-age", "vercel-blob-callback-token-payload", "vercel-blob-callback-url",
                "vercel-blob-if-match", "vercel-blob-maximum-size-in-bytes", "vercel-blob-valid-until")


class BlobError(RuntimeError):
    pass


def _b64url(data):
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


def _b64url_decode(segment):
    return base64.urlsafe_b64decode(segment + "=" * (-len(segment) % 4))


class VercelBlob:
    def __init__(self, token):
        self.token = token
        # vercel_blob_rw_<storeId>_<secret>
        self.store_id = token.split("_")[3]
        self._delegations = {}
        self._lock = threading.Lock()

    # ---- plain API calls with the read-write token -------------------------------------------
    def _headers(self, extra=None):
        h = {"authorization": f"Bearer {self.token}", "x-api-version": API_VERSION,
             "x-vercel-blob-store-id": self.store_id,
             "x-api-blob-request-id": f"{self.store_id}:{int(time.time() * 1000)}:{secrets.token_hex(6)}",
             "x-api-blob-request-attempt": "0"}
        h.update(extra or {})
        return h

    def _request(self, url, method="GET", body=None, headers=None, timeout=120):
        req = urllib.request.Request(url, data=body, method=method, headers=headers or {})
        try:
            return urllib.request.urlopen(req, timeout=timeout)
        except urllib.error.HTTPError as e:
            detail = e.read()[:300].decode("utf-8", "replace")
            raise BlobError(f"Blob {method} {urllib.parse.urlsplit(url).path} failed: {e.code} {detail}") from None

    def blob_url(self, pathname):
        return f"https://{self.store_id}.private.blob.vercel-storage.com/{pathname}"

    def put_file(self, pathname, path, content_type="application/octet-stream"):
        size = os.path.getsize(path)
        url = f"{API_URL}/?{urllib.parse.urlencode({'pathname': pathname})}"
        headers = self._headers({"x-vercel-blob-access": "private", "x-content-type": content_type,
                                 "x-add-random-suffix": "0", "content-length": str(size)})
        with open(path, "rb") as f, self._request(url, "PUT", f, headers, timeout=300) as resp:
            return json.load(resp)

    def download(self, pathname, dest):
        with self._request(self.blob_url(pathname), headers={"authorization": f"Bearer {self.token}"}, timeout=300) as resp, open(dest, "wb") as out:
            while chunk := resp.read(1024 * 1024):
                out.write(chunk)

    def delete(self, pathnames):
        urls = [self.blob_url(p) for p in pathnames]
        if not urls:
            return
        body = json.dumps({"urls": urls}).encode()
        with self._request(f"{API_URL}/delete", "POST", body, self._headers({"content-type": "application/json"})):
            pass

    # ---- presigned URLs ------------------------------------------------------------------------
    def _delegation(self, operation, max_size=None):
        """A store-wide delegation for one operation, cached until 10 minutes before it expires."""
        key = (operation, max_size)
        with self._lock:
            cached = self._delegations.get(key)
            if cached and cached["validUntil"] - time.time() * 1000 > 10 * 60 * 1000:
                return cached
            body = {"pathname": "*", "operations": [operation], "validUntil": int((time.time() + 3600) * 1000)}
            if max_size:
                body["maximumSizeInBytes"] = max_size
            with self._request(f"{API_URL}/signed-token", "POST", json.dumps(body).encode(),
                               self._headers({"content-type": "application/json"})) as resp:
                issued = json.load(resp)
            scope = json.loads(_b64url_decode(issued["delegationToken"].split(".", 1)[0]))
            issued["validUntil"] = scope["validUntil"]
            issued["storeId"] = scope["storeId"].removeprefix("store_")
            self._delegations[key] = issued
            return issued

    def _sign(self, delegation, operation, pathname, entries):
        lines = [f"operation={operation}", f"pathname={pathname}"]
        lines += [f"{k}={v}" for k in _SIGNED_KEYS for ek, v in entries if ek == k and v]
        lines.sort(key=lambda s: s.encode())
        canonical = "\n".join(lines)
        signature = _b64url(hmac.new(delegation["clientSigningToken"].encode(), canonical.encode(), hashlib.sha256).digest())
        return entries + [("vercel-blob-delegation", delegation["delegationToken"]), ("vercel-blob-signature", signature)]

    def _entries(self, delegation, valid_seconds):
        until = int((time.time() + valid_seconds) * 1000)
        return [("vercel-blob-valid-until", str(until))] if until < delegation["validUntil"] else []

    def presign_get(self, pathname, valid_seconds=300):
        d = self._delegation("get")
        params = self._sign(d, "get", pathname, self._entries(d, valid_seconds))
        return f"https://{d['storeId']}.private.blob.vercel-storage.com/{pathname}?{urllib.parse.urlencode(params)}"

    def presign_put(self, pathname, max_size, delegation_max, valid_seconds=900):
        """URL a browser can PUT one file to, at exactly this pathname and at most max_size bytes."""
        d = self._delegation("put", delegation_max)
        entries = self._entries(d, valid_seconds) + [("vercel-blob-maximum-size-in-bytes", str(int(max_size))),
                                                     ("vercel-blob-add-random-suffix", "false"),
                                                     ("vercel-blob-allow-overwrite", "false")]
        params = [("pathname", pathname)] + self._sign(d, "put", pathname, entries)
        headers = {"x-vercel-blob-access": "private", "x-api-version": API_VERSION, "x-vercel-blob-store-id": d["storeId"]}
        return f"{API_URL}/?{urllib.parse.urlencode(params)}", headers


_client = None


def client():
    """The shared client, or None when no Blob store is configured."""
    global _client
    token = os.getenv("BLOB_READ_WRITE_TOKEN")
    if not token:
        return None
    if _client is None or _client.token != token:
        _client = VercelBlob(token)
    return _client
