"""OAuth token manager for GitLab's OFFICIAL MCP server (`/api/v4/mcp`).

The official server speaks OAuth 2.0, not PAT (GitLab issue #586184). Loopback is
human-in-the-loop, so a person authorizes ONCE in a browser (`scripts/oauth_spike.py`);
this module then turns the resulting refresh token into a valid access token on demand,
refreshing headlessly when the 2-hour access token expires. The MCP client wrapper uses
`get_access_token()` for its `Authorization: Bearer` header.

Token source (first that exists wins):
  1. `GITLAB_OAUTH_TOKEN_JSON` - the full JSON blob in an env var. How Cloud Run /
     Secret Manager supplies it; refreshed tokens are kept in memory for the instance's
     life (single always-on instance, so this survives a judging session).
  2. `GITLAB_OAUTH_TOKEN_FILE` (default: repo `.oauth_token.json`) - local dev; the
     rotated blob is written back so refresh survives restarts.

The blob must contain: access_token, refresh_token, client_id, token_endpoint, and
created_at + expires_in (as the spike saves them).
"""

from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path

import httpx

_DEFAULT_FILE = Path(__file__).parent.parent / ".oauth_token.json"
_EXPIRY_BUFFER = 120  # refresh this many seconds before the token actually expires


class GitLabOAuthError(RuntimeError):
    """Token is missing required fields or refresh failed."""


class GitLabOAuth:
    """Loads a saved OAuth token and refreshes it headlessly when near expiry."""

    def __init__(self, timeout: float = 30.0) -> None:
        self._lock = threading.Lock()
        self._timeout = timeout
        self._file: Path | None = None
        # Optional Secret Manager resource (e.g. projects/123/secrets/loopback-oauth).
        # When set, the rotated token is read from / written back to Secret Manager so it
        # survives container restarts across the judging window. Falls back to file/env.
        self._secret_resource = os.environ.get("GITLAB_OAUTH_SECRET_RESOURCE")
        self._blob = self._load()

    @staticmethod
    def _validate(blob: dict) -> dict:
        for field in ("refresh_token", "client_id", "token_endpoint"):
            if not blob.get(field):
                raise GitLabOAuthError(
                    f"Token blob missing '{field}'. Re-run scripts/oauth_spike.py to "
                    f"regenerate a complete token blob."
                )
        return blob

    def _load(self) -> dict:
        if self._secret_resource:
            return self._validate(self._read_secret())
        raw = os.environ.get("GITLAB_OAUTH_TOKEN_JSON")
        if raw:
            try:
                return self._validate(json.loads(raw))
            except json.JSONDecodeError as e:
                raise GitLabOAuthError(f"GITLAB_OAUTH_TOKEN_JSON is not valid JSON: {e}") from e
        path = Path(os.environ.get("GITLAB_OAUTH_TOKEN_FILE", str(_DEFAULT_FILE)))
        if not path.exists():
            raise GitLabOAuthError(
                f"No OAuth token. Set GITLAB_OAUTH_SECRET_RESOURCE or GITLAB_OAUTH_TOKEN_JSON, "
                f"or run scripts/oauth_spike.py to create {path}."
            )
        self._file = path
        return self._validate(json.loads(path.read_text()))

    def _read_secret(self) -> dict:
        from google.cloud import secretmanager

        client = secretmanager.SecretManagerServiceClient()
        name = f"{self._secret_resource}/versions/latest"
        payload = client.access_secret_version(name=name).payload.data.decode("utf-8")
        return json.loads(payload)

    def _persist(self) -> None:
        """Write the (rotated) token blob back to its source so refresh survives restarts."""
        if self._secret_resource:
            from google.cloud import secretmanager

            client = secretmanager.SecretManagerServiceClient()
            client.add_secret_version(
                parent=self._secret_resource,
                payload={"data": json.dumps(self._blob).encode("utf-8")},
            )
        elif self._file is not None:
            self._file.write_text(json.dumps(self._blob, indent=2))

    def _expired(self) -> bool:
        created = self._blob.get("created_at", 0)
        expires_in = self._blob.get("expires_in", 0)
        if not created or not expires_in:
            return True  # unknown expiry -> refresh to be safe
        return time.time() >= (created + expires_in - _EXPIRY_BUFFER)

    def _refresh(self) -> None:
        resp = httpx.post(
            self._blob["token_endpoint"],
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            data={
                "grant_type": "refresh_token",
                "refresh_token": self._blob["refresh_token"],
                "client_id": self._blob["client_id"],
            },
            timeout=self._timeout,
        )
        if resp.status_code >= 400:
            raise GitLabOAuthError(
                f"refresh failed (HTTP {resp.status_code}): {resp.text[:200]}. "
                f"The refresh token may be revoked - re-run scripts/oauth_spike.py."
            )
        new = resp.json()
        # GitLab rotates the refresh token; carry over the static fields and persist.
        self._blob.update(
            {
                "access_token": new["access_token"],
                "refresh_token": new.get("refresh_token", self._blob["refresh_token"]),
                "expires_in": new.get("expires_in", 7200),
                "created_at": new.get("created_at", int(time.time())),
            }
        )
        self._persist()

    def get_access_token(self) -> str:
        """Return a valid access token, refreshing first if it is near expiry."""
        with self._lock:
            if self._expired():
                self._refresh()
            return self._blob["access_token"]


_singleton: GitLabOAuth | None = None
_singleton_lock = threading.Lock()


def get_access_token() -> str:
    """Process-wide convenience accessor for a valid GitLab OAuth access token."""
    global _singleton
    if _singleton is None:
        with _singleton_lock:
            if _singleton is None:
                _singleton = GitLabOAuth()
    return _singleton.get_access_token()


if __name__ == "__main__":
    # Smoke: load, force a refresh, and confirm we get a usable token back.
    mgr = GitLabOAuth()
    print("loaded token blob; forcing a refresh to validate the refresh path...")
    mgr._blob["created_at"] = 0  # make _expired() true
    tok = mgr.get_access_token()
    print(f"refreshed OK - access_token starts {tok[:10]}..., "
          f"new refresh_token persisted={'yes' if mgr._file else '(env, in-memory)'}")
