import discord
from discord.ext import commands
import glob
import os
from PIL import Image
import helpers.perms as perms

class PoliteCat(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.group()
    @perms.check()
    async def reactcfg(self, ctx):
        "Configure available reaction images"
        if ctx.invoked_subcommand is None:
            await ctx.send("Please specify a subcommand. Add/Remove")

    @reactcfg.command()
    @perms.check()
    async def add(self, ctx, name):
        "Add a reaction image"
        try:
            ctx.message.attachments[0]
        except IndexError:
            await ctx.send("There are no attachments in the message")
            return

        assetlist = []
        os.chdir("assets")

        for files in glob.glob("*.webp"):
            assetlist.append(files[:-5])

        for files in glob.glob("*.gif"):
            assetlist.append(files[:-4])

        if name not in assetlist:
            ext = ctx.message.attachments[0].filename.split(".")[-1]

            if ext == "webp" or ext == "gif":
                await ctx.message.attachments[0].save(
                    name + "." + ext)
            elif ext == "jpg" or ext == "jpeg" or ext == "bmp" or ext == "png":
                image = ctx.message.attachments[0]
                await image.save(name + '.webp')
            else:
                await ctx.send("Image must be formatted in " +
                                "webp, png, jpg, bmp or gif")
                return
            
            await ctx.send("Added *" + name + "* to reactions.")

        os.chdir("../")
        return

    @reactcfg.command()
    @perms.check()
    async def remove(self, ctx, name):
        "Remove a reaction image"
        assetlist = []
        os.chdir("assets")

        for files in glob.glob("*.webp"):
            assetlist.append(files[:-5])

        for files in glob.glob("*.gif"):
            assetlist.append(files[:-4])

        if name in assetlist:
            try:
                os.remove(name + ".webp")
            except FileNotFoundError:
                os.remove(name + ".gif")
            finally:
                os.chdir("../")
                await ctx.send("Removed *" + name + "* from reactions.")
                return
        else:
            os.chdir("../")
            await ctx.send("Reaction image does not exist")
            return

    @commands.command()
    @perms.check()
    async def reactlist(self, ctx):
        "List all reaction images"
        assetlist = []
        os.chdir("assets")

        for files in glob.glob("*.png"):
            assetlist.append(files[:-4])

        for files in glob.glob("*.gif"):
            assetlist.append(files[:-4])

    @commands.command()
    @perms.check()
    async def react(self, ctx, image):
        "Use an image/gif as a reaction"
        try:
            await ctx.send(file=discord.File("assets/" + image + ".webp"))
        except FileNotFoundError:
            await ctx.send(file=discord.File("assets/" + image + ".gif"))


def setup(bot):
    bot.add_cog(PoliteCat(bot))
