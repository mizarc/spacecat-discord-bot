import configparser
import os
import sqlite3

import discord
from discord.ext import commands
from discord.utils import get
import toml

def setup():
    # Open server's database file
    db = sqlite3.connect('spacecat.db')
    cursor = db.cursor()

    # Create group permission table
    cursor.execute('''CREATE TABLE group_permissions
        (serverid integer, groupid integer, perm text)''')

    # Create user permission table
    cursor.execute('''CREATE TABLE user_permissions
        (serverid integer, userid integer, perm text)''')

    # Create group parent table
    cursor.execute('''CREATE TABLE group_parents
        (serverid integer, child_group, parent_group)''')

    # Save and exit
    db.commit()
    db.close()

def new(guild):
    # Check if server doesn't have a config file
    if not os.path.exists('servers/' + str(guild.id) + '.toml'):
        # Get default perms from global config
        config = toml.load('config.toml')
        userperms = config['PermsPreset']['user']

        # Assign @everyone role the global user perms
        config = toml.load('config.toml')
        config['PermsGroups'] = {}
        config['PermsGroups'][str(guild.default_role.id)] = userperms
        config['PermsUsers'] = {}

def check():
    def predicate(ctx):
        # If user is the server administrator, always allow
        if ctx.author.guild_permissions.administrator:
            return True

        # Open server's database file
        db = sqlite3.connect('spacecat.db')
        cursor = db.cursor()

        # Check if specific user has a permission in server
        query = (ctx.guild.id, ctx.author.id, f"{ctx.command.cog.qualified_name}.{ctx.command.name}")
        cursor.execute(
            'SELECT perm FROM user_permissions WHERE serverid=? AND userid=? AND perm=?', query)
        check = cursor.fetchall()
        if check:
            return True

        # Check if user's group has a permission in server
        for role in ctx.author.roles:
            query = (ctx.guild.id, role.id, f"{ctx.command.cog.qualified_name}.{ctx.command.name}")
            cursor.execute(
                'SELECT perm FROM group_permissions WHERE serverid=? AND groupid=? AND perm=?', query)
            check = cursor.fetchall()

            query = (ctx.guild.id, role.id)
            parent_check = parent_perms(ctx, cursor, query)

            if check or parent_check:
                return True

    def parent_perms(ctx, cursor, query):
        # Check if group has parents
        cursor.execute(
                'SELECT parent_group FROM group_parents WHERE serverid=? AND child_group=?', query)
        parents = cursor.fetchall()

        # Check parent groups for permission
        if parents:
            for parent in parents:
                query = (ctx.guild.id, parent[0], f"{ctx.command.cog.qualified_name}.{ctx.command.name}")
                cursor.execute(
                    'SELECT perm FROM group_permissions WHERE serverid=? AND groupid=? AND perm=?', query)
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
        config = toml.load('config.toml')

        # If user is the bot administrator
        if ctx.author.id == int(config['base']['adminuser']):
            return True

    return commands.check(predicate)