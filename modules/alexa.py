import asyncio
import datetime
import os
import shutil

import discord
from discord.ext import commands
import youtube_dl

from helpers.appearance import embed_type, embed_icons
from helpers import perms

youtube_dl.utils.bug_reports_message = lambda: ''


ytdl_format_options = {
    'format': 'bestaudio/best',
    'outtmpl': 'cache/%(extractor)s-%(id)s-%(title)s.%(ext)s',
    'restrictfilenames': True,
    'noplaylist': True,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'auto',
    'source_address': '0.0.0.0'
}

ffmpeg_options = {
    'options': '-vn'
}

ytdl = youtube_dl.YoutubeDL(ytdl_format_options)


class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data, volume=0.5):
        super().__init__(source, volume)

        self.data = data

        self.title = data.get('title')
        self.url = data.get('url')
        self.duration = data.get('duration')
        self.webpage_url = data.get('webpage_url')

    @classmethod
    async def from_url(cls, url, *, loop=None, stream=False):
        loop = loop or asyncio.get_event_loop()
        data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=not stream))

        if 'entries' in data:
            # take first item from a playlist
            data = data['entries'][0]

        filename = data['url'] if stream else ytdl.prepare_filename(data)
        return cls(discord.FFmpegPCMAudio(filename, **ffmpeg_options), data=data)


class Alexa(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.song_queue = []
        self.loop_toggle = False
        self.skip_toggle = False
        self.keep_cache = False

    @commands.command()
    @perms.check()
    async def join(self, ctx, *, channel: discord.VoiceChannel = None):
        """Joins a voice channel"""
        # Get user's current channel if no channel is specified
        if channel == None:
            try:
                channel = ctx.author.voice.channel
            except AttributeError:
                embed = discord.Embed(colour=embed_type('warn'), description=f"You must specify or be in a voice channel")
                await ctx.send(embed=embed)
                return

        # Connect if not in a voice channel
        if ctx.voice_client is None:
            await channel.connect()
            return

        # Check if the specified voice channel is the same as the current channel
        if channel == ctx.voice_client.channel:
            embed = discord.Embed(colour=embed_type('warn'), description=f"I'm already in that voice channel")
            await ctx.send(embed=embed)
            return

        # Move to specified channel
        await ctx.voice_client.move_to(channel)
        return

    @commands.command()
    @perms.check()
    async def leave(self, ctx):
        """Stops and leaves the voice channel"""
        # Check if in a voice channel
        if ctx.voice_client is None:
            embed = discord.Embed(colour=embed_type('warn'), description=f"I can't leave if i'm not in a voice channel")
            await ctx.send(embed=embed)
            return

        # Stop and Disconnect from voice channel
        await ctx.invoke(self.stop)
        await ctx.voice_client.disconnect()
        return

    @commands.command()
    @perms.check()
    async def play(self, ctx, *, url):
        """Plays from a url (almost anything youtube_dl supports)"""
        # Join user's voice channel if not in one already
        if ctx.voice_client is None:
            await ctx.invoke(self.join)

        # Grab audio source from youtube_dl and add to queue
        source = await YTDLSource.from_url(url, loop=self.bot.loop)
        song_name = f"[{source.title}]({source.webpage_url}) `{str(datetime.timedelta(seconds=source.duration))[2:]}`"
        self.song_queue.append(source)

        # Play specified song if only one song in queue
        if len(self.song_queue) == 1:
            ctx.voice_client.play(source, after=lambda e: self._next(ctx))
            embed = discord.Embed(colour=embed_type('info'), description=f"Now playing {song_name}")
            await ctx.send(embed=embed)
            return

        # Notify user of song being added to queue
        embed = discord.Embed(colour=embed_type('accept'), description=f"Added {song_name} to #{len(self.song_queue) - 1} in queue")
        await ctx.send(embed=embed)

    @commands.command()
    @perms.check()
    async def stop(self, ctx):
        """Stops and clears the queue"""
        # Check if in a voice channel
        if ctx.voice_client is None:
            embed = discord.Embed(colour=embed_type('warn'), description="I can't stop playing if I'm not in a voice channel")
            await ctx.send(embed=embed)
            return

        # Stops and clears the queue
        ctx.voice_client.stop()
        await asyncio.sleep(0.1)
        self.song_queue.clear()
        embed = discord.Embed(colour=embed_type('accept'), description="Music has been stopped & queue has been cleared")
        await ctx.send(embed=embed)

    @commands.command()
    @perms.check()
    async def resume(self, ctx):
        """Resumes music if paused"""
        # Check if music is paused
        if ctx.voice_client is None or not ctx.voice_client.is_paused():
            embed = discord.Embed(colour=embed_type('warn'), description="Music isn't paused")
            await ctx.send(embed=embed)
            return

        # Resumes music playback
        ctx.voice_client.resume()
        embed = discord.Embed(colour=embed_type('accept'), description="Music has been resumed")
        await ctx.send(embed=embed)

    @commands.command()
    @perms.check()
    async def pause(self, ctx):
        """Pauses the music"""
        # Check if music is paused
        if ctx.voice_client is None or ctx.voice_client.is_paused():
            embed = discord.Embed(colour=embed_type('warn'), description="Music is already paused")
            await ctx.send(embed=embed)
            return

        # Pauses music playback
        ctx.voice_client.pause()
        embed = discord.Embed(colour=embed_type('accept'), description="Music has been paused")
        await ctx.send(embed=embed)

    @commands.command()
    @perms.check()
    async def skip(self, ctx):
        """Skip the current song and play the next song"""
        # Check if there's queue is empty
        if len(self.song_queue) <= 1:
            embed = discord.Embed(colour=embed_type('warn'), description="There's nothing in the queue after this")
            await ctx.send(embed=embed)
            return

        # Stop current song and flag that it has been skipped
        self.skip_toggle = True
        ctx.voice_client.stop()

    @commands.command()
    @perms.check()
    async def loop(self, ctx):
        """Loop the currently playing song"""
        if self.loop_toggle:
            self.loop_toggle = False
            embed = discord.Embed(colour=embed_type('accept'), description=f"Loop disabled")
            await ctx.send(embed=embed)
            return

        self.loop_toggle = True
        embed = discord.Embed(colour=embed_type('warn'), description=f"Loop enabled")
        await ctx.send(embed=embed)
        return

    @commands.command()
    @perms.check()
    async def queue(self, ctx):
        """List the current song queue"""
        # Notify user if nothing is in the queue
        if not self.song_queue:
            embed = discord.Embed(colour=embed_type('warn'), description=f"There's nothing in the queue right now")
            await ctx.send(embed=embed)
            return
        
        # Output first in queue as currently playing
        embed = discord.Embed(colour=embed_type('info'))
        image = discord.File(embed_icons("music"), filename="image.png")
        embed.set_author(name="Music Queue", icon_url="attachment://image.png")
        embed.add_field(name="Currently Playing", value=self.song_queue[0].title)
        
        # List remaining songs in queue
        if len(self.song_queue) > 1:
            queue_formatted = []
            for index, song in enumerate(self.song_queue[1:]):
                queue_formatted.append(f"{index + 1}. {song.title}")
            queue_output = '\n'.join(queue_formatted)
            embed.add_field(name="Queue", value=queue_output, inline=False)

        await ctx.send(file=image, embed=embed)
        
    def _next(self, ctx):
        # If looping, grab cached file and play it again from the start
        if self.loop_toggle and not self.skip_toggle:
            source = discord.FFmpegPCMAudio(ytdl.prepare_filename(self.song_queue[0].data))
            ctx.voice_client.play(source, after=lambda e: self._next(ctx))
            return

        # Remove already played songs from cache & queue
        os.remove(ytdl.prepare_filename(self.song_queue[0].data))
        self.song_queue.pop(0)

        # Disable skip toggle to indicate that a skip has been completed
        if self.skip_toggle:
            self.skip_toggle = False

        # Remove first in queue and play the new first in list
        if self.song_queue:
            ctx.voice_client.play(self.song_queue[0], after=lambda e: self._next(ctx))
            return


def setup(bot):
    bot.add_cog(Alexa(bot))
