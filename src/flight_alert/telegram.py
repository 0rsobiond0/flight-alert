from __future__ import annotations

import httpx


class TelegramClient:
    def __init__(self, token: str | None, chat_id: str | None, http_client: httpx.Client | None):
        self.token = token
        self.chat_id = chat_id
        self.http_client = http_client

    def send(self, text: str, dry_run: bool = False) -> None:
        if dry_run:
            return None
        if not self.token or not self.chat_id or self.http_client is None:
            raise ValueError("Telegram credentials and client are required")
        try:
            response = self.http_client.post(
                f"https://api.telegram.org/bot{self.token}/sendMessage",
                data={"chat_id": self.chat_id, "text": text},
                timeout=30,
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise RuntimeError(f"Telegram request failed: {type(exc).__name__}") from None
