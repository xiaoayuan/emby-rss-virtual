import requests


def refresh_emby(server_url: str, api_key: str, timeout: int = 15):
    if not server_url or not api_key:
        return {"ok": False, "error": "missing server_url/api_key"}

    base = server_url.rstrip("/")
    url = f"{base}/emby/Library/Refresh"
    try:
        r = requests.post(url, params={"api_key": api_key}, timeout=timeout)
        return {"ok": r.ok, "status": r.status_code, "text": r.text[:200]}
    except Exception as e:
        return {"ok": False, "error": str(e)}
