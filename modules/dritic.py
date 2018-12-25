import discord
from discord.ext import commands
import requests


class Seethreepio:
    def __init__(self, bot):
        self.bot = bot
        self.webhook = discord.Webhook.from_url(
            "https://discordapp.com/api/webhooks/512666631705591808/FsQniWc7Ai"
            "ad_AjMcrCYoDWiuK8gckqJUIO8431aHk2xTYnWSKS5P5qdD6oWyxoGcg1N",
            adapter=discord.RequestsWebhookAdapter())

    @commands.command()
    async def kek(self, ctx, *, message):
        self.webhook.send(message)

    @commands.command()
    async def kekc(self, ctx, name, *, message):
        self.webhook.send(message, username=name)


def setup(bot):
    bot.add_cog(Seethreepio(bot))
