import discord
from discord.ext import commands
import glob
import os
from PIL import Image
import helpers.perms as perms

class PoliteCat(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        

    @commands.Cog.listener()
    async def on_message(self, message):
        if not message.attachments:
            return

        if not message.attachments[0].filename[-4:] == 'webp':
            return

        # Open cache directory
        try:
            os.chdir("cache")
        except FileNotFoundError:
            os.mkdir("cache")
            os.chdir("cache")

        await message.attachments[0].save(str(message.id) + '.webp')
        image = Image.open(str(message.id) + '.webp')
        try:
            image.seek(1)
            image.info.pop('background', None)
            image.save(str(message.id) + '.gif', 'gif', save_all=True)
            await message.channel.send(file=discord.File(str(message.id) + '.gif'))
            os.remove(str(message.id) + '.gif')
            await message.delete()
            
        except:
            pass
        
        os.remove(str(message.id) + '.webp')
        os.chdir("../")
        return

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
        # Check if attachment exists in message
        try:
            image = ctx.message.attachments[0]
        except IndexError:
            await ctx.send("There are no attachments in the message")
            return

        # Open assets directory
        try:
            os.chdir("assets")
        except FileNotFoundError:
            os.mkdir("assets")
            os.chdir("assets")

        # Get all images in directory and add to list
        assetlist = []
        for files in glob.glob("*.webp"):
            assetlist.append(files[:-5])

        for files in glob.glob("*.gif"):
            assetlist.append(files[:-4])

        # Check if name already exists
        if name in assetlist:
            await ctx.send("Reaction name already exists.")
            os.chdir("../")
            return

        # Check if file extention is valid and convert to webp when possible
        ext = image.filename.split(".")[-1]
        if ext == "webp" or ext == "gif":
            await image.save(name + "." + ext)
        elif ext == "jpg" or ext == "jpeg" or ext == "bmp" or ext == "png":
            await image.save(name + '.webp')
        else:
            await ctx.send("Image must be formatted in " +
                            "webp, png, jpg, bmp or gif")
            os.chdir("../")
            return
        
        await ctx.send("Added *" + name + "* to reactions.")
        os.chdir("../")
        return

    @reactcfg.command()
    @perms.check()
    async def remove(self, ctx, name):
        "Remove a reaction image"
        
        os.chdir("assets")

        # Get all images from directoy and add to list
        assetlist = []
        for files in glob.glob("*.webp"):
            assetlist.append(files[:-5])

        for files in glob.glob("*.gif"):
            assetlist.append(files[:-4])

        # Check if image name exists
        if name not in assetlist:
            await ctx.send("Reaction image does not exist")
            os.chdir("../")
            return

        # Remove specified image
        try:
            os.remove(name + ".webp")
        except FileNotFoundError:
            os.remove(name + ".gif")
        finally:
            os.chdir("../")
            await ctx.send("Removed *" + name + "* from reactions.")
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
