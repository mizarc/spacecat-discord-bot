import discord
from discord.ext import commands

from spacecat.helpers import settings


class Help(commands.Cog):
    """Information on how to use commands"""
    def __init__(self, bot):
        self.bot = bot
        bot.remove_command('help')

    @commands.command()
    async def help(self, ctx, menu=None):
        # Create embed
        embed = discord.Embed(colour=settings.embed_type('info'),
        description=f"Type !help <module> to list all commands in the module")
        image = discord.File(settings.embed_icons("information"), filename="image.png")
        embed.set_author(name="Help Menu", icon_url="attachment://image.png")

        # Add all modules to the embed
        modules = self.bot.cogs
        for module in modules.values():
            embed.add_field(
                name=f"**{module.qualified_name}**",
                value=f"{module.description}")
        await ctx.send(file=image, embed=embed)


def setup(bot):
    bot.add_cog(Help(bot))