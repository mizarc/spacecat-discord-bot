"""
This module provides social tools and games for users to play.

Commands within this module focus on the social aspects of interactions,
encouraging users to have fun and interact with others. Notable tools
include the dice roll which can be used for things like DnD or general
decision-making.
"""

from __future__ import annotations

import asyncio
import io
from typing import Self

import fluxer
import requests

import spacecat.core.features.social as core_social
from spacecat.platforms.fluxer.helpers import permissions


class Social(fluxer.Cog):
    """Commands suite to provide fun social interactions."""

    def __init__(self: Social, bot: fluxer.Bot) -> None:
        """
        Initializes a new instance of the Fun class.

        Args:
            bot: The bot instance.
        """
        super().__init__(bot)

    @fluxer.Cog.command()
    @permissions.check()
    async def coinflip(self: Self, ctx: fluxer.Message) -> None:
        """
        Simulates a coin flip.

        Args:
            ctx: The command context.
        """
        message = core_social.coinflip()
        await ctx.reply(message)

    @fluxer.Cog.command()
    @permissions.check()
    async def diceroll(self: Self, ctx: fluxer.Message, sides: int = 6) -> None:
        """
        Simulates a die roll with a given number of sides.

        Args:
            ctx: The command context.
            sides: The number of sides on the die.
                Defaults to 6.
        """
        message = core_social.diceroll(int(sides))
        await ctx.reply(message)

    @fluxer.Cog.command()
    @permissions.check()
    async def slap(self: Self, ctx: fluxer.Message, target: str) -> None:
        """
        Create a slap animation using a user's profile picture.

        Args:
            ctx: The command context.
            target: The user to slap. If not provided,
                it uses the command author's profile picture.
        """
        try:
            # Get the target user (default to command author if not specified)
            clean_id = target.replace("<@", "").replace("!", "").replace(">", "")
            user_instance = await self.bot.fetch_user(clean_id)

            # Get user's avatar
            avatar_url = user_instance.avatar_url or user_instance.default_avatar_url

            # Download the avatar
            response = await asyncio.to_thread(requests.get, avatar_url, timeout=10)
            response.raise_for_status()
            avatar_data = response.content

            # Create the slap GIF
            gif_data = core_social.slap(avatar_data)

            # Send the GIF
            gif_file = fluxer.File(io.BytesIO(gif_data), filename="slap.gif")
            await ctx.reply(file=gif_file)

        except requests.RequestException as e:
            await ctx.reply(f"Sorry, I couldn't create the slap animation: {e}")

    @fluxer.Cog.command()
    @permissions.check()
    async def wheelspin(self: Self, ctx: fluxer.Message, *, choices: str) -> None:
        """Spin a wheel of choices."""
        # Split by comma and clean up whitespace
        min_options = 2
        max_options = 15
        options = [opt.strip() for opt in choices.split(",") if opt.strip()]

        if len(options) < min_options:
            await ctx.reply("Please provide at least 2 options separated by commas!")
            return
        if len(options) > max_options:
            await ctx.reply("Too many options! Try to keep it under 15.")
            return

        # Get our animation frames
        header, frames = core_social.wheelspin(options)

        # Send the initial message
        message = await ctx.reply(f"**{header}**\n{frames[0][0]}")

        # Loop through frames and edit
        for i in range(1, len(frames)):
            content, delay = frames[i]
            await asyncio.sleep(delay)
            try:
                await message.edit(content=f"**{header}**\n{content}")
            except fluxer.errors.NotFound:
                # Handle cases where the message is deleted during spin
                break

        # Final flair: Bold the winner
        winner_text = frames[-1][0].replace("<--", "⬅️ **WINNER**")
        await message.edit(content=f"**{header}**\n{winner_text}")


async def setup(bot: fluxer.Bot) -> None:
    """
    Load the Fun cog.

    Args:
        bot (fluxer.Bot): The Fluxer bot instance.
    """
    await bot.add_cog(Social(bot))
