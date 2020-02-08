import discord
from discord.ext import commands

from spacecat.helpers import settings


class ErrorHandler(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_command_error(self, ctx, error):
        if isinstance(error, commands.CommandNotFound):
            return

        if isinstance(error, commands.CheckFailure):
            embed = discord.Embed(
                colour=settings.embed_type('warn'),
                description="You don't have permission to use that command")
            await ctx.send(embed=embed)
            return

        if isinstance(error, commands.BotMissingPermissions):
            embed = discord.Embed(
                colour=settings.embed_type('warn'),
                description="I don't have the necessary server permission"
                "to execute that. Contact the server administrator.")
            await ctx.send(embed=embed)
            return

        if isinstance(error, commands.MissingRequiredArgument):
            embed = discord.Embed(
                colour=settings.embed_type('warn'),
                description="Missing Arguments. "
                f"Type `{ctx.prefix}help {ctx.command}` for more info")
            await ctx.send(embed=embed)
            return

        if isinstance(error, commands.BadArgument):
            embed = discord.Embed(
                colour=settings.embed_type('warn'),
                description="Invalid arguments provided. "
                f"Type `{ctx.prefix}help {ctx.command}` for more info")
            await ctx.send(embed=embed)
            return

        if isinstance(error, commands.CommandInvokeError):
            print(error)
            return

def setup(bot):
    bot.add_cog(ErrorHandler(bot))