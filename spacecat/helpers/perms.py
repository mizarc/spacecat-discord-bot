"""
This helper module provides functions for managing permissions.

Permissions are handled on a role and user basis. Decorators can be
utilised in order to check what kind of permission needs to be checked
before performing said command, else the user is alerted to their lack
of permissions.

The `check` decorator is a user facing permission check, while
`exclusive` is a bot administrator check. Use accordingly.
"""

import re
import sqlite3
from collections.abc import Callable
from pathlib import Path

import discord
import toml
from discord.ext import commands

from spacecat.helpers import constants


def init_database() -> None:
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


def new(guild: discord.Guild) -> None:
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


def check() -> Callable:
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
        permissions = {"*", "." + ".".join(command_values)}
        for i in range(len(command_values) - 1):
            result = ".".join(command_values[: i + 1]) + ".*"
            permissions.add(result)

        regex_query = re.compile("Preset.[a-zA-Z0-9]+")

        # Query database to allow if user has the required permission
        db = sqlite3.connect(constants.DATA_DIR + "spacecat.db")
        db.row_factory = lambda _, row: row[0]
        cursor = db.cursor()
        query = (interaction.guild.id, interaction.user.id)
        cursor.execute(
            "SELECT permission FROM user_permission WHERE server_id=? AND user_id=?", query
        )
        user_results = cursor.fetchall()
        presets = list(filter(regex_query.match, user_results))
        if set(user_results).intersection(permissions):
            return True

        # Query database to allow if any group that the user is assigned
        # to has the required permission
        for group in interaction.user.roles:
            query = (interaction.guild.id, group.id)
            cursor.execute(
                "SELECT permission FROM group_permission WHERE server_id=? AND group_id=?",
                query,
            )
            group_results = cursor.fetchall()
            presets = presets + list(filter(regex_query.match, group_results))
            if set(group_results).intersection(permissions):
                return True

            # Execute recurring parent check
            parent_query = (interaction.guild.id, query[1])
            parent_check, presets = _parent_perms(
                interaction, cursor, parent_query, permissions, presets
            )
            if parent_check:
                return True

        # Query permission presets from config that the user or group may have
        config = toml.load(constants.DATA_DIR + "config.toml")
        for preset in presets:
            comparison = list(set(config["permissions"][preset[7:]]).intersection(permissions))
            if comparison:
                return True

        # Query config's default permission list
        query = (interaction.guild.id,)
        cursor.execute("SELECT advanced_permission FROM server_settings WHERE server_id=?", query)
        advanced = cursor.fetchone()
        if advanced == 0:
            comparison = set(config["permissions"]["default"]).intersection(permissions)
            if comparison:
                return True
        return False

    return discord.app_commands.check(predicate)


def exclusive() -> Callable:
    """Checks if the user is a bot administrator."""

    def predicate(ctx: commands.Context) -> bool:
        # Open global config file
        config = toml.load(constants.DATA_DIR + "config.toml")

        # If user is the bot administrator
        if ctx.author.id in config["base"]["adminuser"]:
            return True
        return False

    return commands.check(predicate)


def _parent_perms(
    interaction: discord.Interaction,
    cursor: sqlite3.Cursor,
    parent_query: tuple,
    checks: set,
    presets: list,
) -> tuple:
    """
    Recursively checks all parent permissions.

    These checks continue all the way up until either all dead ends have
    been reached, or the appropriate permission has been found.
    """
    # Check if group has parents
    cursor.execute(
        "SELECT parent_id FROM group_parent WHERE server_id=? AND child_id=?", parent_query
    )
    parents = cursor.fetchall()

    # Check parent groups for permission
    for parent in parents:
        if interaction.guild is None:
            return False, presets

        perm_query = (interaction.guild.id, parent)
        cursor.execute(
            "SELECT permission FROM group_permission WHERE server_id=? AND group_id=?",
            perm_query,
        )
        results = cursor.fetchall()
        regex_query = re.compile("Preset.[a-zA-Z0-9]+")
        presets = presets + list(filter(regex_query.match, results))
        if set(results).intersection(checks):
            return True, presets

        # Check next parent level
        new_parent_query = (interaction.guild.id, parent)
        parent_check, presets = _parent_perms(
            interaction, cursor, new_parent_query, checks, presets
        )
        if parent_check:
            return True, presets
    return False, presets
