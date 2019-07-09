import discord
from discord.ext import commands


class TrashPanda(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def echo(self, ctx, channel, *, message):
        ch = self.bot.get_channel(int(channel))
        await ch.send(message)

    @commands.command()
    async def test(self, ctx):
        await ctx.send(ctx.guild.default_role.id)


def setup(bot):
    bot.add_cog(TrashPanda(bot))