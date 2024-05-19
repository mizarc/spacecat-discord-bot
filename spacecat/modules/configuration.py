"""
This module provides a cog for managing the configuration of the bot.

Anything pertaining to bot wide changes should go here. Notable examples
include changing the bot's status and activity.
"""

from __future__ import annotations

from typing import Self

import aiofiles
import discord
import toml
from discord import app_commands
from discord.ext import commands

from spacecat.helpers import constants, perms


class Configuration(commands.Cog):
    """Modify Discord wide bot settings."""

    def __init__(self: Configuration, bot: commands.Bot) -> None:
        """Initialize the Configuration cog.

        Args:
            bot (commands.Bot): The Discord bot instance.
        """
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self: Self) -> None:
        """Listener that sets up the config values on launch."""
        # Auto generate the permissions config category with
        # default (@everyone) role
        config = toml.load(constants.DATA_DIR + "config.toml")
        try:
            config["permissions"]
        except KeyError:
            config["permissions"] = {}
        try:
            config["permissions"]["default"]
        except KeyError:
            config["permissions"]["default"] = []

        async with aiofiles.open(constants.DATA_DIR + "config.toml", "w") as config_file:
            toml.dump(config, config_file)

    @app_commands.command()
    @perms.exclusive()
    async def status(self: Self, interaction: discord.Interaction, status: discord.Status) -> None:
        """
        Sets the online status of the bot.

        Args:
            interaction (discord.Interaction): The Discord interaction.
            status (discord.Status): The new status to set.
        """
        config = toml.load(constants.DATA_DIR + "config.toml")
        activity_name = config["base"]["activity_type"]
        try:
            activity = discord.Activity(
                type=discord.ActivityType[activity_name], name=config["base"]["activity_name"]
            )
        except KeyError:
            activity = None

        # Check if valid status name was used
        if status is None:
            embed = discord.Embed(
                colour=constants.EmbedStatus.FAIL.value, description="That's not a valid status"
            )
            await interaction.response.send_message(embed=embed)
            return

        if activity:
            await self.bot.change_presence(status=status, activity=activity)
        else:
            await self.bot.change_presence(status=status)

        config["base"]["status"] = status.name
        async with aiofiles.open(constants.DATA_DIR + "config.toml", "w") as config_file:
            toml.dump(config, config_file)

    @app_commands.command()
    @perms.exclusive()
    async def activity(
        self: Self,
        interaction: discord.Interaction,
        activity_type: discord.ActivityType,
        *,
        name: str,
    ) -> None:
        """
        Sets the activity type and text of the bot.

        Args:
            interaction (discord.Interaction): The Discord interaction.
            activity_type (discord.ActivityType): The type of activity
                to set.
            name (str): The text of the activity.
        """
        config = toml.load(constants.DATA_DIR + "config.toml")
        activity = discord.Activity(
            type=activity_type, name=name, url="https://www.twitch.tv/yeet"
        )
        try:
            status = config["base"]["status"]
        except KeyError:
            status = None

        if activity_type is None:
            embed = discord.Embed(
                colour=constants.EmbedStatus.FAIL.value,
                description="That's not a valid activity type",
            )
            await interaction.response.send_message(embed=embed)
            return

        if status:
            await self.bot.change_presence(activity=activity, status=status)
        else:
            await self.bot.change_presence(activity=activity)

        config["base"]["activity_type"] = activity_type.name
        config["base"]["activity_name"] = name
        async with aiofiles.open(constants.DATA_DIR + "config.toml", "w") as config_file:
            toml.dump(config, config_file)


async def setup(bot: commands.Bot) -> None:
    """Load the Configuration cog."""
    await bot.add_cog(Configuration(bot))
