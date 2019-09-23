import discord
from discord.ext import commands
import helpers.perms as perms

class Seethreepio(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

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
    async def stealuserpic(self, ctx, user: discord.User):
        await ctx.send(user.avatar_url)


def setup(bot):
    bot.add_cog(Seethreepio(bot))
