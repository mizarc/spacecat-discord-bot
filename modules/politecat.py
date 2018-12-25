import discord
from discord.ext import commands
import glob
import datetime
import os
import deps.perms as perms


class PoliteCat:
    def __init__(self, bot):
        self.bot = bot
        self.webhook = discord.Webhook.from_url(
            "https://discordapp.com/api/webhooks/503811017990471680/-XL-S8muBK"
            "1Jrz8ND_8ZoAz47hSx84uPbxMmk0IGKG5iNR7S1-W0V-mqfV8YtEEenF_5",
            adapter=discord.RequestsWebhookAdapter())

    @commands.group()
    @perms.admin()
    async def reactcfg(self, ctx):
        "Configure available reaction images"
        if ctx.invoked_subcommand is None:
            self.webhook.send("I am w o k e")

    @reactcfg.command()
    async def add(self, ctx, name):
        "Add a reaction image"
        assetlist = []
        os.chdir("assets")

        twomin = datetime.datetime.now() - datetime.timedelta(minutes=2)

        for files in glob.glob("*.png"):
            assetlist.append(files[:-4])

        for files in glob.glob("*.gif"):
            assetlist.append(files[:-4])

        if name not in assetlist:
            async for message in ctx.history(after=twomin):
                if message.author == ctx.author and message.attachments:
                    extension = message.attachments[0].filename[-4:]
                    print(message.attachments[0].filename[-4:])
                    if extension == ".png" or extension == ".gif":
                        await message.attachments[0].save(
                            name + extension)
                    else:
                        self.webhook.send("Image must be a png or a gif")
                    os.chdir("../")
                    self.webhook.send("Added *" + name + "* to reactions.")
                    return

    @reactcfg.command()
    async def remove(self, ctx, name):
        "Remove a reaction image"
        assetlist = []
        os.chdir("assets")

        for files in glob.glob("*.png"):
            assetlist.append(files[:-4])

        for files in glob.glob("*.gif"):
            assetlist.append(files[:-4])

        if name in assetlist:
            try:
                os.remove(name + ".png")
            except FileNotFoundError:
                os.remove(name + ".gif")
        else:
            self.webhook.send("Reaction image does not exist")

        os.chdir("../")
        self.webhook.send("Removed *" + name + "* from reactions.")
        return

    @commands.command()
    async def reactlist(self, ctx):
        "List all reaction images"
        assetlist = []
        os.chdir("assets")

        for files in glob.glob("*.png"):
            assetlist.append(files[:-4])

        for files in glob.glob("*.gif"):
            assetlist.append(files[:-4])

    @commands.command()
    @perms.admin()
    async def react(self, ctx, image):
        "Use an image/gif as a reaction"
        try:
            self.webhook.send(file=discord.File("assets/" + image + ".png"))
        except FileNotFoundError:
            self.webhook.send(file=discord.File("assets/" + image + ".gif"))


def setup(bot):
    bot.add_cog(PoliteCat(bot))
