"""Utility commands for general bot functionality."""

from __future__ import annotations

import time
from datetime import datetime
from typing import Self

import fluxer

from spacecat.platforms.fluxer.helpers import permissions
import spacecat.core.features.utility as core_utility


class Utility(fluxer.Cog):
    """General utility commands."""

    def __init__(self: Utility, bot: fluxer.Bot) -> None:
        """Initialise the Utility cog.

        Args:
            bot: The bot instance.
        """
        super().__init__(bot)
        self.start_time = time.time()

    @fluxer.Cog.command()
    @permissions.check()
    async def avatar(self: Self, ctx, user: fluxer.User | None = None) -> None:
        """Get a user's avatar URL.

        Args:
            ctx: The command context.
            user: The user to get avatar for. Defaults to command author.
        """
        clean_id = user.replace("<@", "").replace("!", "").replace(">", "")
        user_instance = await self.bot.fetch_user(clean_id)
        response = core_utility.avatar(user_instance.avatar_url)
        await ctx.reply(response)

    @fluxer.Cog.command()
    @permissions.check()
    async def calc(self: Self, ctx, *, expression: str):
        """Core logic to calculate a math equation."""
        response = core_utility.calc(expression)
        await ctx.reply(response)

    @fluxer.Cog.command()
    @permissions.check()
    async def color(self: Self, ctx, hex_code: str) -> None:
        """Provides a visual preview and data for a color code.

        Args:
            ctx: The command context.
            hex_code: The hex color code (e.g., #FF5733).
        """
        try:
            # 1. Generate the image in memory
            buffer, data = core_utility.color(hex_code)

            # 2. Convert HEX for the embed color parameter
            # We need to strip the '#' and turn it into an int
            embed_color = int(hex_code.lstrip('#'), 16)

            # 3. Present data
            embed = fluxer.Embed(
                title=f"Color Preview: {hex_code}",
                color=embed_color
            )
            clean_hex = hex_code.lstrip('#')
            embed.set_thumbnail(url=f"https://dummyimage.com/100x100/{clean_hex}/{clean_hex}.png")
            embed.add_field(name="RGB", value=data["rgb"], inline=False)
            embed.add_field(name="HSL", value=data["hsl"], inline=False)
            embed.add_field(name="CMYK", value=data["cmyk"], inline=False)

            await ctx.reply(embed=embed)
        except ValueError:
            await ctx.reply("Invalid HEX code! Make sure it's in the format #RRGGBB.")

    @fluxer.Cog.command()
    @permissions.check()
    async def echo(self: Self, ctx, *, message: str) -> None:
        """Repeats a given message.

        Args:
            ctx: The command context.
            message: The message to repeat.
        """
        response = core_utility.echo(message)
        await ctx.reply(response)

    @fluxer.Cog.command()
    @permissions.check()
    async def ping(self: Self, ctx) -> None:
        """Check bot latency.

        Args:
            ctx: The command context.
        """
        await core_utility.ping(
            send_func=ctx.reply,
            edit_func=lambda msg, content: msg.edit(content=content)
        )

    @fluxer.Cog.command()
    @permissions.check()
    async def qrcode(self: Self, ctx, *, data: str) -> None:
        """Generates a QR code from the provided text or URL.

        Args:
            ctx: The command context.
            data: The URL or text to encode.
        """
        # 1. Logic call
        buffer = core_utility.qrcode(data)

        # 2. Prepare the file
        file = fluxer.File(fp=buffer, filename="qrcode.png")

        await ctx.reply(file=file)

    @fluxer.Cog.command()
    @permissions.check()
    async def timestamp(self: Self, ctx, *, time: str | None = None):
        if time is None:
            time = str(datetime.now())
        response = core_utility.timestamp(time)
        await ctx.reply(response)

    @fluxer.Cog.command()
    @permissions.check()
    async def uptime(self: Self, ctx) -> None:
        """Check how long the bot has been running.

        Args:
            ctx: The command context.
        """
        response = core_utility.uptime(self.start_time)
        await ctx.reply(response)


async def setup(bot: fluxer.Bot) -> None:
    """Load the Utility cog.

    Args:
        bot: The Fluxer bot instance.
    """
    await bot.add_cog(Utility(bot))
