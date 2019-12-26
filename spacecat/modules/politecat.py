import glob
import os

import discord
from discord.ext import commands
from PIL import Image

from helpers import perms
from helpers import settings


class PoliteCat(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.webp_convert = True

    @commands.Cog.listener()
    async def on_message(self, message):
        if not self.webp_convert:
            return

        # Check for valid webp attachment
        if not message.attachments:
            return
        elif not message.attachments[0].filename[-4:] == 'webp':
            return

        # Fetch image from attachment
        gif = f'{settings.cache}{str(message.id)}.gif'
        webp = f'{settings.cache}{str(message.id)}.webp'
        await message.attachments[0].save(webp)
        image = Image.open(webp)

        # Check if webp is animated
        try:
            image.seek(1)
        except EOFError:
            return

        # Convert webp to gif
        try:
            image.info.pop('background', None)
            image.save(gif, 'gif', save_all=True)

            # Add spoiler tag if original image is tagged as a spoiler
            spoiler = False
            if message.attachments[0].is_spoiler():
                spoiler = True

            await message.channel.send(
            f"**{message.author.display_name} sent:**\n{message.content}",
            file=discord.File(gif, spoiler=spoiler))
            await message.delete()

        # Notify if conversion failed
        except discord.errors.HTTPException:
            embed = discord.Embed(
                colour=settings.embed_type('warn'),
                description=f"Failed to convert webp to gif. "
                "Image may be too large")
            await message.channel.send(embed=embed) 
            return
        finally:
            os.remove(gif)
            os.remove(webp)
        
        return

    @commands.command()
    @perms.check()
    async def togglewebp(self, ctx):
        if self.webp_convert:
            self.webp_convert = False
            embed = discord.Embed(
                colour=settings.embed_type('accept'),
                description="Automatic WebP conversion has been disabled")
            await ctx.send(embed=embed)

        elif not self.webp_convert:
            self.webp_convert = True
            embed = discord.Embed(
                colour=settings.embed_type('accept'),
                description="Automatic WebP conversion has been enabled")
            await ctx.send(embed=embed)

    @commands.group()
    @perms.check()
    async def reactcfg(self, ctx):
        "Configure available reaction images"
        if ctx.invoked_subcommand is None:
            embed = discord.Embed(colour=settings.embed_type('warn'), description=f"Please specify a valid subcommand: `add/remove`")
            await ctx.send(embed=embed) 

    @reactcfg.command()
    @perms.check()
    async def add(self, ctx, name):
        "Add a reaction image"
        # Check if attachment exists in message
        try:
            image = ctx.message.attachments[0]
        except IndexError:
            embed = discord.Embed(colour=settings.embed_type('warn'), description=f"There are no attachments in that message")
            await ctx.send(embed=embed) 
            return

        # Create reactions folder if it doesn't exist
        if not os.path.exists(settings.data + 'reactions/'):
            os.mkdir(settings.data + 'reactions/')

        # Cancel if name already exists
        reactions = await self._get_reactions()
        if name in reactions:
            embed = discord.Embed(colour=settings.embed_type('warn'), description=f"Reaction name already in use")
            await ctx.send(embed=embed)
            return

        # Check if file extention is valid and convert to webp when possible
        ext = image.filename.split(".")[-1]
        if ext == "webp" or ext == "gif":
            await image.save(f'{settings.data}reactions/{name}.{ext}')
        elif ext == "jpg" or ext == "jpeg" or ext == "bmp" or ext == "png":
            await image.save(f'{settings.data}reactions/{name}.webp')
        else:
            await ctx.send("Image must be formatted in " +
                            "webp, png, jpg, bmp or gif")
            return
        
        embed = discord.Embed(colour=settings.embed_type('accept'), description=f"Added {name} to reactions")
        await ctx.send(embed=embed)
        return

    @reactcfg.command()
    @perms.check()
    async def remove(self, ctx, name):
        "Remove a reaction image"
        # Cancel if image name exists
        reactions = await self._get_reactions()
        if name not in reactions:
            embed = discord.Embed(colour=settings.embed_type('warn'), description="Reaction image does not exist")
            await ctx.send(embed=embed)
            return

        # Remove specified image
        try:
            os.remove(f"{settings.data}reactions/{name}.webp")
        except FileNotFoundError:
            os.remove(f"{settings.data}reactions/{name}.gif")

        embed = discord.Embed(colour=settings.embed_type('accept'), description=f"Removed {name} from reactions")
        await ctx.send(embed=embed) 
        return
            

    @commands.command()
    @perms.check()
    async def reactlist(self, ctx):
        "List all reaction images"
        reactions = self._get_reactions()

        # Alert if no reactions exist
        if not reactions:
            embed = discord.Embed(colour=settings.embed_type('warn'), description="No reactions are available")
            await ctx.send(embed=embed)
            return

    @commands.command()
    @perms.check()
    async def react(self, ctx, name):
        "Use an image/gif as a reaction"
        # Try sending WebP
        try:
            await ctx.send(
                file=discord.File(f"{settings.data}reactions/{name}.webp"))
            return
        except FileNotFoundError:
            pass

        # Try sending Gif
        try:
            await ctx.send(
                file=discord.File(f"{settings.data}reactions/{name}.gif"))
            return
        except FileNotFoundError:
            pass

        # Warn if reaction name doesn't exist
        embed = discord.Embed(
            colour=settings.embed_type('warn'),
            description=f"Reaction `{name}` does not exist")
        await ctx.send(embed=embed) 

    async def _get_reactions(self):
        # Get all images from directoy and add to list
        reactions = []
        for files in glob.glob(settings.data + "reactions/*"):
            existing_image = os.path.basename(os.path.splitext(files)[0])
            reactions.append(existing_image)
        return reactions


def setup(bot):
    bot.add_cog(PoliteCat(bot))
