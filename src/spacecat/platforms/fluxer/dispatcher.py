# src/spacecat/platforms/fluxer/dispatcher.py
from __future__ import annotations

from typing import TYPE_CHECKING

import fluxer

from spacecat.core.interfaces import BaseDispatcher

if TYPE_CHECKING:
    from spacecat.platforms.fluxer.client import FluxerClient


class FluxerDispatcher(BaseDispatcher):
    """Action dispatcher for the Fluxer platform."""

    def __init__(self, bot: FluxerClient) -> None:
        """Initialize the dispatcher with a Fluxer client."""
        self.bot = bot

    async def dispatch_reminder(self, channel_id: int, message_id: int, content: str) -> None:
        """
        Dispatch a reminder message to a specified channel.

        Args:
            channel_id: The ID of the channel to send the reminder to.
            message_id: The ID of the original reminder message to send
                the reply to.
            content: The content of the reminder message.
        """
        message = await self.bot.fetch_message(str(channel_id), str(message_id))
        await message.reply(content)

    async def dispatch_message(self, channel_id: int, content: str):
        channel = self.bot.get_channel(channel_id) or await self.bot.fetch_channel(channel_id)
        await channel.send(content)

    async def dispatch_embed(
        self, channel_id: int, title: str, description: str, color: int = 0x00FF00
    ):
        embed = fluxer.Embed(title=title, description=description, color=color)
        channel = self.bot.get_channel(channel_id) or await self.bot.fetch_channel(channel_id)
        await channel.send(embed=embed)

    async def dispatch_voice_move(self, guild_id: int, user_id: int, target_vc: int):
        guild = self.bot.get_guild(guild_id)
        member = await guild.get_member(user_id)
        if member and member.voice:
            await member.move_to(self.bot.get_channel(target_vc))

    # Add your other 17 types here...
