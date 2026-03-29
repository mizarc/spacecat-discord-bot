# src/spacecat/platforms/fluxer/dispatcher.py
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import fluxer

from spacecat.core.interfaces import BaseDispatcher

if TYPE_CHECKING:
    from spacecat.platforms.fluxer.client import FluxerClient

logger = logging.getLogger(__name__)


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

    async def dispatch_voice_move(self, source_channel: int, destination_channel: int) -> None:
        """
        Move a user to a different voice channel.

        Args:
            source_channel: The ID of the source voice channel.
            destination_channel: The ID of the destination voice
                channel.
        """
        source_vc = await self.bot.fetch_channel(str(source_channel))
        target_vc = await self.bot.fetch_channel(str(destination_channel))
        voice_states = self.bot.get_guild_voice_states(source_vc.guild_id)

        # Check if channels exist
        if not source_vc or not target_vc:
            logger.warning("Voice Move Failed: Source or Target channel not found.")
            return

        # Iterate through all members currently in the source channel
        channel_members = [state for state in voice_states if state.channel_id == source_channel]
        guild = await self.bot.fetch_guild(str(source_vc.guild_id))
        for voice_state in channel_members:
            try:
                # Fetch guild member instance for each to move into destination channel
                member = await guild.fetch_member(voice_state.user_id)
                await member.edit(channel_id=destination_channel)
            except Exception:
                logger.exception(
                    "Failed to move member %s to channel %s",
                    voice_state.user_id,
                    destination_channel,
                )
