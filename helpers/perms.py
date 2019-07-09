from discord.ext import commands
from discord.utils import get
import configparser
import os

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
        config.read('servers/' + str(guild.id) + '.ini')
            
        if discord.Permissions.administrator in ctx.author.guild_permissions:
            return True

        for role in ctx.author.roles:
            roleid = str(role.id)
            permroles = ['Perms'][method.__name__].split(',')
            if role in permroles:
                return True
    
    return commands.check(predicate)

        
def exclusive():
    def predicate(ctx):
        config = configparser.ConfigParser()
        config.read('config.ini')

        if ctx.author.id == int(config['Base']['adminuser']):
            return True

    return commands.check(predicate)