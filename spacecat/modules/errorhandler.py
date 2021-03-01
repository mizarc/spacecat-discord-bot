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
            embed = discord.Embed(
                colour=constants.EmbedStatus.FAIL.value,
                description="You don't have permission to use that command")
            await ctx.send(embed=embed)
            return

        if isinstance(error, discord.Forbidden):
            embed = discord.Embed(
                colour=constants.EmbedStatus.FAIL.value,
                description="I don't have the necessary server permission"
                "to execute that. Contact the server administrator.")
            await ctx.send(embed=embed)
            return


def setup(bot):
    bot.add_cog(ErrorHandler(bot))
