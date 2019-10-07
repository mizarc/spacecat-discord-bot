import discord
from discord.ext import commands

from helpers import perms
from helpers.appearance import embed_type

class Dad(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.channel = 97297058267951104
        self.toggle = True

    @commands.Cog.listener()
    async def on_message(self, message):
        if self.toggle:
            words = message.content.lower().split()

            triggers = ["im", "i'm"]

            for x in triggers:
                if x in words[:1]:
                    qualitycontent = "Hi " + " ".join(words[1:]) + ", I'm a Cat!"

                    if "a cat" in words[:2]:
                        qualitycontent = "No you're not, I'm a cat."
                    break
                else:
                    return

            print(qualitycontent)
            await message.channel.send(qualitycontent)

    @commands.command()
    @perms.check()
    async def toggledad(self, ctx):
        if self.toggle:
            self.toggle = False
            embed = discord.Embed(colour=embed_type('accept'), description="Dad has been disabled")
            await ctx.send(embed=embed) 
        elif not self.toggle:
            self.toggle = True
            embed = discord.Embed(colour=embed_type('accept'), description="Dad has been enabled")
            await ctx.send(embed=embed) 


def setup(bot):
    bot.add_cog(Dad(bot))
