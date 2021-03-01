import discord
from discord.ext import commands
from discord_slash import error as dserror

from spacecat.helpers import constants


class ErrorHandler(commands.Cog):
    """Outputs appropriate messages on errors"""
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_slash_command_error(self, ctx, error):
        if isinstance(error, dserror.CheckFailure):
            await ctx.send_hidden(f"**Error:** You don't have permission to use **{ctx.name}**")
            return

        if isinstance(error, discord.Forbidden):
            await ctx.send_hidden(f"**Error:** I don't have the necessary server permission"
                f" to execute **{ctx.name}**. Contact the server administrator for assistance.")
            return


def setup(bot):
    bot.add_cog(ErrorHandler(bot))
