import base64

import pytest

from website import create_app
from website.config import CONFIG


@pytest.fixture()
def app():
    app = create_app()
    app.config["TESTING"] = True
    yield app


@pytest.fixture()
def client(app):
    return app.test_client()


class AuthClient:
    """Wraps Flask test client to inject Basic Auth on every request."""

    def __init__(self, test_client):
        self._client = test_client
        token = base64.b64encode(
            f"{CONFIG.admin_user}:{CONFIG.admin_pass}".encode()
        ).decode()
        self._headers = {"Authorization": f"Basic {token}"}

    def _merge(self, kwargs):
        hdrs = dict(self._headers)
        hdrs.update(kwargs.pop("headers", {}))
        kwargs["headers"] = hdrs
        return kwargs

    def get(self, *args, **kwargs):
        return self._client.get(*args, **self._merge(kwargs))

    def post(self, *args, **kwargs):
        return self._client.post(*args, **self._merge(kwargs))

    def patch(self, *args, **kwargs):
        return self._client.patch(*args, **self._merge(kwargs))

    def delete(self, *args, **kwargs):
        return self._client.delete(*args, **self._merge(kwargs))


@pytest.fixture()
def auth_client(app):
    return AuthClient(app.test_client())
