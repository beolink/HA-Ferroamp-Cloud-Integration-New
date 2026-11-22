"""The Ferroamp cloud client: Keycloak login and token refresh, GraphQL.

Logs in the way the Ferroamp user app does (PROTOCOL.md) and keeps only
the offline refresh token it hands out. Whoever owns the client stores
that token (the config entry) and is told through ``on_refresh_token``
when Keycloak rotates it. The password is used once, in ``login``, and
never kept.
"""

from __future__ import annotations

import asyncio
import logging
import secrets
import time
from collections.abc import Callable
from typing import Any

import aiohttp

from . import protocol
from .const import AUTH_BASE, GRAPHQL_URL, TOKEN_MARGIN_S

_LOGGER = logging.getLogger(__name__)

TIMEOUT = aiohttp.ClientTimeout(total=30)
# Keycloak's login page answers a plain browser better than aiohttp's own
# user agent; the app itself logs in through the system browser.
USER_AGENT = "Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 (KHTML, like Gecko) Mobile Safari/537.36"


class AuthError(Exception):
    """The login or the stored token was refused: the owner has to log in
    again (Home Assistant's re-authentication)."""


class CloudError(Exception):
    """The cloud could not be reached or answered something unusable.
    Temporary: the next poll tries again."""


async def login(email: str, password: str, auth_base: str = AUTH_BASE) -> dict[str, Any]:
    """Log in with e-mail and password; return Keycloak's token answer.

    Runs in its own short-lived session, so the login page's cookies never
    reach Home Assistant's shared one. Raises AuthError when the page says
    no (wrong password, a second factor, an account that signs in with
    Apple or Google only) and CloudError when it cannot be reached.
    """
    verifier, challenge = protocol.pkce_pair()
    state = secrets.token_hex(16)
    url = protocol.auth_url(auth_base, state, secrets.token_hex(16), challenge)
    headers = {"User-Agent": USER_AGENT}
    # unsafe=True only lets the jar keep cookies for a host given as an IP
    # address (the tests' local server); the session lives for this login.
    try:
        async with aiohttp.ClientSession(cookie_jar=aiohttp.CookieJar(unsafe=True),
                                         timeout=TIMEOUT) as session:
            async with session.get(url, headers=headers) as resp:
                page = await resp.text()
            try:
                action, fields = protocol.login_form(page, email, password)
            except protocol.LoginError as err:
                raise CloudError(f"Ferroamp login page: {err.reason}") from err
            async with session.post(action, data=fields, headers=headers,
                                    allow_redirects=False) as resp:
                location = resp.headers.get("Location", "")
                if resp.status not in (302, 303) or "code=" not in location:
                    reason = protocol.page_error(await resp.text()) or (
                        f"HTTP {resp.status}: wrong password, or an extra login step"
                    )
                    raise AuthError(reason)
            try:
                code = protocol.code_from_redirect(location, state)
            except protocol.LoginError as err:
                raise AuthError(err.reason) from err
            async with session.post(f"{auth_base}/token",
                                    data=protocol.token_request(code, verifier),
                                    headers=headers) as resp:
                tokens = await resp.json(content_type=None)
                if resp.status != 200 or "refresh_token" not in tokens:
                    raise AuthError(f"token exchange refused: {tokens.get('error_description') or resp.status}")
                return tokens
    except (aiohttp.ClientError, asyncio.TimeoutError) as err:
        raise CloudError(f"Ferroamp login unreachable: {err}") from err


class FerroampCloud:
    """GraphQL against the Ferroamp cloud on behalf of one account."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        refresh_token: str,
        on_refresh_token: Callable[[str], None] | None = None,
        auth_base: str = AUTH_BASE,
        graphql_url: str = GRAPHQL_URL,
    ) -> None:
        self._session = session
        self._refresh_token = refresh_token
        self._on_refresh_token = on_refresh_token
        self._auth_base = auth_base
        self._graphql_url = graphql_url
        self._access_token: str | None = None
        self._expires_at = 0.0
        self._lock = asyncio.Lock()
        #: The errors of the latest query whose answer still carried data (a
        #: field the account may not read comes back null, with an error).
        self.last_errors: list[str] = []

    @property
    def refresh_token(self) -> str:
        return self._refresh_token

    async def _ensure_token(self, force: bool = False) -> str:
        async with self._lock:
            if not force and self._access_token and time.monotonic() < self._expires_at - TOKEN_MARGIN_S:
                return self._access_token
            try:
                async with self._session.post(
                    f"{self._auth_base}/token",
                    data=protocol.refresh_request(self._refresh_token),
                    headers={"User-Agent": USER_AGENT},
                    timeout=TIMEOUT,
                ) as resp:
                    body = await resp.json(content_type=None)
            except (aiohttp.ClientError, asyncio.TimeoutError, ValueError) as err:
                raise CloudError(f"token refresh failed: {err}") from err
            if resp.status in (400, 401) and body.get("error") in ("invalid_grant", "unauthorized_client"):
                raise AuthError(body.get("error_description") or body["error"])
            if resp.status != 200 or "access_token" not in body:
                raise CloudError(f"token refresh answered {resp.status}")
            self._access_token = body["access_token"]
            self._expires_at = time.monotonic() + float(body.get("expires_in", 300))
            rotated = body.get("refresh_token")
            if rotated and rotated != self._refresh_token:
                self._refresh_token = rotated
                if self._on_refresh_token is not None:
                    self._on_refresh_token(rotated)
            return self._access_token

    async def query(self, document: str, variables: dict[str, Any] | None = None) -> dict:
        """Run one query; return its ``data``. A refused token is renewed
        once before the error goes up."""
        for attempt in (0, 1):
            token = await self._ensure_token(force=attempt == 1)
            try:
                async with self._session.post(
                    self._graphql_url,
                    json={"query": document, "variables": variables or {}},
                    headers={"Authorization": f"Bearer {token}", "User-Agent": USER_AGENT},
                    timeout=TIMEOUT,
                ) as resp:
                    if resp.status == 401 and attempt == 0:
                        continue
                    if resp.status == 401:
                        raise AuthError("the API refused a fresh token")
                    if resp.status >= 500:
                        raise CloudError(f"API answered {resp.status}")
                    answer = await resp.json(content_type=None)
            except (aiohttp.ClientError, asyncio.TimeoutError, ValueError) as err:
                raise CloudError(f"API unreachable: {err}") from err
            self.last_errors = protocol.error_messages(answer)
            try:
                return protocol.data_of(answer)
            except protocol.GraphQLError as err:
                if err.unauthenticated and attempt == 0:
                    continue
                if err.unauthenticated:
                    raise AuthError(str(err)) from err
                raise CloudError(str(err)) from err
        raise CloudError("unreachable")  # pragma: no cover - the loop returns or raises

    async def subscribe_once(self, document: str, variables: dict[str, Any], wait_s: float = 8.0) -> dict | None:
        """The first event of a subscription on the server-sent event stream,
        as the app listens to it, or None when none comes within ``wait_s``.
        The stream is closed again right away."""
        token = await self._ensure_token()
        try:
            async with self._session.post(
                self._graphql_url + "/stream",
                json={"query": document, "variables": variables},
                headers={"Authorization": f"Bearer {token}", "User-Agent": USER_AGENT,
                         "Accept": "text/event-stream"},
                timeout=aiohttp.ClientTimeout(total=wait_s + 5, sock_read=wait_s),
            ) as resp:
                if resp.status != 200:
                    raise CloudError(f"stream answered {resp.status}")
                deadline = time.monotonic() + wait_s
                while time.monotonic() < deadline:
                    line = await resp.content.readline()
                    if not line:
                        return None
                    text = line.decode(errors="replace").strip()
                    if text.startswith("data:"):
                        try:
                            event = protocol.json_loads(text[5:].strip())
                        except ValueError:
                            continue
                        return protocol.data_of(event)
        except (aiohttp.ClientError, asyncio.TimeoutError) as err:
            raise CloudError(f"stream unreachable: {err}") from err
        except protocol.GraphQLError as err:
            raise CloudError(str(err)) from err
        return None
