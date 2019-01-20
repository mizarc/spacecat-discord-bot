import discord
from discord.ext import commands


class Seethreepio:
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def flip(self, ctx, member: discord.Member):
        if member.id != self.bot.user.id:
            await ctx.send("(╯°□°）╯︵ " + member.mention)
        else:
            await ctx.send("Bitch please. \n'(╯°□°）╯︵ "
                           + ctx.message.author.mention)

    @commands.command()
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


def setup(bot):
    bot.add_cog(Seethreepio(bot))
