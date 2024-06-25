"""
Module for providing image based conversions and reactions.

Features within this module should pertain to the saving, loading, and
conversion of images. Notably, use cases currently include reaction
images as well as the automatic conversion of webp to gif since Discord
does not support animated webps.
"""

from __future__ import annotations

from pathlib import Path
from typing import Self

import discord
from discord import app_commands
from discord.ext import commands
from PIL import Image

from spacecat.helpers import constants, permissions


class PoliteCat(commands.Cog):
    """Image posting based features."""

    def __init__(self: PoliteCat, bot: commands.Bot) -> None:
        """
        Initialize the PoliteCat class.

        Args:
            bot (commands.Bot): The Discord bot instance.
        """
        self.bot = bot
        self.webp_convert = True

    @commands.Cog.listener()
    async def on_message(self: Self, message: discord.Message) -> None:
        """
        Listener for handling image detection and posting conversions.

        This method is called whenever a new message is received. When
        an image of webp format is detected, it gets converted into a
        gif if possible.

        This is due to Discord's poor support of animated webps.

        Args:
        self (Self): The instance of the PoliteCat class.
        message (discord.Message): The message object representing the
            incoming message.

        Returns:
        None
        """
        if not self.webp_convert:
            return

        # Check for valid webp attachment
        if not message.attachments or message.attachments[0].filename[-4:] != "webp":
            return

        # Fetch image from attachment
        gif = Path(f"{constants.CACHE_DIR}{message.id!s}.gif")
        webp = Path(f"{constants.CACHE_DIR}{message.id!s}.webp")
        await message.attachments[0].save(webp)
        image = Image.open(webp)

        # Check if webp is animated
        try:
            image.seek(1)
        except EOFError:
            return

        # Convert webp to gif
        try:
            image.info.pop("background", None)
            image.save(gif, "gif", save_all=True)

            # Add spoiler tag if original image is tagged as a spoiler
            spoiler = False
            if message.attachments[0].is_spoiler():
                spoiler = True

            await message.channel.send(
                f"**{message.author.display_name} sent:**\n{message.content}",
                file=discord.File(gif, spoiler=spoiler),
            )
            await message.delete()

        # Notify if conversion failed
        except discord.errors.HTTPException:
            embed = discord.Embed(
                colour=constants.EmbedStatus.FAIL.value,
                description="Failed to convert webp to gif. " "Image may be too large",
            )
            await message.channel.send(embed=embed)
            return
        finally:
            Path(gif).unlink()
            Path(webp).unlink()
        return

    @app_commands.command()
    @permissions.check()
    async def togglewebp(self: Self, interaction: discord.Interaction) -> None:
        """Toggle automatic WebP conversion."""
        if self.webp_convert:
            self.webp_convert = False
            embed = discord.Embed(
                colour=constants.EmbedStatus.NO.value,
                description="Automatic WebP conversion has been disabled",
            )
            await interaction.response.send_message(embed=embed)

        elif not self.webp_convert:
            self.webp_convert = True
            embed = discord.Embed(
                colour=constants.EmbedStatus.YES.value,
                description="Automatic WebP conversion has been enabled",
            )
            await interaction.response.send_message(embed=embed)

    @commands.group(invoke_without_command=True)
    @permissions.check()
    async def reactcfg(self: Self, ctx: commands.Context) -> None:
        """Configure available reaction images."""
        embed = discord.Embed(
            colour=constants.EmbedStatus.FAIL.value,
            description="Please specify a valid subcommand: `add/remove`",
        )
        await ctx.send(embed=embed)

    @reactcfg.group()
    @permissions.check()
    async def add(self: Self, ctx: commands.Context, name: str) -> None:
        """Add a reaction image."""
        # Check if attachment exists in message
        try:
            image = ctx.message.attachments[0]
        except IndexError:
            embed = discord.Embed(
                colour=constants.EmbedStatus.FAIL.value,
                description="There are no attachments in that message",
            )
            await ctx.send(embed=embed)
            return

        # Create reactions folder if it doesn't exist
        if not Path(constants.DATA_DIR + "reactions/").exists:
            Path(constants.DATA_DIR + "reactions/").mkdir()

        # Cancel if name already exists
        reactions = await self._get_reactions()
        if name in reactions:
            embed = discord.Embed(
                colour=constants.EmbedStatus.FAIL.value, description="Reaction name already in use"
            )
            await ctx.send(embed=embed)
            return

        # Check if file extension is valid and convert to webp when possible
        ext = image.filename.split(".")[-1]
        if ext in {"webp", "png"}:
            await image.save(Path(f"{constants.DATA_DIR}reactions/{name}.{ext}"))
        elif ext in {"jpg", "jpeg", "bmp", "png"}:
            await image.save(Path(f"{constants.DATA_DIR}reactions/{name}.webp"))
        else:
            await ctx.send("Image must be formatted in webp, png, jpg, bmp or gif")
            return

        embed = discord.Embed(
            colour=constants.EmbedStatus.YES.value, description=f"Added {name} to reactions"
        )
        await ctx.send(embed=embed)
        return

    @reactcfg.group()
    @permissions.check()
    async def remove(self: Self, ctx: commands.Context, name: str) -> None:
        """Remove a reaction image."""
        # Cancel if image name exists
        reactions = await self._get_reactions()
        if name not in reactions:
            embed = discord.Embed(
                colour=constants.EmbedStatus.FAIL.value,
                description="Reaction image does not exist",
            )
            await ctx.send(embed=embed)
            return

        # Remove specified image
        try:
            Path(f"{constants.DATA_DIR}reactions/{name}.webp").unlink()
        except FileNotFoundError:
            Path(f"{constants.DATA_DIR}reactions/{name}.gif").unlink()

        embed = discord.Embed(
            colour=constants.EmbedStatus.NO.value, description=f"Removed {name} from reactions"
        )
        await ctx.send(embed=embed)
        return

    @app_commands.command()
    @permissions.check()
    async def reactlist(self: Self, interaction: discord.Interaction) -> None:
        """List all reaction images."""
        reactions = self._get_reactions()

        # Alert if no reactions exist
        if not reactions:
            embed = discord.Embed(
                colour=constants.EmbedStatus.FAIL.value, description="No reactions are available"
            )
            await interaction.response.send_message(embed=embed)
            return

    @app_commands.command()
    @permissions.check()
    async def react(self: Self, interaction: discord.Interaction, name: str) -> None:
        """Use an image/gif as a reaction."""
        # Try sending WebP
        try:
            await interaction.response.send_message(
                file=discord.File(f"{constants.DATA_DIR}reactions/{name}.webp")
            )
        except FileNotFoundError:
            pass
        else:
            return

        # Try sending Gif
        try:
            await interaction.response.send_message(
                file=discord.File(f"{constants.DATA_DIR}reactions/{name}.gif")
            )
        except FileNotFoundError:
            pass
        else:
            return

        # Warn if reaction name doesn't exist
        embed = discord.Embed(
            colour=constants.EmbedStatus.FAIL.value,
            description=f"Reaction `{name}` does not exist",
        )
        await interaction.response.send_message(embed=embed)

    async def _get_reactions(self: Self) -> list:
        # Get all images from directory and add to list
        reactions = []
        for files in Path(constants.DATA_DIR + "reactions/*").glob("*"):
            existing_image = Path(Path(files).stem).name
            reactions.append(existing_image)
        return reactions


async def setup(bot: commands.Bot) -> None:
    """Load the PoliteCat cog."""
    await bot.add_cog(PoliteCat(bot))
