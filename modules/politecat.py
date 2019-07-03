import discord
from discord.ext import commands
import glob
import os
from PIL import Image


class PoliteCat(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.group()
    async def reactcfg(self, ctx):
        "Configure available reaction images"
        if ctx.invoked_subcommand is None:
            await ctx.send("I am w o k e")

    @reactcfg.command()
    async def add(self, ctx, name):
        "Add a reaction image"
        assetlist = []
        os.chdir("assets")

        for files in glob.glob("*.webp"):
            assetlist.append(files[:-5])

        for files in glob.glob("*.gif"):
            assetlist.append(files[:-4])

        if name not in assetlist:
            if ctx.message.attachments is not None:

                ext = ctx.message.attachments[0].filename.split(".")[-1]
                print(ext)
                if ext == "webp" or ext == "gif":
                    await ctx.message.attachments[0].save(
                        name + ext)
                elif ext == "jpg" or ext == "jpeg" or ext == "bmp":
                    image = ctx.message.attachments[0]
                    await image.save(name + '.webp')
                else:
                    await ctx.send("Image must be formatted in " +
                                   "webp, png, jpg, bmp or gif")
                os.chdir("../")
                await ctx.send("Added *" + name + "* to reactions.")
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
    async def react(self, ctx, image):
        "Use an image/gif as a reaction"
        try:
            await ctx.send(file=discord.File("assets/" + image + ".webp"))
        except FileNotFoundError:
            await ctx.send(file=discord.File("assets/" + image + ".gif"))


def setup(bot):
    bot.add_cog(PoliteCat(bot))
