from discord.ext import commands
from discord.utils import get
import configparser
import os
import discord

def setup():
    config = configparser.ConfigParser()

    config['PermsPreset']['administrator'] = {}
    config['PermsPreset']['moderator'] = {}
    config['PermsPreset']['user'] = {}

    with open('config.ini', 'w') as file:
            config.write(file)

def new(guild):
    if not os.path.exists('servers/' + str(guild.id) + '.ini'):
        config = configparser.ConfigParser()
        config.read('config.ini')
        userperms = config['PermsPreset']['user']

        config = configparser.ConfigParser()

        config['PermsGroups'] = {}
        config['PermsGroups'][str(guild.default_role.id)] = userperms
        
        config['PermsUsers'] = {}

        with open('servers/' + str(guild.id) + '.ini', 'w') as file:
                config.write(file)

def check():
    def predicate(ctx):
        config = configparser.ConfigParser()
        config.read('servers/' + str(ctx.guild.id) + '.ini')
        
        if ctx.author.guild_permissions.administrator:
            return True

        try:
            userperms = config['UserPerms'][str(ctx.author.id)].split(',')
            if ctx.command.name in userperms:
                return True
        except KeyError:
            pass

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
        config = configparser.ConfigParser()
        config.read('config.ini')

        if ctx.author.id == int(config['Base']['adminuser']):
            return True

    return commands.check(predicate)