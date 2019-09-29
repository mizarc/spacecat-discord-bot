from discord.ext import commands
from discord.utils import get
import configparser
import os
import discord

def setup():
    # Create blank permission headers
    config = configparser.ConfigParser()
    config['PermsPreset']['administrator'] = {}
    config['PermsPreset']['moderator'] = {}
    config['PermsPreset']['user'] = {}

    # Write to global config file
    with open('config.ini', 'w') as file:
            config.write(file)

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
        # Open server's config file
        config = configparser.ConfigParser()
        config.read('servers/' + str(ctx.guild.id) + '.ini')
        
        # If user is the bot administrator, always allow
        if ctx.author.guild_permissions.administrator:
            return True

        # Check if specific user has a permission
        try:
            userperms = config['UserPerms'][str(ctx.author.id)].split(',')
            if ctx.command.name in userperms:
                return True
        except KeyError:
            pass

        # Check if user's group has a permission
        for role in ctx.author.roles:
            try:
                groupperms = config['GroupPerms'][str(role.id)].split(',')
                if ctx.command.name in groupperms:
                    return True
            except KeyError:
                pass
        

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