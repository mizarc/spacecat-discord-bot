"""
This module provides fun games for users to play.

Features within this module must be fun little tools or games that the
user can play with their friends. Notable tools include the dice roll
which can be used for things like DnD or general decision making. Games
that are fun to play include the Rock Paper Scissors game.
"""

from __future__ import annotations

import asyncio
import io
import requests
from typing import Self

import fluxer

from spacecat.platforms.fluxer.helpers import permissions
import spacecat.core.features.social as core_social


class Social(fluxer.Cog):
    """Commands suite to provide fun social interactions."""

    def __init__(self: Social, bot: fluxer.Bot) -> None:
        """
        Initialises a new instance of the Fun class.

        Args:
            bot (fluxer.Bot): The bot instance.
        """
        super().__init__(bot)

    @fluxer.Cog.command()
    @permissions.check()
    async def coinflip(self: Self, ctx) -> None:
        """
        Simulates a coin flip.

        Args:
            ctx: The command context.
        """
        message = core_social.coinflip()
        await ctx.reply(message)

    @fluxer.Cog.command()
    @permissions.check()
    async def diceroll(self: Self, ctx, sides: int = 6) -> None:
        """
        Simulates a dice roll with a given number of sides.

        Args:
            ctx: The command context.
            sides (int, optional): The number of sides on the dice.
                Defaults to 6.
        """
        message = core_social.diceroll(int(sides))
        await ctx.reply(message)

    @fluxer.Cog.command()
    @permissions.check()
    async def slap(self: Self, ctx, target: str = None) -> None:
        """
        Create a slap animation using a user's profile picture.

        Args:
            ctx: The command context.
            target (str, optional): The user to slap. If not provided,
                uses the command author's profile picture.
        """
        try:
            # Get the target user (default to command author if not specified)
            clean_id = target.replace("<@", "").replace("!", "").replace(">", "")
            user_instance = await self.bot.fetch_user(clean_id)

            # Get user's avatar
            avatar_url = user_instance.avatar_url \
                if user_instance.avatar_url else target.default_avatar_url

            # Download the avatar
            response = requests.get(avatar_url)
            response.raise_for_status()
            avatar_data = response.content

            # Create the slap GIF
            gif_data = core_social.slap(avatar_data)

            # Send the GIF
            gif_file = fluxer.File(io.BytesIO(gif_data), filename="slap.gif")
            await ctx.reply(file=gif_file)

        except Exception as e:
            await ctx.reply(f"Sorry, I couldn't create the slap animation: {str(e)}")

    @fluxer.Cog.command()
    @permissions.check()
    async def wheelspin(self: Self, ctx, *, choices: str) -> None:
        """Spin a wheel of choices."""
        # Split by comma and clean up whitespace
        options = [opt.strip() for opt in choices.split(",") if opt.strip()]

        if len(options) < 2:
            return await ctx.reply("Please provide at least 2 options separated by commas!")
        if len(options) > 15:
            return await ctx.reply("Too many options! Try to keep it under 15.")

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
            except Exception:
                # Handle cases where the message is deleted during spin
                break

        # Final flair: Bold the winner
        winner_text = frames[-1][0].replace("<--", "⬅️ **WINNER**")
        return await message.edit(content=f"**{header}**\n{winner_text}")


async def setup(bot: fluxer.Bot) -> None:
    """
    Load the Fun cog.

    Args:
        bot (fluxer.Bot): The Fluxer bot instance.
    """
    await bot.add_cog(Fun(bot))
