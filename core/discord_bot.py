"""Public stub of core.discord_bot -- the Discord bot ships in the private build."""
from __future__ import annotations


class OnyxBot:
    """Minimal stub. Instantiation requires a token; behaviour is otherwise undefined."""
    def __init__(self, token: str = "") -> None:
        if not token:
            raise ValueError("OnyxBot requires a Discord bot token.")
        self.token = token

    def run(self) -> None:
        raise NotImplementedError("Discord bot is only available in the private build of OnyxKraken.")
