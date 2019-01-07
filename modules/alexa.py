import discord
from discord.ext import commands


class Alexa:
    def __init__(self, bot):
        self.bot = bot

    async def on_message(self, message):
        if "alexa play despacito" in message.content:
            ctx.send("no")


def setup(bot):
    bot.add_cog(Alexa(bot))
