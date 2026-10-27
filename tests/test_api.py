"""The cloud client against a fake Keycloak and GraphQL server."""

from __future__ import annotations

import asyncio
import urllib.parse

import pytest

aiohttp = pytest.importorskip("aiohttp")
from aiohttp import web
from aiohttp.test_utils import TestServer

from custom_components.ferroamp_cloud_control import api


class FakeCloud:
    """Keycloak's form login and token endpoint, and a GraphQL endpoint."""

    def __init__(self) -> None:
        self.password = "right"
        self.refresh_tokens = {"offline-1": "offline-2"}   # old -> rotated
        self.valid_access: set[str] = set()
        self.graphql_calls = 0
        self.app = web.Application()
        self.app.router.add_get("/oidc/auth", self.auth)
        self.app.router.add_post("/oidc/authenticate", self.authenticate)
        self.app.router.add_post("/oidc/token", self.token)
        self.app.router.add_post("/graphql", self.graphql)
        self.server = TestServer(self.app)

    def url(self, path: str) -> str:
        return str(self.server.make_url(path))

    async def auth(self, request: web.Request) -> web.Response:
        self.state = request.query["state"]
        resp = web.Response(content_type="text/html", text=(
            f'<form id="kc-form-login" action="{self.url("/oidc/authenticate")}?session=1&amp;tab=2" method="post">'
            '<input name="username" value=""><input name="password" type="password">'
            '<input type="hidden" name="credentialId" value=""></form>'))
        resp.set_cookie("AUTH_SESSION_ID", "s1")
        return resp

    async def authenticate(self, request: web.Request) -> web.Response:
        form = await request.post()
        if request.cookies.get("AUTH_SESSION_ID") != "s1":
            return web.Response(status=400, text="cookie not found")
        if form.get("password") != self.password:
            return web.Response(status=200, content_type="text/html",
                                text='<span id="input-error">Invalid username or password.</span>')
        raise web.HTTPFound(f"ferroampuser://app/auth/login?state={self.state}&code=c1")

    async def token(self, request: web.Request) -> web.Response:
        form = await request.post()
        if form["grant_type"] == "authorization_code":
            assert form["client_id"] == "user-app" and form["code"] == "c1" and form["code_verifier"]
            return web.json_response({"access_token": "a0", "expires_in": 3600,
                                      "refresh_token": "offline-1", "refresh_expires_in": 0})
        old = form["refresh_token"]
        if old not in self.refresh_tokens and old not in self.refresh_tokens.values():
            return web.json_response({"error": "invalid_grant", "error_description": "Offline session not active"},
                                     status=400)
        new = self.refresh_tokens.get(old, old)
        access = f"a-{len(self.valid_access) + 1}"
        self.valid_access.add(access)
        return web.json_response({"access_token": access, "expires_in": 3600, "refresh_token": new})

    async def graphql(self, request: web.Request) -> web.Response:
        self.graphql_calls += 1
        token = request.headers.get("Authorization", "").removeprefix("Bearer ")
        if token not in self.valid_access:
            return web.json_response({"errors": [{"message": "Unauthorized",
                                                  "extensions": {"code": "UNAUTHENTICATED"}}]})
        body = await request.json()
        return web.json_response({"data": {"echo": body["variables"]}})


def run(coro_fn):
    async def main():
        cloud = FakeCloud()
        await cloud.server.start_server()
        try:
            return await coro_fn(cloud)
        finally:
            await cloud.server.close()
    return asyncio.run(main())


def test_login_returns_the_offline_token():
    async def go(cloud):
        return await api.login("a@example.com", "right", auth_base=cloud.url("/oidc"))
    tokens = run(go)
    assert tokens["refresh_token"] == "offline-1"


def test_wrong_password_is_an_auth_error_with_keycloaks_words():
    async def go(cloud):
        with pytest.raises(api.AuthError) as err:
            await api.login("a@example.com", "wrong", auth_base=cloud.url("/oidc"))
        return str(err.value)
    assert run(go) == "Invalid username or password."


def test_query_refreshes_and_reports_a_rotated_token():
    async def go(cloud):
        rotated = []
        async with aiohttp.ClientSession() as session:
            client = api.FerroampCloud(session, "offline-1", rotated.append,
                                       auth_base=cloud.url("/oidc"), graphql_url=cloud.url("/graphql"))
            data = await client.query("query { x }", {"id": 1})
            again = await client.query("query { x }", {"id": 2})
        return data, again, rotated, client.refresh_token, cloud.graphql_calls
    data, again, rotated, token, calls = run(go)
    assert data == {"echo": {"id": 1}} and again == {"echo": {"id": 2}}
    assert rotated == ["offline-2"] and token == "offline-2"
    assert calls == 2   # the access token is reused, not fetched per query


def test_a_refused_access_token_is_renewed_once():
    async def go(cloud):
        async with aiohttp.ClientSession() as session:
            client = api.FerroampCloud(session, "offline-1",
                                       auth_base=cloud.url("/oidc"), graphql_url=cloud.url("/graphql"))
            await client.query("query { x }")
            cloud.valid_access.clear()          # the server forgets the access token
            data = await client.query("query { x }", {"n": 3})
        return data, cloud.graphql_calls
    data, calls = run(go)
    assert data == {"echo": {"n": 3}}
    assert calls == 3


def test_a_revoked_offline_token_is_an_auth_error():
    async def go(cloud):
        async with aiohttp.ClientSession() as session:
            client = api.FerroampCloud(session, "revoked",
                                       auth_base=cloud.url("/oidc"), graphql_url=cloud.url("/graphql"))
            with pytest.raises(api.AuthError):
                await client.query("query { x }")
    run(go)


def test_an_unreachable_cloud_is_a_cloud_error():
    async def go(cloud):
        base = cloud.url("/")
        await cloud.server.close()
        async with aiohttp.ClientSession() as session:
            client = api.FerroampCloud(session, "offline-1",
                                       auth_base=urllib.parse.urljoin(base, "oidc"),
                                       graphql_url=urllib.parse.urljoin(base, "graphql"))
            with pytest.raises(api.CloudError):
                await client.query("query { x }")
    run(go)
