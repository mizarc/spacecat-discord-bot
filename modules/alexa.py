import asyncio
import discord
import os
import shutil
import youtube_dl
from discord.ext import commands
import helpers.perms as perms

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
                await ctx.send("You must specify or be in a channel")
                return

        # Connect if not in a voice channel
        if ctx.voice_client is None:
            await channel.connect()
            return

        # Check if the specified voice channel is the same as the current channel
        if channel == ctx.voice_client.channel:
            await ctx.send("I'm already in that voice channel")
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
            await ctx.send("I can't leave if i'm not even in a voice channel")
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
        self.song_queue.append(source)

        # Play specified song if only one song in queue
        if len(self.song_queue) == 1:
            ctx.voice_client.play(source, after=lambda e: self._next(ctx))
            await ctx.send(f'Now playing: `{source.title}`')
            return

        # Notify user of song being added to queue
        await ctx.send(f"Added `{source.title}` to queue")

    @commands.command()
    @perms.check()
    async def stop(self, ctx):
        """Stops and clears the queue"""
        # Check if in a voice channel
        if ctx.voice_client is None:
            await ctx.send("I can't stop playing if i'm not even in a voice channel")
            return

        # Stops and clears the queue
        ctx.voice_client.stop()
        await asyncio.sleep(0.1)
        self.song_queue.clear()
        shutil.rmtree('cache')
        await ctx.send("Music has been stopped & queue has been cleared")

    @commands.command()
    @perms.check()
    async def resume(self, ctx):
        """Resumes music if paused"""
        # Check if music is paused
        if ctx.voice_client is None or not ctx.voice_client.is_paused():
            await ctx.send("Music isn't paused")
            return

        # Resumes music playback
        ctx.voice_client.resume()
        await ctx.send("Music has been resumed")

    @commands.command()
    @perms.check()
    async def pause(self, ctx):
        """Pauses the music"""
        # Check if music is paused
        if ctx.voice_client is None or ctx.voice_client.is_paused():
            await ctx.send("Music is already paused")
            return

        # Pauses music playback
        ctx.voice_client.pause()
        await ctx.send("Music has been paused")

    @commands.command()
    @perms.check()
    async def skip(self, ctx):
        """Skip the current song and play the next song"""
        # Check if there's queue is empty
        if len(self.song_queue) <= 1:
            await ctx.send("There's nothing in the queue after this")
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
            await ctx.send("Loop disabled")
            return

        self.loop_toggle = True
        await ctx.send("Loop enabled")
        return

    @commands.command()
    @perms.check()
    async def queue(self, ctx):
        """List the current song queue"""
        # Notify user if nothing is in the queue
        if not self.song_queue:
            await ctx.send("There's nothing in the queue right now")
            return
        
        # Output first in queue as currently playing
        await ctx.send(f"Currently Playing: `{self.song_queue[0].title}`")

        # List remaining songs in queue
        if len(self.song_queue) > 1:
            queue_formatted = []
            for index, song in enumerate(self.song_queue[1:]):
                queue_formatted.append(f"{index + 1}. `{song.title}`")
            queue_output = '\n'.join(queue_formatted)
            await ctx.send(f"Next Up:\n {queue_output}")
        
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
