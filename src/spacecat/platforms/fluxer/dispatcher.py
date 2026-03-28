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

    async def dispatch_message(self, channel_id: int, content: str) -> None:
        """
        Dispatch a message to a specified channel.

        Args:
            channel_id: The ID of the channel to send the message to.
            content: The content of the message.
        """
        channel = await self.bot.fetch_channel(str(channel_id))
        await channel.send(content)

    async def dispatch_embed(
        self, channel_id: int, title: str, description: str, color: int = 0x00FF00
    ) -> None:
        """
        Dispatch an embed message to a specified channel.

        Args:
            channel_id: The ID of the channel to send the embed to.
            title: The title of the embed.
            description: The description of the embed.
            color: The color of the embed.
        """
        embed = fluxer.Embed(title=title, description=description, color=color)
        channel = self.bot.get_channel(channel_id) or await self.bot.fetch_channel(channel_id)
        await channel.send(embed=embed)

    async def dispatch_voice_move(self, guild_id: int, user_id: int, target_vc: int) -> None:
        """
        Move a user to a different voice channel.

        Args:
            guild_id: The ID of the guild the user is in.
            user_id: The ID of the user to move.
            target_vc: The ID of the target voice channel.
        """
        guild = self.bot.get_guild(guild_id)
        member = await guild.get_member(user_id)
        if member and member.voice:
            await member.move_to(self.bot.get_channel(target_vc))

    # Add your other 17 types here...
