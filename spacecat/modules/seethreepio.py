import discord
from discord.ext import commands
from discord_slash import cog_ext, SlashContext

from spacecat.helpers import perms

guild_ids = [287483491032104962]


class Seethreepio(commands.Cog):
    """Random text response based features"""
    def __init__(self, bot):
        self.bot = bot

    @cog_ext.cog_slash(name='echo', guild_ids=guild_ids)
    @perms.check()
    async def echo(self, ctx: SlashContext, *, message):
        """Repeats a given message"""
        await ctx.respond()
        await ctx.send(message)

    @commands.command()
    @perms.check()
    async def flip(self, ctx, member: discord.Member):
        if member.id != self.bot.user.id:
            await ctx.send("(╯°□°）╯︵ " + member.mention)
        else:
            await ctx.send("Bitch please. \n'(╯°□°）╯︵ "
                           + ctx.message.author.mention)

    @commands.command()
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

    @commands.command()
    @perms.check()
    async def stealuserpic(self, ctx, user: discord.User):
        await ctx.send(user.avatar_url)


def setup(bot):
    bot.add_cog(Seethreepio(bot))
