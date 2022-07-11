import discord
from discord import app_commands
from discord.ext import commands

from spacecat.helpers import constants
from spacecat.helpers import perms


class Dad(commands.Cog):
    """A minor annoyance and a pinch of fun"""
    def __init__(self, bot):
        self.bot = bot
        self.toggle = True

    @commands.Cog.listener()
    async def on_message(self, message):
        if self.toggle:
            words = message.content.lower().split()
            triggers = ["im", "i'm"]

            # Compare first word to each trigger word
            for x in triggers:

                # Reply if first word starts with trigger word
                if x in words[:1]:
                    qualitycontent = f'Hi {" ".join(words[1:])}, I\'m a Cat!'

                    # Different reply if next words start with "a cat"
                    if 'a cat' in ' '.join(words[1:3]):
                        qualitycontent = "No you're not, I'm a cat."

                    await message.channel.send(qualitycontent)
                    return

    @app_commands.command()
    @perms.check()
    async def toggledad(self, interaction):
        if self.toggle:
            self.toggle = False
            embed = discord.Embed(
                colour=constants.EmbedStatus.NO.value,
                description="Dad has been disabled")
            await interaction.response.send_message(embed=embed)
        elif not self.toggle:
            self.toggle = True
            embed = discord.Embed(
                colour=constants.EmbedStatus.YES.value,
                description="Dad has been enabled")
            await interaction.response.send_message(embed=embed)


async def setup(bot):
    await bot.add_cog(Dad(bot))
