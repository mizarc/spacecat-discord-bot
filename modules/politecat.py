import discord
from discord.ext import commands
import glob
import datetime
import os
import deps.perms as perms


class PoliteCat(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.group()
    @perms.admin()
    async def reactcfg(self, ctx):
        "Configure available reaction images"
        if ctx.invoked_subcommand is None:
            ctx.send("I am w o k e")

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
                        ctx.send("Image must be a png or a gif")
                    os.chdir("../")
                    ctx.send("Added *" + name + "* to reactions.")
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
            ctx.send("Reaction image does not exist")

        os.chdir("../")
        ctx.send("Removed *" + name + "* from reactions.")
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
            ctx.send(file=discord.File("assets/" + image + ".png"))
        except FileNotFoundError:
            ctx.send(file=discord.File("assets/" + image + ".gif"))


def setup(bot):
    bot.add_cog(PoliteCat(bot))
