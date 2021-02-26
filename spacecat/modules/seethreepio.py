import discord
from discord.ext import commands
from discord_slash import cog_ext, SlashContext

from spacecat.helpers import perms


class Seethreepio(commands.Cog):
    """Random text response based features"""
    def __init__(self, bot):
        self.bot = bot

    @cog_ext.cog_slash()
    @perms.check()
    async def echo(self, ctx: SlashContext, *, message):
        """Repeats a given message"""
        await ctx.respond()
        await ctx.send(message)

    @cog_ext.cog_slash()
    @perms.check()
    async def flip(self, ctx: SlashContext, member: discord.Member=None):
        """Flips a table... Or a person"""
        if member == None:
            await ctx.send("(╯°□°）╯︵ ┻━┻")
            return

        if member.id != self.bot.user.id:
            await ctx.send("(╯°□°）╯︵ " + member.mention)
        else:
            await ctx.send("Bitch please. \n'(╯°□°）╯︵ "
                           + ctx.message.author.mention)

    @cog_ext.cog_slash()
    @perms.check()
    async def throw(self, ctx, member: discord.Member, *, item=None):
        if item is not None:
            await ctx.send("(∩⚆ᗝ⚆)⊃ --==(" + item + ")     "
                           + member.mention)
        else:
            if member.id != self.bot.user.id:
                await ctx.send("(∩⚆ᗝ⚆)⊃ --==(O)     " + member.mention)
            else:
                await ctx.send("Bitch please. \n'(∩⚆ᗝ⚆)⊃ --==(O)     "
                               + ctx.message.author.mention)

    @cog_ext.cog_slash()
    @perms.check()
    async def stealuserpic(self, ctx, user: discord.User):
        await ctx.send(user.avatar_url)


def setup(bot):
    bot.add_cog(Seethreepio(bot))
