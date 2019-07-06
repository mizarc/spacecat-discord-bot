from discord.ext import commands
from discord.utils import get
import configparser


config = configparser.ConfigParser()
config.read('config.ini')
roles = ['admin', 'mod']


def init():
    for x in roles:
        try:
            # Read Config File for API Key
            perm = config['Perms'][x]
            return perm
        except KeyError:
            config['Perms'] = {}
            config['Perms'][x] = ''
    with open('config.ini', 'w') as file:
        config.write(file)


def admin():
    def predicate(ctx):
        role = "admin"
        admin_roles = config['Perms'][role].split(',')
        for x in admin_roles:
            roles = ctx.author.roles.name
            if get(roles, name=admin_roles):
                return True
    return commands.check(predicate)


def mod():
    def predicate(ctx):
        role = "mod"
        mod_roles = config['Perms'][role].split(',')
        for x in mod_roles:
            roles = ctx.author.roles.name
            if get(roles, name=mod_roles):
                return True
    return commands.check(predicate)
