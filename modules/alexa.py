import asyncio
import discord
import youtube_dl
from discord.ext import commands

youtube_dl.utils.bug_reports_message = lambda: ''


ytdl_format_options = {
    'format': 'bestaudio/best',
    'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
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
        self.queue = []

    @commands.command()
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
    async def leave(self, ctx):
        """Stops and leaves the voice channel"""
        # Check if in a voice channel
        if ctx.voice_client is None:
            await ctx.send("I can't leave if i'm not even in a voice channel")
            return

        # Disconnect from voice channel
        self.queue.clear()
        await ctx.voice_client.disconnect()
        return

    @commands.command()
    async def play(self, ctx, *, url):
        """Plays from a url (almost anything youtube_dl supports)"""
        # Join user's voice channel if not in one already
        if ctx.voice_client is None:
            await ctx.invoke(self.join)

        # Grab audio source from youtube_dl
        source = await YTDLSource.from_url(url, loop=self.bot.loop)

        # Play specified song if queue is empty
        if not self.queue:
            self.queue.append(source)
            ctx.voice_client.play(source)
            await ctx.send(f'Now playing: `{source.title}`')
            return

        # Add to queue if song is currently playing
        self.queue.append(source)
        await ctx.send(f"Added `{source.title}` to queue")

    @commands.command()
    async def stop(self, ctx):
        """Stops and clears the queue"""
        # Check if in a voice channel
        if ctx.voice_client is None:
            await ctx.send("I can't stop playing if i'm not even in a voice channel")
            return

        # Stops and clears the queue
        self.queue.clear()
        await ctx.voice_client.stop()
        await ctx.send("Music has been stopped & queue has been cleared")

    @commands.command()
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
    async def pause(self, ctx):
        """Pauses the music"""
        # Check if music is paused
        if ctx.voice_client is None or ctx.voice_client.is_paused():
            await ctx.send("Music is already paused")
            return

        # Pauses music playback
        ctx.voice_client.pause()
        await ctx.send("Music has been paused")


def setup(bot):
    bot.add_cog(Alexa(bot))
