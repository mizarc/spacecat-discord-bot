from discord.ext import commands
from discord.utils import get
import configparser

def setup():
    config['PermsPreset']['administrator'] = {}
    config['PermsPreset']['moderator'] = {}
    config['PermsPreset']['user'] = {}


def new(guild):
    config = configparser.ConfigParser()

    if not os.path.exists('servers/' + guild.id + '.ini'):
        config['PermsGroups'] = {}
        config['PermsUsers'] = {}

    config.read('config.ini')
    userperms = config['PermsPreset']['user']

    config.read('servers/' + guild.id + '.ini')
    config['PermsGroups'][guild.default_role] = userperms


def check():
    def predicate(ctx):
        config = configparser.ConfigParser()
        config.read('servers/' + guild.id + '.ini')
            
        if discord.Permissions.administrator in ctx.author.guild_permissions:
            return True

        for role in ctx.author.roles:
            roleid = role.id
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