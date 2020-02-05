import configparser
import os
import sqlite3

import discord
from discord.ext import commands
from discord.utils import get
import toml

from helpers import settings


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
        # If user is the server administrator, always allow
        command_parents = ctx.command.qualified_name.split(' ')

        if ctx.author.guild_permissions.administrator:
            return True

        # Open server's database file
        db = sqlite3.connect(settings.data + 'spacecat.db')
        cursor = db.cursor()

        # Check if specific user has a permission in server
        queries = []
        queries.append((ctx.guild.id, ctx.author.id, "*"))
        queries.append((ctx.guild.id, ctx.author.id, f"{ctx.command.cog.qualified_name}.*"))

        # Check subcommand parents for permission
        perm = ''
        for index, command in enumerate(command_parents):
            if index == 0:
                perm = command
            else:
                perm = f"{perm}.{command}"
            queries.append((ctx.guild.id, ctx.author.id, f"{ctx.command.cog.qualified_name}.{perm}.*"))
        queries.append((ctx.guild.id, ctx.author.id, f"{ctx.command.cog.qualified_name}.{perm}%"))
        
        # Execute user perm queries
        for query in queries:
            cursor.execute(
                'SELECT permission FROM user_permission WHERE server_id=? AND user_id=? AND permission LIKE ?', query)
            check = cursor.fetchall()
            if check:
                return True

        # Convert query from user ID to every group ID that a user has
        group_queries = []
        for role in ctx.author.roles:
            for index, query in enumerate(queries):
                query_conversion = list(query)
                query_conversion[1] = role.id
                group_queries.append(query_conversion)

        # Execute all group perm queries
        for query in group_queries:
            cursor.execute(
                'SELECT permission FROM group_permission WHERE server_id=? AND group_id=? AND permission LIKE ?', query)
            check = cursor.fetchall()
            query = (ctx.guild.id, role.id)
            parent_check = parent_perms(ctx, cursor, query)
            if check or parent_check:
                return True

    def parent_perms(ctx, cursor, query):
        # Check if group has parents
        cursor.execute(
                'SELECT parent_id FROM group_parent WHERE server_id=? AND child_id=?', query)
        parents = cursor.fetchall()

        # Check parent groups for permission
        if parents:
            for parent in parents:
                query = (ctx.guild.id, parent[0], f"{ctx.command.cog.qualified_name}.{ctx.command.name}")
                cursor.execute(
                    'SELECT permission FROM group_permission WHERE server_id=? AND group_id=? AND permission LIKE ?', query)
                check = cursor.fetchall()
                if check:
                    return True

                query = (ctx.guild.id, parent[0])
                parent_check = parent_perms(ctx, cursor, f"{ctx.command.cog.qualified_name}.{ctx.command.name}")
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