import httpx
import pytest

from flight_alert.telegram import TelegramClient


def test_telegram_error_does_not_expose_token():
    token = "secret-token"
    request = httpx.Request("POST", f"https://api.telegram.org/bot{token}/sendMessage")
    response = httpx.Response(500, request=request)
    client = TelegramClient(token, "chat", httpx.Client(transport=httpx.MockTransport(lambda req: response)))
    with pytest.raises(RuntimeError) as error:
        client.send("hello")
    assert token not in str(error.value)
