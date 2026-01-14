# tests/functional/test_api_pytest.py

import pytest
import api


@pytest.mark.parametrize(
    "case",
    [
        {
            "account": "horns&hoofs",
            "login": "h&f",
            "method": "online_score",
            "token": "",
            "arguments": {},
        },
        {
            "account": "horns&hoofs",
            "login": "h&f",
            "method": "online_score",
            "token": "sdd",
            "arguments": {},
        },
        {
            "account": "horns&hoofs",
            "login": "admin",
            "method": "online_score",
            "token": "",
            "arguments": {},
        },
    ],
    ids=[
        "empty_token",
        "invalid_token",
        "admin_without_token",
    ],
)
def test_bad_auth_pytest(case):
    context = {}
    headers = {}
    store = None

    response, code = api.method_handler(
        {"body": case, "headers": headers},
        context,
        store,
    )

    assert code == api.FORBIDDEN
