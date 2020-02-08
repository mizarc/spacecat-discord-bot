import discord
from discord.ext import commands

from spacecat.helpers import settings


class Help(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        bot.remove_command('help')

    @commands.command()
    async def help(self, ctx, menu=None):
        # Output first in queue as currently playing
        embed = discord.Embed(colour=settings.embed_type('info'))
        image = discord.File(settings.embed_icons("information"), filename="image.png")
        embed.set_author(name="Help Menu", icon_url="attachment://image.png")

        modules = self.bot.cogs
        modules_output = []
        for module in modules.values():
            modules_output.append(f"`{module.qualified_name}`: {module.description}")
        #modules_output = 

        embed.add_field(
        name="Type !help <module> to list all commands in the module",
        value="\n".join(modules_output))


        # Output results to chat
        await ctx.send(file=image, embed=embed)


def setup(bot):
    bot.add_cog(Help(bot))