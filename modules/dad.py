import discord
from discord.ext import commands
import deps.perms as perms


class Dad(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.channel = 97297058267951104
        self.toggle = True

    async def on_message(self, message):
        if message.channel.id == self.channel:
            if self.toggle:
                words = message.content.lower().split()

                triggers = ["im", "i'm"]

                for x in triggers:
                    if x in words[:1]:
                        qualitycontent = "Hi " + " ".join(words[1:])
                        + ", I'm Dad!"

                        if "dad" in words[:2]:
                            qualitycontent = "No you're not, I'm dad."
                    else:
                        return

                ctx.send(qualitycontent)

    @commands.command()
    @perms.mod()
    async def toggledad(self, ctx):
        if self.toggle:
            self.toggle = False
            ctx.send("Dad has been disabled")
        elif not self.toggle:
            self.toggle = True
            ctx.send("Dad has been enabled")


def setup(bot):
    bot.add_cog(Dad(bot))
