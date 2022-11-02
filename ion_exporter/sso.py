import hashlib
from base64 import urlsafe_b64encode
from secrets import token_bytes
from typing import Any, cast
from urllib.parse import parse_qs, urlparse

import httpx


def base64(b: bytes) -> str:
    return urlsafe_b64encode(b)[:43].decode()


def sha256(s: str) -> bytes:
    m = hashlib.sha256()
    m.update(s.encode())
    return m.digest()


class SSOClient(httpx.Client):
    DEFAULT_BASE_URL = "https://sso.arubainstanton.com"
    DEFAULT_SETTINGS_URL = "https://portal.arubainstanton.com/settings.json"

    def __init__(
        self,
        base_url: str = DEFAULT_BASE_URL,
        settings: dict | None = None,
        settings_url: str = DEFAULT_SETTINGS_URL,
        **kwargs: Any,
    ):
        self.settings = settings if settings else httpx.get(settings_url).json()
        super().__init__(base_url=base_url, **kwargs)

    def authenticate(self, username: str, password: str, otp: str | None = None) -> str:
        data = {"username": username, "password": password}
        if otp:
            data["otp"] = otp
        res = self.post("/aio/api/v1/mfa/validate/full", data=data)
        res.raise_for_status()
        token = res.json()
        return cast(str, token["access_token"])

    def authorize(self, session_token: str) -> tuple[str, str]:
        state = base64(token_bytes(32))
        code_verifier = base64(token_bytes(32))
        code_challenge = base64(sha256(code_verifier))
        params = {
            "client_id": self.settings["ssoClientIdAuthZ"],
            "redirect_uri": self.settings["ssoRedirectUrl"],
            "response_type": "code",
            "scope": "profile openid",
            "state": state,
            "code_challenge_method": "S256",
            "code_challenge": code_challenge,
            "sessionToken": session_token,
        }
        res = self.get("/as" + self.settings["ssoEndpointAuthZ"], params=params)
        qs = parse_qs(urlparse(res.headers["Location"]).query)
        return qs["code"][0], code_verifier

    def fetch_tokens(
        self, username: str, password: str, otp: str | None = None
    ) -> dict:
        session_token = self.authenticate(username, password, otp)
        authorization_code, code_verifier = self.authorize(session_token)
        data = {
            "client_id": self.settings["ssoClientIdAuthZ"],
            "redirect_uri": self.settings["ssoRedirectUrl"],
            "code": authorization_code,
            "code_verifier": code_verifier,
            "grant_type": "authorization_code",
        }
        res = self.post("/as" + self.settings["ssoEndpointTokens"], data=data)
        res.raise_for_status()
        return cast(dict, res.json())

    def refresh_token(self, refresh_token: str) -> dict:
        data = {
            "client_id": self.settings["ssoClientIdAuthZ"],
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        }
        res = self.post("/as" + self.settings["ssoEndpointTokens"], data=data)
        res.raise_for_status()
        return cast(dict, res.json())
