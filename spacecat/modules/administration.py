"""
This module provides a cog for managing server wide settings.

Anything pertaining to general server wide configurations that can be
modified by server administrators should go here. Notable examples
include the ability to change timezone for time based functionality.
"""

from __future__ import annotations

import sqlite3
from typing import Self

import discord
from discord import app_commands
from discord.ext import commands

from spacecat.helpers import constants, permissions


class ServerSettings:
    """Represents server wide settings for the bot."""

    def __init__(self: ServerSettings, id_: int, timezone: str) -> None:
        """
        Initialises an instance of ServerSettings.

        Args:
        id_ (int): The ID of the server.
        timezone (str): The timezone of the server.
        """
        self.id = id_
        self.timezone = timezone


class ServerSettingsRepository:
    """
    Represents a repository for server wide settings.

    This class provides methods for creating, reading, updating, and
    deleting server settings.
    """

    def __init__(self: ServerSettingsRepository, database: sqlite3.Connection) -> None:
        """
        Initializes an instance of the ServerSettingsRepository class.

        Args:
            database (sqlite3.Connection): The database connection.
        """
        self.db = database
        cursor = self.db.cursor()
        cursor.execute("PRAGMA foreign_keys = ON")
        cursor.execute(
            "CREATE TABLE IF NOT EXISTS server_settings (id INTEGER PRIMARY KEY, timezone TEXT)"
        )
        self.db.commit()

    def get_all(self: Self) -> list[ServerSettings]:
        """Get list of all reminders."""
        results = self.db.cursor().execute("SELECT * FROM server_settings").fetchall()
        return [ServerSettings(result[0], result[1]) for result in results]

    def get_by_guild(self: Self, guild_id: int) -> ServerSettings:
        """
        Retrieves a `ServerSettings` object based on the provided guild.

        Args:
            guild_id (int): The ID of the guild.

        Returns:
            ServerSettings: The `ServerSettings` object retrieved from
                the database.
        """
        result = (
            self.db.cursor()
            .execute("SELECT * FROM server_settings WHERE id=?", (guild_id,))
            .fetchone()
        )
        return ServerSettings(result[0], result[1])

    def add(self: Self, server_settings: ServerSettings) -> None:
        """
        Adds a new server settings record to the database.

        Args:
            server_settings (ServerSettings): The server settings to be
                added.
        """
        cursor = self.db.cursor()
        values = (str(server_settings.id), server_settings.timezone)
        cursor.execute("INSERT INTO server_settings VALUES (?, ?)", values)
        self.db.commit()

    def update(self: Self, server_settings: ServerSettings) -> None:
        """
        Updates the timezone of a server in the server_settings table.

        Args:
            server_settings (ServerSettings): The server settings object
                containing the new timezone.
        """
        cursor = self.db.cursor()
        values = (server_settings.timezone, str(server_settings.id))
        cursor.execute("UPDATE server_settings SET timezone=? WHERE id=?", values)
        self.db.commit()

    def remove(self: Self, server_settings: ServerSettings) -> None:
        """
        Remove a server's settings from the database.

        Args:
            server_settings (ServerSettings): The server setting to
                remove.
        """
        cursor = self.db.cursor()
        values = (server_settings.id,)
        cursor.execute("DELETE FROM server_settings WHERE id=?", values)
        self.db.commit()


class Administration(commands.Cog):
    """Modify server wide settings."""

    def __init__(self: Administration, bot: commands.Bot) -> None:
        """
        Initializes an instance of the Administration class.

        Args:
            bot (commands.Bot): The Discord bot instance.
        """
        self.bot = bot
        self.database = sqlite3.connect(constants.DATA_DIR + "spacecat.db")
        self.server_settings = ServerSettingsRepository(self.database)

    @commands.Cog.listener()
    async def on_ready(self: Self) -> None:
        """Listener that sets up the server settings on launch."""
        db = sqlite3.connect(constants.DATA_DIR + "spacecat.db")
        cursor = db.cursor()

        # Create tables if they don't exist
        cursor.execute(
            "CREATE TABLE IF NOT EXISTS command_alias"
            "(server_id INTEGER, alias TEXT, command TEXT)"
        )

        # Compare bot servers and database servers to check if the bot was
        # added to servers while the bot was offline
        cursor.execute("SELECT id FROM server_settings")
        servers = self.bot.guilds
        server_ids = {server.id for server in servers}
        db_servers = cursor.fetchall()
        db_server_ids = {server for (server,) in db_servers}
        missing_servers = list(server_ids - db_server_ids)

        # Add missing servers to database
        for server in missing_servers:
            await self._add_server_entry(server)

        db.commit()
        db.close()

    @commands.Cog.listener()
    async def on_guild_join(self: Self, guild: discord.Guild) -> None:
        """
        Listener that adds server settings for new guild additions.

        Parameters:
            self (Self): The instance of the class.
            guild (discord.Guild): The guild that the bot has joined.

        Returns:
            None
        """
        await self._add_server_entry(guild.id)

    @app_commands.command()
    @permissions.check()
    async def timezone(self: Self, interaction: discord.Interaction, region: str) -> None:
        """
        Sets the timezone for the server.

        Parameters:
            interaction (discord.Interaction): The user interaction.
            region (str): The region for the timezone.
        """
        if interaction.guild is None:
            await interaction.response.send_message(
                embed=discord.Embed(
                    colour=constants.EmbedStatus.YES.value,
                    description=f"Timezone has been set to {region}. "
                    "This will apply to time based commands.",
                )
            )
            return

        server_settings = self.server_settings.get_by_guild(interaction.guild.id)
        server_settings.timezone = region
        self.server_settings.update(server_settings)
        await interaction.response.send_message(
            embed=discord.Embed(
                colour=constants.EmbedStatus.YES.value,
                description=f"Timezone has been set to {region}. "
                "This will apply to time based commands.",
            )
        )

    async def _add_server_entry(self: Self, guild: int) -> None:
        db = sqlite3.connect(constants.DATA_DIR + "spacecat.db")
        cursor = db.cursor()
        value = (guild, None)
        cursor.execute("INSERT OR IGNORE INTO server_settings VALUES (?,?)", value)
        db.commit()
        db.close()


async def setup(bot: commands.Bot) -> None:
    """
    Set up the Administration cog for the bot.

    Args:
        bot (commands.Bot): The Discord bot instance.
    """
    await bot.add_cog(Administration(bot))
