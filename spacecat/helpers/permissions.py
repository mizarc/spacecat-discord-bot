"""
This helper module provides functions for managing permissions.

Permissions are handled on a role and user basis. Decorators can be
utilised in order to check what kind of permission needs to be checked
before performing said command, else the user is alerted to their lack
of permissions.

The `check` decorator is a user facing permission check, while
`exclusive` is a bot administrator check. Use accordingly.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Self

import discord
import toml
from discord.ext import commands

from spacecat.helpers import constants

if TYPE_CHECKING:
    from spacecat.spacecat import SpaceCat


class Permissions:
    def __init__(self: Permissions, bot: SpaceCat) -> None:
        self.bot = bot

    def init_database(self: Self) -> None:
        """
        Initializes the permissions databases.

        This function should be run on bot start in order to ensure that
        the tables that hold permissions are created if they do not exist.
        """
        db = sqlite3.connect(constants.DATA_DIR + "spacecat.db")
        db.execute(
            "CREATE TABLE IF NOT EXISTS user_permission "
            "(server_id INTEGER, user_id INTEGER, permission TEXT)"
        )
        db.execute(
            "CREATE TABLE IF NOT EXISTS group_permission "
            "(server_id INTEGER, group_id INTEGER, permission TEXT)"
        )
        db.commit()
        db.close()

    def new(self: Self, guild: discord.Guild) -> None:
        """
        Initializes a new server configuration file for the given guild.

        Parameters:
            guild (discord.Guild): The guild for which to create the
                configuration file.
        """
        # Check if server doesn't have a config file
        if not Path("servers/" + str(guild.id) + ".toml").exists:
            # Get default perms from global config
            config = toml.load(constants.DATA_DIR + "config.toml")
            userperms = config["PermsPreset"]["user"]

            # Assign @everyone role the global user perms
            config = toml.load(constants.DATA_DIR + "config.toml")
            config["PermsGroups"] = {}
            config["PermsGroups"][str(guild.default_role.id)] = userperms
            config["PermsUsers"] = {}

    def check(self: Self) -> Callable:
        """
        Check if user has permission to use the command.

        Server administrators are automatically granted permission. Otherwise, users
        are checked based on whether it is a globally granted permission, or
        whether it is overwritten on an individual server basis.
        """

        def predicate(interaction: discord.Interaction) -> bool:
            # You've put this decorator on the wrong function if this check triggers
            if interaction.command is None:
                return False

            # Check if command is being run outside of a guild or command is invalid
            if not isinstance(interaction.user, discord.Member) or interaction.guild is None:
                return False

            # Allow if user is a server administrator
            if interaction.user.guild_permissions.administrator:
                return True

            # Grab valid permissions from the command using its subcommand tree.
            command_values = interaction.command.qualified_name.split(" ")
            permissions = ["*", ".".join(command_values)]
            for i in range(len(command_values) - 1):
                result = ".".join(command_values[: i + 1]) + ".*"
                permissions.append(result)

            # Query database to allow if user has the required permission
            db = sqlite3.connect(constants.DATA_DIR + "spacecat.db")
            db.row_factory = lambda _, row: row[0]
            cursor = db.cursor()

            # Allow if permission is granted to the user or role that the user has
            user_result = self._user_permission_check(
                interaction.guild, interaction.user, permissions, cursor
            )
            role_result = self._role_permission_check(
                interaction.guild, interaction.user, permissions, cursor
            )
            default_result = self._default_permission_check(interaction.guild, permissions, cursor)
            if user_result or role_result or default_result:
                return True

            return False

        return discord.app_commands.check(predicate)

    def exclusive(self: Self) -> Callable:
        """Checks if the user is a bot administrator."""

        def predicate(ctx: commands.Context) -> bool:
            # Open global config file
            config = toml.load(constants.DATA_DIR + "config.toml")

            # If user is the bot administrator
            if ctx.author.id in config["base"]["adminuser"]:
                return True
            return False

        return commands.check(predicate)

    def _user_permission_check(
        self: Self,
        guild: discord.Guild,
        user: discord.Member,
        permissions: list[str],
        cursor: sqlite3.Cursor,
    ) -> bool:
        """
        Checks permission to use command based on user.

        The user themself is checked to see if they have permission to use
        the command.

        Args:
            guild (discord.Guild): The guild to check for default permissions.
            user (discord.Member): The user to check.
            permissions (list[str]): The permissions to check.
            cursor (sqlite3.Cursor): The cursor to execute the SQL query.

        Returns:
            bool: True if user has permission.
        """
        query = (guild.id, user.id)
        cursor.execute(
            "SELECT permission FROM user_permission WHERE server_id=? AND user_id=?", query
        )
        user_results = cursor.fetchall()
        if set(user_results).intersection(permissions):
            return True
        return False

    def _role_permission_check(
        self: Self,
        guild: discord.Guild,
        user: discord.Member,
        permissions: list[str],
        cursor: sqlite3.Cursor,
    ) -> bool:
        """
        Checks permission to use command based on user's assigned roles.

        Each of the user's assigned server roles are checked to see if any
        of them have the required permission to use the command.

        Args:
            guild (discord.Guild): The guild to check for default permissions.
            user (discord.Member): The user to check.
            permissions (list[str]): The permissions to check.
            cursor (sqlite3.Cursor): The cursor to execute the SQL query.

        Returns:
            bool: True if user has permission.
        """
        for group in user.roles:
            query = (guild.id, group.id)
            cursor.execute(
                "SELECT permission FROM group_permission WHERE server_id=? AND group_id=?",
                query,
            )
            group_results = cursor.fetchall()
            if set(group_results).intersection(permissions):
                return True
        return False

    def _default_permission_check(
        self: Self,
        guild: discord.Guild,
        permissions: list[str],
        cursor: sqlite3.Cursor,
    ) -> bool:
        """
        Checks permission to use command if default permissions are enabled.

        If the server that is being checked has default permissions enabled,
        it checks to see if the command that the player is trying to use is
        part of the default commands list.

        Args:
            guild (discord.Guild): The guild to check for default permissions.
            permissions (list[str]): The permissions to check.
            cursor (sqlite3.Cursor): The cursor to execute the SQL query.

        Returns:
            bool: True if user has permission.
        """
        query = (guild.id,)
        cursor.execute(
            "SELECT disable_default_permissions FROM server_settings WHERE server_id=?", query
        )
        default_permissions = cursor.fetchone()
        if default_permissions == 0:
            config = self.bot.instance.get_config()
            comparison = set(config["base"]["default_permissions"]).intersection(permissions)
            if comparison:
                return True
        return False
