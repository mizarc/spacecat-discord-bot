import discord
from discord.ext import commands


class Dad:
    def __init__(self, bot):
        self.bot = bot
        self.webhook = discord.Webhook.from_url(
            "https://discordapp.com/api/webhooks/503836986956840960/L-Z5eLPoV1"
            "FC5Q48jaDtM2llapn53-rYQrRvCzQ6X_urzYEmOSBit0dR9PwQEx-DRapQ",
            adapter=discord.RequestsWebhookAdapter())
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

                self.webhook.send(qualitycontent)

    @commands.command()
    async def toggledad(self, ctx):
        if self.toggle:
            self.toggle = False
            self.webhook.send("Dad has been disabled")
        elif not self.toggle:
            self.toggle = True
            self.webhook.send("Dad has been enabled")


def setup(bot):
    bot.add_cog(Dad(bot))
