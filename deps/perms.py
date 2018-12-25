from discord.ext import commands
from discord.utils import get


def admin():
    def predicate(ctx):
        admin_role = "Meme Council"
        roles = ctx.author.roles
        return get(roles, name=admin_role)
    return commands.check(predicate)


def mod():
    def predicate(ctx):
        mod_role = "Salt Squad"
        roles = ctx.author.roles.name
        return get(roles, name=mod_role)
    return commands.check(predicate)
