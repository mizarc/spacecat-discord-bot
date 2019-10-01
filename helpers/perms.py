import configparser
import os
import sqlite3

import discord
from discord.ext import commands
from discord.utils import get

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
    if not os.path.exists('servers/' + str(guild.id) + '.ini'):
        # Get default perms from global config
        config = configparser.ConfigParser()
        config.read('config.ini')
        userperms = config['PermsPreset']['user']

        # Assign @everyone role the global user perms
        config = configparser.ConfigParser()
        config['PermsGroups'] = {}
        config['PermsGroups'][str(guild.default_role.id)] = userperms
        config['PermsUsers'] = {}

        # Write to server config file
        with open('servers/' + str(guild.id) + '.ini', 'w') as file:
                config.write(file)

def check():
    def predicate(ctx):
        # If user is the server administrator, always allow
        if ctx.author.guild_permissions.administrator:
            return True

        # Open server's database file
        db = sqlite3.connect('spacecat.db')
        cursor = db.cursor()

        # Open server's config file
        config = configparser.ConfigParser()
        config.read('servers/' + str(ctx.guild.id) + '.ini')

        # Check if specific user has a permission in server
        user_perms = cursor.execute(
            'SELECT perm FROM user_permissions WHERE serverid=' + str(ctx.guild.id) + ' AND userid=' + str(ctx.author.id))
        for perm in user_perms:
                if ctx.command.name == perm[0]:
                    return True

        # Check if user's group has a permission in server
        for role in ctx.author.roles:
            group_perms = cursor.execute(
                'SELECT perm FROM group_permissions WHERE serverid=' + str(ctx.guild.id) + ' AND groupid=' + str(role.id))
            for perm in group_perms:
                if ctx.command.name == perm[0]:    
                    return True
        
    return commands.check(predicate)

        
def exclusive():
    def predicate(ctx):
        # Open global config file
        config = configparser.ConfigParser()
        config.read('config.ini')

        # If user is the bot administrator
        if ctx.author.id == int(config['Base']['adminuser']):
            return True

    return commands.check(predicate)