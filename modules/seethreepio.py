import discord
from discord.ext import commands


class Seethreepio:
    def __init__(self, bot):
        self.bot = bot
        self.webhook = discord.Webhook.from_url(
            "https://discordapp.com/api/webhooks/503821187479109642/B45e9xmjoE"
            "YHC0uUnjAklcjONLNh64qrz_f2trCv1-uvKKxjAa9TjLRdTzbqInGoaEt0",
            adapter=discord.RequestsWebhookAdapter())

    @commands.command()
    async def flip(self, ctx, member: discord.Member):
        if member.id != self.bot.user.id:
            self.webhook.send('(╯°□°）╯︵ ' + member.mention)
        else:
            self.webhook.send("Bitch please. \n'(╯°□°）╯︵ " +
                              ctx.message.author.mention)


def setup(bot):
    bot.add_cog(Seethreepio(bot))
