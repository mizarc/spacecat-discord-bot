import discord
from discord.ext import commands


class Seethreepio:
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def flip(self, ctx, member: discord.Member):
        if member.id != self.bot.user.id:
            ctx.send('(╯°□°）╯︵ ' + member.mention)
        else:
            ctx.send("Bitch please. \n'(╯°□°）╯︵ " + ctx.message.author.mention)


def setup(bot):
    bot.add_cog(Seethreepio(bot))
