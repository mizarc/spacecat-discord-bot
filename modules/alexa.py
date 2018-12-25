import discord
from discord.ext import commands


class Alexa:
    def __init__(self, bot):
        self.bot = bot
        self.webhook = discord.Webhook.from_url(
            "https://discordapp.com/api/webhooks/503520485901074452/QxrkngBFG4"
            "vX5tz5Jmn2JRuq3EOG4Rf0yfelIrNWOxAjiydID7co1Ua_mMsh2CTIADnw",
            adapter=discord.RequestsWebhookAdapter())

    async def on_message(self, message):
        if "alexa play despacito" in message.content:
            self.webhook.send("no")


def setup(bot):
    bot.add_cog(Alexa(bot))
