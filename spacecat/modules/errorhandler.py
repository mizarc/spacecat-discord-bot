import discord
from discord.ext import commands

from helpers import settings


class ErrorHandler(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_command_error(self, ctx, error):
        if isinstance(error, commands.CommandNotFound):
            return

        if isinstance(error, commands.CheckFailure):
            embed = discord.Embed(colour=settings.embed_type('warn'), description="You don't have permission to use that command")
            await ctx.send(embed=embed)
            return

        if isinstance(error, commands.CommandInvokeError):
            print(error)
            return

def setup(bot):
    bot.add_cog(ErrorHandler(bot))