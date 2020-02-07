import discord
from discord.ext import commands

from spacecat.helpers import perms
from spacecat.helpers import settings


class Dad(commands.Cog):
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
                    qualitycontent = f"Hi {' '.join(words[1:])}, I'm a Cat!"

                    # Different reply if next words start with "a cat"
                    if "a cat" in ' '.join(words[1:3]):
                        qualitycontent = "No you're not, I'm a cat."

                    await message.channel.send(qualitycontent)
                    return

    @commands.command()
    @perms.check()
    async def toggledad(self, ctx):
        if self.toggle:
            self.toggle = False
            embed = discord.Embed(colour=settings.embed_type('accept'), description="Dad has been disabled")
            await ctx.send(embed=embed) 
        elif not self.toggle:
            self.toggle = True
            embed = discord.Embed(colour=settings.embed_type('accept'), description="Dad has been enabled")
            await ctx.send(embed=embed) 


def setup(bot):
    bot.add_cog(Dad(bot))
