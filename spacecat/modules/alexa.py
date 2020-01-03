import asyncio
from itertools import islice
import os
import re
import shutil
import sqlite3
from time import gmtime, strftime, time

import discord
from discord.ext import commands
import youtube_dl
from bs4 import BeautifulSoup as bs
import requests

from helpers import perms
from helpers import settings


youtube_dl.utils.bug_reports_message = lambda: ''


ytdl_format_options = {
    'format': 'bestaudio',
    'restrictfilenames': True,
    'noplaylist': True,
    'nocheckcertificate': True,
    'ignoreerrors': True,
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'auto',
    'source_address': '0.0.0.0',
    'youtube_include_dash_manifest': False
}

ffmpeg_options = {
    'options': '-vn -loglevel quiet'
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
    async def from_url(cls, url):
        loop = asyncio.get_event_loop()
        data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=False))
        before_args = "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5" 

        if 'entries' in data:
            # take first item from a playlist
            data = data['entries'][0]

        return cls(discord.FFmpegPCMAudio(data['url'], **ffmpeg_options, before_options=before_args), data=data)


class Alexa(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.song_queue = {}
        self.start_time = {}
        self.loop_toggle = {}
        self.skip_toggle = {}

    @commands.Cog.listener()
    async def on_ready(self):
        # Create playlist table if it don't exist
        db = sqlite3.connect(settings.data + 'spacecat.db')
        cursor = db.cursor()
        cursor.execute('PRAGMA foreign_keys = ON')

        cursor.execute(
            'CREATE TABLE IF NOT EXISTS playlist'
            '(id INTEGER PRIMARY KEY, name TEXT, description TEXT,'
            'server_id INTEGER)')

        cursor.execute(
            'CREATE TABLE IF NOT EXISTS playlist_music'
            '(id INTEGER PRIMARY KEY, title TEXT, length INTEGER, url TEXT,'
            'previous_song INTEGER, playlist_id INTEGER,'
            'FOREIGN KEY(playlist_id) REFERENCES playlist(id))')

        db.commit()
        db.close()

    @commands.command()
    @perms.check()
    async def join(self, ctx, *, channel: discord.VoiceChannel = None):
        """Joins a voice channel"""
        # Get user's current channel if no channel is specified
        if channel == None:
            try:
                channel = ctx.author.voice.channel
            except AttributeError:
                embed = discord.Embed(colour=settings.embed_type('warn'), description=f"You must specify or be in a voice channel")
                await ctx.send(embed=embed)
                return

        # Connect if not in a voice channel
        await self._add_server_keys(ctx.guild)
        if ctx.voice_client is None:
            await channel.connect()
            return

        # Check if the specified voice channel is the same as the current channel
        if channel == ctx.voice_client.channel:
            embed = discord.Embed(colour=settings.embed_type('warn'), description=f"I'm already in that voice channel")
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
        status = await self._check_music_status(ctx, ctx.guild)
        if not status:
            return

        # Stop and Disconnect from voice channel
        await ctx.invoke(self.stop)
        await ctx.voice_client.disconnect()
        await self._remove_server_keys(ctx.guild)
        return

    @commands.command()
    @perms.check()
    async def play(self, ctx, *, url):
        """Plays from a url (almost anything youtube_dl supports)"""
        # Join user's voice channel if not in one already
        if ctx.voice_client is None:
            await ctx.invoke(self.join)

            # End function if bot failed to join a voice channel.
            if ctx.voice_client is None:
                return
        
        # Check if too many songs in queue
        if len(self.song_queue[ctx.guild.id]) > 30:
            embed = discord.Embed(colour=settings.embed_type('warn'), description="Too many songs in queue. Calm down.")

        # Grab audio source from youtube_dl and check if longer than 3 hours
        source = await YTDLSource.from_url(url)
        print(source)
        if source.duration >= 10800:
            embed = discord.Embed(colour=settings.embed_type('warn'), description="Video must be shorter than 3 hours")
            await ctx.send(embed=embed)
            return
        duration = await self._get_duration(source.duration)
        song_name = f"[{source.title}]({source.webpage_url}) `{duration}`"

        # Notify user of song being added to queue
        if len(self.song_queue[ctx.guild.id]) > 0:
            self.song_queue[ctx.guild.id].append(source)
            embed = discord.Embed(
                colour=settings.embed_type('accept'),
                description=f"Added {song_name} to #{len(self.song_queue[ctx.guild.id]) - 1} in queue")

        # Play song instantly and notify user
        else:
            self.song_queue[ctx.guild.id].append(source)
            self.start_time[ctx.guild.id] = time()
            ctx.voice_client.play(source, after=lambda e: self._next(ctx))
            embed = discord.Embed(colour=settings.embed_type('accept'), description=f"Now playing {song_name}")

        await ctx.send(embed=embed)
        return

    @commands.command()
    @perms.check()
    async def playsearch(self, ctx, *, search):
        # Join user's voice channel if not in one already
        if ctx.voice_client is None:
            await ctx.invoke(self.join)

            # End function if bot failed to join a voice channel.
            if ctx.voice_client is None:
                return

        # Set urls to be used by the searcher
        base_url = "https://www.youtube.com"
        search_url = f"https://www.youtube.com/results?search_query={search}"

        # Query youtube with a search term and grab the title, duration and url
        # of all videos on the page
        source = requests.get(search_url).text
        soup = bs(source, 'html.parser')
        titles = soup.find_all('a', attrs={'class':'yt-uix-tile-link'})
        durations = soup.find_all('span', attrs={'class':'video-time'})
        urls = []
        for title in titles:
            urls.append(f"{base_url}{title.attrs['href']}")

        # Alert user if search term returns no results
        if not titles:
            embed = discord.Embed(
                colour=settings.embed_type('warn'),
                description="Search query returned no results")
            await ctx.send(embed=embed)
            return
        
        # Format the data to be in a usable list
        index = 0
        results_format = []
        for title, duration, url in zip(titles, durations, urls):
            # Stop at 5 songs
            if index == 5:
                break
            # Skip playlists
            if '&list=' in url:
                continue
            index += 1
            results_format.append(f"{index}. [{title.get_text()}]({url}) `{duration.get_text()}`")

        # Output results to chat
        embed = discord.Embed(colour=settings.embed_type('info'))
        image = discord.File(settings.embed_icons("music"), filename="image.png")
        embed.set_author(name=f"Search Query", icon_url="attachment://image.png")
        results_output = '\n'.join(results_format)
        embed.add_field(
            name=f"Results for '{search}'",
            value=results_output, inline=False)
        msg = await ctx.send(file=image, embed=embed)

        # Add reaction button for every result
        reactions = []
        for index, result in enumerate(results_format):
            emoji = settings.number_to_emoji(index + 1)
            await msg.add_reaction(emoji)
            reactions.append(emoji)

        # Check if the requester selects a valid reaction
        def reaction_check(reaction, user):
            if user == ctx.author and str(reaction) in reactions:
                return reaction

        # Request reaction within timeframe
        try:
            reaction, user = await self.bot.wait_for(
                'reaction_add', timeout=30.0, check=reaction_check)
        except asyncio.TimeoutError:
            embed = discord.Embed(
                    colour=settings.embed_type('warn'),
                    description=f"Song selection timed out.")
            embed.set_author(name=f"Search Query", icon_url="attachment://image.png")
            await msg.clear_reactions()
            await msg.edit(file=None, embed=embed)
            return

        # Play selected song
        number = settings.emoji_to_number(str(reaction))
        selected_song = urls[number - 1]
        await ctx.invoke(self.play, url=selected_song)

    @commands.command()
    @perms.check()
    async def playplaylist(self, ctx, playlist):
        """Play from a locally saved playlist"""
        # Join user's voice channel if not in one already
        if ctx.voice_client is None:
            await ctx.invoke(self.join)

            # End function if bot failed to join a voice channel.
            if ctx.voice_client is None:
                return

        # Get all songs in playlist
        try:
            playlist_id, songs = await self._get_songs(ctx, playlist)
        except TypeError:
            embed = discord.Embed(
                colour=settings.embed_type('warn'),
                description=f"Playlist `{playlist}` does not exist")
            await ctx.send(embed=embed)
            return
        song_links = {}
        for song in songs:
            song_links[song[4]] = [song[0], song]

        # Play first song if no song is currently playing
        next_song = song_links.get(None)
        if len(self.song_queue[ctx.guild.id]) == 0:
            source = await YTDLSource.from_url(next_song[1][3])
            next_song = song_links.get(next_song[0])
            self.song_queue[ctx.guild.id].append(source)
            self.start_time[ctx.guild.id] = time()
            ctx.voice_client.play(source, after=lambda e: self._next(ctx))
            embed = discord.Embed(
                colour=settings.embed_type('accept'),
                description=f"Now playing playlist `{playlist}`")
            await ctx.send(embed=embed)

        # Add remaining songs to queue
        while next_song is not None:
            source = await YTDLSource.from_url(next_song[1][3])
            self.song_queue[ctx.guild.id].append(source)
            next_song = song_links.get(next_song[0])

        embed = discord.Embed(
            colour=settings.embed_type('accept'),
            description=f"Added playlist `{playlist}` to queue")
        await ctx.send(embed=embed)

    @commands.command()
    @perms.check()
    async def stop(self, ctx):
        """Stops and clears the queue"""
        # Check if in a voice channel
        status = await self._check_music_status(ctx, ctx.guild)
        if not status:
            return

        # Stops and clears the queue
        self.skip_toggle[ctx.guild.id] = True
        self.song_queue[ctx.guild.id].clear()
        ctx.voice_client.stop()
        embed = discord.Embed(colour=settings.embed_type('accept'), description="Music has been stopped & queue has been cleared")
        await ctx.send(embed=embed)

    @commands.command()
    @perms.check()
    async def resume(self, ctx):
        """Resumes music if paused"""
        status = await self._check_music_status(ctx, ctx.guild)
        if not status:
            return

        # Check if music is paused
        if not ctx.voice_client.is_paused():
            embed = discord.Embed(colour=settings.embed_type('warn'), description="Music isn't paused")
            await ctx.send(embed=embed)
            return

        # Resumes music playback
        ctx.voice_client.resume()
        embed = discord.Embed(colour=settings.embed_type('accept'), description="Music has been resumed")
        await ctx.send(embed=embed)

    @commands.command()
    @perms.check()
    async def pause(self, ctx):
        """Pauses the music"""
        status = await self._check_music_status(ctx, ctx.guild)
        if not status:
            return

        # Check if music is paused
        if ctx.voice_client.is_paused():
            embed = discord.Embed(colour=settings.embed_type('warn'), description="Music is already paused")
            await ctx.send(embed=embed)
            return

        # Pauses music playback
        ctx.voice_client.pause()
        embed = discord.Embed(colour=settings.embed_type('accept'), description="Music has been paused")
        await ctx.send(embed=embed)

    @commands.command()
    @perms.check()
    async def skip(self, ctx):
        """Skip the current song and play the next song"""
        status = await self._check_music_status(ctx, ctx.guild)
        if not status:
            return

        # Check if there's queue is empty
        if len(self.song_queue[ctx.guild.id]) <= 1:
            embed = discord.Embed(colour=settings.embed_type('warn'), description="There's nothing in the queue after this")
            await ctx.send(embed=embed)
            return

        # Stop current song and flag that it has been skipped
        self.skip_toggle[ctx.guild.id] = True
        ctx.voice_client.stop()

    @commands.command()
    @perms.check()
    async def loop(self, ctx):
        """Loop the currently playing song"""
        status = await self._check_music_status(ctx, ctx.guild)
        if not status:
            return

        # Disable loop if enabled
        if self.loop_toggle[ctx.guild.id]:
            self.loop_toggle[ctx.guild.id] = False
            embed = discord.Embed(colour=settings.embed_type('accept'), description=f"Loop disabled")
            await ctx.send(embed=embed)
            return

        # Enable loop if disabled
        self.loop_toggle[ctx.guild.id] = True
        embed = discord.Embed(colour=settings.embed_type('accept'), description=f"Loop enabled")
        await ctx.send(embed=embed)
        return

    @commands.command()
    @perms.check()
    async def queue(self, ctx):
        """List the current song queue"""
        status = await self._check_music_status(ctx, ctx.guild)
        if not status:
            return

        # Notify user if nothing is in the queue
        if not self.song_queue[ctx.guild.id]:
            embed = discord.Embed(colour=settings.embed_type('warn'), description=f"There's nothing in the queue right now")
            await ctx.send(embed=embed)
            return
        
        # Output first in queue as currently playing
        embed = discord.Embed(colour=settings.embed_type('info'))
        image = discord.File(settings.embed_icons("music"), filename="image.png")
        embed.set_author(name="Music Queue", icon_url="attachment://image.png")
        duration = await self._get_duration(self.song_queue[ctx.guild.id][0].duration)
        current_time = int(time() - self.start_time[ctx.guild.id])
        current_time = await self._get_duration(current_time)

        # Set header depending on if looping or not, and whether to add a spacer
        queue_status = False
        if self.loop_toggle[ctx.guild.id]:
            header = "Currently Playing (Looping)"
        else:
            header = "Currently Playing"
        if len(self.song_queue[ctx.guild.id]) > 1:
            queue_status = True
            spacer = "\u200B"
        else:
            spacer = ""
        embed.add_field(
        name=header,
        value=f"{self.song_queue[ctx.guild.id][0].title} `{current_time}/{duration}` \n{spacer}")
        
        # List remaining songs in queue plus total duration
        if queue_status:
            queue_info = []

            total_duration = -self.song_queue[ctx.guild.id][0].duration
            for song in self.song_queue[ctx.guild.id]:
                total_duration += song.duration

            for index, song in enumerate(islice(self.song_queue[ctx.guild.id], 1, 11)):
                duration = await self._get_duration(song.duration)
                queue_info.append(f"{index + 1}. {song.title} `{duration}`")
            
            # Omit songs past 10 and just display amount instead
            if len(self.song_queue[ctx.guild.id]) > 11:
                queue_info.append(f"`+{len(self.song_queue[ctx.guild.id]) - 11} more in queue`")

            # Output results to chat
            duration = await self._get_duration(total_duration)
            queue_output = '\n'.join(queue_info)
            embed.add_field(
                name=f"Queue  `{duration}`",
                value=queue_output, inline=False)
        await ctx.send(file=image, embed=embed)

    @commands.group()
    @perms.check()
    async def playlist(self, ctx):
        """Configure music playlists"""
        if ctx.invoked_subcommand is None:
            embed = discord.Embed(colour=settings.embed_type('warn'), description="Please specify a valid subcommand: `create/destroy/add/remove/list`")
            await ctx.send(embed=embed)

    @playlist.command(name='create')
    @perms.check()
    async def createplaylist(self, ctx, *, playlist):
        """Create a new playlist"""
        # Cancel if playlist linked to server already exists in db
        playlists = await self._get_playlists(ctx)
        if playlist in playlists:
            embed = discord.Embed(
                colour=settings.embed_type('warn'),
                description=f"Playlist `{playlist}` already exists")
            await ctx.send(embed=embed)
            return

        # Add playlist to database
        db = sqlite3.connect(settings.data + 'spacecat.db')
        cursor = db.cursor()
        values = (playlist, ctx.guild.id)
        cursor.execute(
            'INSERT INTO playlist(name, server_id) VALUES (?,?)', values)
        db.commit()
        db.close()

        embed = discord.Embed(
            colour=settings.embed_type('accept'),
            description=f"Playlist `{playlist}` has been created")
        await ctx.send(embed=embed)

    @playlist.command(name='destroy')
    @perms.check()
    async def destroyplaylist(self, ctx, *, playlist):
        """Deletes an existing playlist"""
        # Cancel if playlist doesn't exist in db
        playlists = await self._get_playlists(ctx)
        if playlist not in playlists:
            embed = discord.Embed(
                colour=settings.embed_type('warn'),
                description=f"Playlist `{playlist}` doesn't exist")
            await ctx.send(embed=embed)
            return

        # Add playlist to database
        db = sqlite3.connect(settings.data + 'spacecat.db')
        cursor = db.cursor()
        values = (playlist, ctx.guild.id)
        cursor.execute(
            'DELETE FROM playlist WHERE name=? AND server_id=?', values)
        db.commit()
        db.close()

        embed = discord.Embed(
            colour=settings.embed_type('accept'),
            description=f"Playlist `{playlist}` has been destroyed")
        await ctx.send(embed=embed)

    @playlist.command(name='add')
    @perms.check()
    async def addplaylist(self, ctx, playlist, url):
        """Adds a song to a playlist"""
        # Cancel if playlist doesn't exist
        playlists = await self._get_playlists(ctx)
        if playlist not in playlists:
            embed = discord.Embed(
                colour=settings.embed_type('warn'),
                description=f"Playlist `{playlist}` doesn't exist")
            await ctx.send(embed=embed)
            return

        # First song in playlist has no previous song
        playlist_id, songs = await self._get_songs(ctx, playlist)
        if not songs:
            previous_song = None

        # Check if any song id exists as a previous id to determine if it is
        # the last song in the playlist
        else:
            song_ids = []
            previous_ids = []
            for song in songs:
                song_ids.append(song[0])
                previous_ids.append(song[4])

            previous_song = list(set(song_ids) - set(previous_ids))[0]

        # Add song to end of playlist
        source = await YTDLSource.from_url(url)
        db = sqlite3.connect(settings.data + 'spacecat.db')
        cursor = db.cursor()
        values = (
            source.title, source.duration, source.webpage_url,
            previous_song, playlist_id)
        cursor.execute(
            'INSERT INTO playlist_music'
            '(title, length, url, previous_song, playlist_id) '
            'VALUES (?,?,?,?,?)', values)
        db.commit()
        db.close()

        embed = discord.Embed(
            colour=settings.embed_type('accept'),
            description=f"`{source.title}` has been added to playlist `{playlist}``")
        await ctx.send(embed=embed)
    
    def _next(self, ctx):
        # If looping, grab source from url again
        if self.loop_toggle[ctx.guild.id] and not self.skip_toggle[ctx.guild.id]:
            get_source = YTDLSource.from_url(self.song_queue[ctx.guild.id][0].url)
            coroutine = asyncio.run_coroutine_threadsafe(get_source, self.bot.loop)
            source = coroutine.result()
            self.start_time[ctx.guild.id] = time()
            ctx.voice_client.play(source, after=lambda e: self._next(ctx))
            return

        # Disable skip toggle to indicate that a skip has been completed
        if self.skip_toggle[ctx.guild.id]:
            self.skip_toggle[ctx.guild.id] = False

        # Remove first in queue. Exception used for stop command clearing queue.
        try:
            self.song_queue[ctx.guild.id].pop(0)
        except IndexError:
            return

        # Play the new first song in list
        if self.song_queue[ctx.guild.id]:
            self.start_time[ctx.guild.id] = time()
            ctx.voice_client.play(self.song_queue[ctx.guild.id][0], after=lambda e: self._next(ctx))
            return

    # Format duration based on what values there are
    async def _get_duration(self, seconds):
        try:
            duration = strftime("%H:%M:%S", gmtime(seconds)).lstrip("0:")
            if len(duration) < 2:
                duration = f"0:0{duration}"
            elif len(duration) < 3:
                duration = f"0:{duration}"
            return duration
        except:
            return "N/A"

    async def _add_server_keys(self, server):
        self.song_queue = {server.id: []}
        self.loop_toggle = {server.id: False}
        self.skip_toggle = {server.id: False}

    async def _remove_server_keys(self, server):
        self.song_queue.pop(server.id, None)
        self.loop_toggle.pop(server.id, None)
        self.skip_toggle.pop(server.id, None)

    async def _check_music_status(self, ctx, server):
        try:
            self.loop_toggle[server.id]
            return True
        except KeyError:
            embed = discord.Embed(
                colour=settings.embed_type('warn'),
                description="I need to be in a voice channel to execute music "
                "commands. \nUse **!join** or **!play** to connect me to a channel")
            await ctx.send(embed=embed)
            return False

    async def _get_playlists(self, ctx):
        db = sqlite3.connect(settings.data + 'spacecat.db')
        db.row_factory = lambda cursor, row: row[0]
        cursor = db.cursor()
        values = (ctx.guild.id,)
        cursor.execute(
            'SELECT name FROM playlist WHERE server_id=?', values)
        playlists = cursor.fetchall()
        db.close()
        return playlists

    async def _get_songs(self, ctx, playlist):
        db = sqlite3.connect(settings.data + 'spacecat.db')
        #db.row_factory = lambda cursor, row: row[0]
        cursor = db.cursor()

        # Get playlist id from name
        values = (playlist, ctx.guild.id)
        cursor.execute(
            'SELECT id FROM playlist WHERE name=? AND server_id=?', values)
        playlist_id = cursor.fetchone()[0]

        # Get list of all songs in playlist
        values = (playlist_id,)
        cursor.execute(
            'SELECT * FROM playlist_music WHERE playlist_id=?', values)
        songs = cursor.fetchall()
        db.close()
        return playlist_id, songs


def setup(bot):
    bot.add_cog(Alexa(bot))
