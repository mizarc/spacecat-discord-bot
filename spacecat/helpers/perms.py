import configparser
import os
import sqlite3

import discord
from discord.ext import commands
from discord.utils import get
import toml

from spacecat.helpers import settings


def new(guild):
    # Check if server doesn't have a config file
    if not os.path.exists('servers/' + str(guild.id) + '.toml'):
        # Get default perms from global config
        config = toml.load(settings.data + 'config.toml')
        userperms = config['PermsPreset']['user']

        # Assign @everyone role the global user perms
        config = toml.load(settings.data + 'config.toml')
        config['PermsGroups'] = {}
        config['PermsGroups'][str(guild.default_role.id)] = userperms
        config['PermsUsers'] = {}


def check():
    def predicate(ctx):
        module = ctx.command.cog.qualified_name
        command = ctx.command.qualified_name
        command_values = command.split(' ')

        # Allow if user is a server administrator
        if ctx.author.guild_permissions.administrator:
            return True

        # Add queries for both config and database by including the
        # global wildcard, module wildcard, command wildcard,
        # and the command on its own
        database_queries = [
            (ctx.guild.id, ctx.author.id, "*"),
            (ctx.guild.id, ctx.author.id, f"{module}.*")]
        config_queries = ['*', f'{module}.*']
        perm = ''
        for index, command in enumerate(command_values):
            if index == 0:
                perm = command
            else:
                perm = f"{perm}.{command}"
            database_queries.append(
                (ctx.guild.id, ctx.author.id, f"{module}.{perm}.*"))
            config_queries.append(f'{module}.{perm}.*')
        database_queries.append(
            (ctx.guild.id, ctx.author.id, f"{module}.{perm}"))
        config_queries.append(f'{module}.{perm}')
        
        # Query database for user permissions
        db = sqlite3.connect(settings.data + 'spacecat.db')
        cursor = db.cursor()
        for query in database_queries:
            cursor.execute(
                'SELECT permission FROM user_permission '
                'WHERE server_id=? AND user_id=? AND permission=?', query)
            check = cursor.fetchall()
            if check:
                return True
        
        # Convert query from user ID to every group ID that a user has
        group_queries = []
        for role in ctx.author.roles:
            for index, query in enumerate(database_queries):
                query_conversion = list(query)
                query_conversion[1] = role.id
                group_queries.append(query_conversion)

        # Execute all group perm queries
        for query in group_queries:
            cursor.execute(
                'SELECT permission FROM group_permission '
                'WHERE server_id=? AND group_id=? AND permission=?', query)
            check = cursor.fetchall()
            if check:
                return True

            # Execute recurring parent check
            parent_query = (ctx.guild.id, query[1])
            parent_check = parent_perms(ctx, cursor, parent_query, query[2])
            if parent_check:
                return True

        # Check config's default permission list
        query = (ctx.guild.id,)
        cursor.execute(
            'SELECT advanced_permission FROM server_settings '
            'WHERE server_id=?', query)
        advanced = cursor.fetchone()
        if advanced[0] == 0:
            config = toml.load(settings.data + 'config.toml')
            comparison = list(
                set(config['permissions']['default'])
                .intersection(set(config_queries)))
            if comparison:
                return True


    def parent_perms(ctx, cursor, parent_query, permission):
        """
        Recursively checks all parents until either all dead ends have
        been reached, or the appropriate permission has been found.
        """
        # Check if group has parents
        cursor.execute(
            'SELECT parent_id FROM group_parent '
            'WHERE server_id=? AND child_id=?', parent_query)
        parents = cursor.fetchall()

        if parents:
            # Check parent groups for permission
            for parent in parents:
                perm_query = (
                    ctx.guild.id, parent[0], permission)
                cursor.execute(
                    'SELECT permission FROM group_permission '
                    'WHERE server_id=? AND group_id=? AND permission=?',
                    perm_query)
                check = cursor.fetchall()
                if check:
                    return True

                # Check next parent level
                new_parent_query = (ctx.guild.id, parent[0])
                parent_check = parent_perms(
                    ctx, cursor, new_parent_query, permission)
                if parent_check:
                    return True

    return commands.check(predicate)

        
def exclusive():
    def predicate(ctx):
        # Open global config file
        config = toml.load(settings.data + 'config.toml')

        # If user is the bot administrator
        if ctx.author.id in config['base']['adminuser']:
            return True

    return commands.check(predicate)