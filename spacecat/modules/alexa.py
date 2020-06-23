import asyncio
from itertools import islice
import os
import random
import re
import shutil
import sqlite3
from time import gmtime, strftime, time

import discord
from discord.ext import commands, tasks
import youtube_dl
from bs4 import BeautifulSoup as bs
import requests
import toml

from spacecat.helpers import constants
from spacecat.helpers import perms


youtube_dl.utils.bug_reports_message = lambda: ''


class VideoTooLongError(ValueError):
    pass


class VideoUnavailableError(ValueError):
    pass


class YTDLLogger(object):
    def debug(self, msg):
        pass

    def warning(self, msg):
        pass

    def error(self, msg):
        pass


ytdl_format_options = {
    'format': 'bestaudio/best',
    'restrictfilenames': True,
    'noplaylist': True,
    'nocheckcertificate': True,
    'ignoreerrors': True,
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'auto',
    'source_address': '0.0.0.0',
    'youtube_include_dash_manifest': False,
    'logger': YTDLLogger()
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

        try:
            if 'entries' in data:
                # take first item from a playlist
                data = data['entries'][0]
        except TypeError:
            return

        return cls(discord.FFmpegPCMAudio(data['url'], **ffmpeg_options, before_options=before_args), data=data)


class Alexa(commands.Cog):
    """Play some funky music in a voice chat"""
    def __init__(self, bot):
        self.bot = bot
        self.song_queue = {}
        self.song_start_time = {}
        self.song_pause_time = {}
        self.loop_toggle = {}
        self.skip_toggle = {}
        self.disconnect_time = {}
        self._disconnect_timer.start()

    @commands.Cog.listener()
    async def on_ready(self):
        # Add config keys
        config = toml.load(constants.DATA_DIR + 'config.toml')
        if 'music' not in config:
            config['music'] = {}
        if 'auto_disconnect' not in config['music']:
            config['music']['auto_disconnect'] = True
        if 'disconnect_time' not in config['music']:
            config['music']['disconnect_time'] = 300
        with open(constants.DATA_DIR + "config.toml", "w") as config_file:
            toml.dump(config, config_file)
        
        # Create playlist table if it don't exist
        db = sqlite3.connect(constants.DATA_DIR + 'spacecat.db')
        cursor = db.cursor()
        cursor.execute('PRAGMA foreign_keys = ON')

        cursor.execute(
            'CREATE TABLE IF NOT EXISTS playlist'
            '(id INTEGER PRIMARY KEY, name TEXT, description TEXT,'
            'server_id INTEGER)')

        cursor.execute(
            'CREATE TABLE IF NOT EXISTS playlist_music'
            '(id INTEGER PRIMARY KEY, title TEXT, duration INTEGER, url TEXT,'
            'previous_song INTEGER, playlist_id INTEGER,'
            'FOREIGN KEY(playlist_id) REFERENCES playlist(id))')

        db.commit()
        db.close()

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        """Disconnect the bot if the last user leaves the channel"""
        # Check if bot voice client isn't active
        voice_client = member.guild.voice_client
        if not voice_client:
            return

        # Check if auto disconnect is disabled
        config = toml.load(constants.DATA_DIR + 'config.toml')
        if not config['music']['auto_disconnect']:
            return

        # Check if user isn't in same channel or not a disconnect/move event
        if (voice_client.channel != before.channel or
                before.channel == after.channel):
            return

        # Disconnect if the bot is the only user left
        if len(voice_client.channel.members) < 2:
            await voice_client.disconnect()

    @commands.command()
    @perms.check()
    async def join(self, ctx, *, channel: discord.VoiceChannel = None):
        """Joins a voice channel"""
        # Get user's current channel if no channel is specified
        if channel == None:
            try:
                channel = ctx.author.voice.channel
            except AttributeError:
                embed = discord.Embed(colour=constants.EMBED_TYPE['warn'], description=f"You must specify or be in a voice channel")
                await ctx.send(embed=embed)
                return

        # Connect if not in a voice channel
        await self._add_server_keys(ctx.guild)
        if ctx.voice_client is None:
            await channel.connect()
            return

        # Check if the specified voice channel is the same as the current channel
        if channel == ctx.voice_client.channel:
            embed = discord.Embed(colour=constants.EMBED_TYPE['warn'], description=f"I'm already in that voice channel")
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

        # Instantly play song if no song currently playing
        # Send to queue_add function if there is a song playing
        if len(self.song_queue[ctx.guild.id]) > 0:
            await ctx.invoke(self.queue_add, url)
            return
        else:
            try:
                source, song_name = await self._process_song(ctx, url)
            except VideoTooLongError:
                embed = discord.Embed(
                    colour=constants.EMBED_TYPE['warn'],
                    description="Woops, that video is too long")
                await ctx.send(embed=embed)
                return
            except VideoUnavailableError:
                embed = discord.Embed(
                    colour=constants.EMBED_TYPE['warn'],
                    description="Woops, that video is unavailable")
                await ctx.send(embed=embed)
                return
            self.song_queue[ctx.guild.id].append(source)
            self.song_start_time[ctx.guild.id] = time()
            ctx.voice_client.play(source, after=lambda e: self._next(ctx))
            embed = discord.Embed(
                colour=constants.EMBED_TYPE['accept'],
                description=f"Now playing {song_name}")

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
                colour=constants.EMBED_TYPE['warn'],
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
        embed = discord.Embed(colour=constants.EMBED_TYPE['info'])
        image = discord.File(constants.EmbedIcon.MUSIC.value, filename="image.png")
        embed.set_author(name=f"Search Query", icon_url="attachment://image.png")
        results_output = '\n'.join(results_format)
        embed.add_field(
            name=f"Results for '{search}'",
            value=results_output, inline=False)
        msg = await ctx.send(file=image, embed=embed)

        # Add reaction button for every result
        reactions = []
        for index in range(len(results_format)):
            emoji = constants.NUM_TO_EMOJI[index + 1]
            await msg.add_reaction(emoji)
            reactions.append(emoji)

        # Check if the requester selects a valid reaction
        def reaction_check(reaction, user):
            return user == ctx.author and str(reaction) in reactions

        # Request reaction within timeframe
        try:
            reaction, _ = await self.bot.wait_for(
                'reaction_add', timeout=30.0, check=reaction_check)
        except asyncio.TimeoutError:
            embed = discord.Embed(
                    colour=constants.EMBED_TYPE['warn'],
                    description=f"Song selection timed out.")
            embed.set_author(name=f"Search Query", icon_url="attachment://image.png")
            await msg.clear_reactions()
            await msg.edit(file=None, embed=embed)
            return

        # Play selected song
        number = constants.EMOJI_TO_NUM[str(reaction)]
        selected_song = urls[number - 1]
        await ctx.invoke(self.play, url=selected_song)
        
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
        embed = discord.Embed(colour=constants.EMBED_TYPE['accept'], description="Music has been stopped & queue has been cleared")
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
            embed = discord.Embed(colour=constants.EMBED_TYPE['warn'], description="Music isn't paused")
            await ctx.send(embed=embed)
            return

        # Resumes music playback
        ctx.voice_client.resume()
        self.song_start_time[ctx.guild.id] = time() - self.song_pause_time[ctx.guild.id]
        self.song_pause_time[ctx.guild.id] = None
        embed = discord.Embed(colour=constants.EMBED_TYPE['accept'], description="Music has been resumed")
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
            embed = discord.Embed(colour=constants.EMBED_TYPE['warn'], description="Music is already paused")
            await ctx.send(embed=embed)
            return

        # Pauses music playback
        config = toml.load(constants.DATA_DIR + 'config.toml')
        self.disconnect_time[ctx.guild.id] = time() \
            + config['music']['disconnect_time']
        ctx.voice_client.pause()
        self.song_pause_time[ctx.guild.id] = time() - self.song_start_time[ctx.guild.id]
        embed = discord.Embed(colour=constants.EMBED_TYPE['accept'], description="Music has been paused")
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
            embed = discord.Embed(colour=constants.EMBED_TYPE['warn'], description="There's nothing in the queue after this")
            await ctx.send(embed=embed)
            return

        # Stop current song and flag that it has been skipped
        self.skip_toggle[ctx.guild.id] = True
        ctx.voice_client.stop()

    @commands.command()
    @perms.check()
    async def shuffle(self, ctx):
        """Randomly moves the contents of the queue around"""
        # Alert if queue is empty
        if len(self.song_queue[ctx.guild.id]) < 2:
            embed = discord.Embed(
                colour=constants.EMBED_TYPE['warn'],
                description=f"There's nothing in the queue to shuffle")
            await ctx.send(embed=embed)
            return

        # Create temp queue excluding currently playing song to shuffle
        temp_queue = self.song_queue[ctx.guild.id][1:]
        random.shuffle(temp_queue)
        self.song_queue[ctx.guild.id][1:] = temp_queue

        # Output result to chat
        embed = discord.Embed(
            colour=constants.EMBED_TYPE['accept'],
            description=f"Queue has been shuffled")
        await ctx.send(embed=embed)
        return

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
            embed = discord.Embed(colour=constants.EMBED_TYPE['accept'], description=f"Loop disabled")
            await ctx.send(embed=embed)
            return

        # Enable loop if disabled
        self.loop_toggle[ctx.guild.id] = True
        embed = discord.Embed(colour=constants.EMBED_TYPE['accept'], description=f"Loop enabled")
        await ctx.send(embed=embed)
        return

    @commands.group(invoke_without_command=True)
    @perms.check()
    async def queue(self, ctx, arg: int=1):
        """View and modify the current song queue. Defaults to the list subcommand."""
        # Run the queue list subcommand if no subcommand is specified
        await ctx.invoke(self.queue_list, arg)

    @queue.command(name='list')
    @perms.check()
    async def queue_list(self, ctx, page: int=1):
        """List the current song queue"""
        status = await self._check_music_status(ctx, ctx.guild)
        if not status:
            return

        # Notify user if nothing is in the queue
        if not self.song_queue[ctx.guild.id]:
            embed = discord.Embed(colour=constants.EMBED_TYPE['warn'], description=f"There's nothing in the queue right now")
            await ctx.send(embed=embed)
            return

        # Output first in queue as currently playing
        embed = discord.Embed(colour=constants.EMBED_TYPE['info'])
        image = discord.File(constants.EmbedIcon.MUSIC.value, filename="image.png")
        embed.set_author(name="Music Queue", icon_url="attachment://image.png")
        duration = await self._get_duration(self.song_queue[ctx.guild.id][0].duration)
        if not self.song_pause_time[ctx.guild.id]:
            current_time = int(time() - self.song_start_time[ctx.guild.id])
        else:
            current_time = int(self.song_pause_time[ctx.guild.id])
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

            # Modify page variable to get every ten results
            page -= 1
            if page > 0: page = page * 10

            total_duration = -self.song_queue[ctx.guild.id][0].duration
            for song in self.song_queue[ctx.guild.id]:
                total_duration += song.duration

            for index, song in enumerate(islice(self.song_queue[ctx.guild.id], page + 1, page + 11)):
                duration = await self._get_duration(song.duration)
                queue_info.append(f"{page + index + 1}. {song.title} `{duration}`")

            # Alert if no songs are on the specified page
            if page > 0 and not queue_info:
                embed = discord.Embed(
                    colour=constants.EMBED_TYPE['warn'],
                    description=f"There are no songs on that page")
                await ctx.send(embed=embed)
                return

            # Omit songs past 10 and just display amount instead
            if len(self.song_queue[ctx.guild.id]) > page + 11:
                queue_info.append(f"`+{len(self.song_queue[ctx.guild.id]) - 11 - page} more in queue`")

            # Output results to chat
            duration = await self._get_duration(total_duration)
            queue_output = '\n'.join(queue_info)
            embed.add_field(
                name=f"Queue  `{duration}`",
                value=queue_output, inline=False)
        await ctx.send(file=image, embed=embed)

    @queue.command(name='move')
    @perms.check()
    async def queue_move(self, ctx, original_pos: int, new_pos: int):
        """Move a song to a different position in the queue"""
        status = await self._check_music_status(ctx, ctx.guild)
        if not status:
            return

        # Try to remove song from queue using the specified index
        try:
            if original_pos < 1:
                raise IndexError('Position can\'t be be less than 1')
            song = self.song_queue[ctx.guild.id][original_pos]
        except IndexError:
            embed = discord.Embed(
                colour=constants.EMBED_TYPE['warn'],
                description=f"There's no song at that position")
            await ctx.send(embed=embed)
            return

        # Move song into new position in queue
        if not 1 <= new_pos < len(self.song_queue[ctx.guild.id]):
            embed = discord.Embed(
                colour=constants.EMBED_TYPE['warn'],
                description=f"You can't move the song into that position")
            await ctx.send(embed=embed)
            return
        self.song_queue[ctx.guild.id].pop(original_pos)
        self.song_queue[ctx.guild.id].insert(new_pos, song)
            
        # Output result to chat
        duration = await self._get_duration(song.duration)
        embed = discord.Embed(
            colour=constants.EMBED_TYPE['accept'],
            description=f"[{song.title}]({song.webpage_url}) "
            f"`{duration}` has been moved from position #{original_pos} "
            f"to position #{new_pos}")
        await ctx.send(embed=embed)

    @queue.command(name='add')
    @perms.check()
    async def queue_add(self, ctx, url):
        """Adds a song to the queue"""
        # Alert if too many songs in queue
        if len(self.song_queue[ctx.guild.id]) > 100:
            embed = discord.Embed(
                colour=constants.EMBED_TYPE['warn'],
                description="Too many songs in queue. Calm down.")
            await ctx.send(embed=embed)
            return
            
        # Add the song to the queue and output result
        try:
            source, song_name = await self._process_song(ctx, url)
        except VideoTooLongError:
                embed = discord.Embed(
                    colour=constants.EMBED_TYPE['warn'],
                    description="Woops, that video is too long")
                await ctx.send(embed=embed)
                return
        except VideoUnavailableError:
            embed = discord.Embed(
                colour=constants.EMBED_TYPE['warn'],
                description="Woops, that video is unavailable")
            await ctx.send(embed=embed)
            return
        self.song_queue[ctx.guild.id].append(source)
        embed = discord.Embed(
            colour=constants.EMBED_TYPE['accept'],
            description=f"Added {song_name} to " 
            f"#{len(self.song_queue[ctx.guild.id]) - 1} in queue")
        await ctx.send(embed=embed)
        return
        
    @queue.command(name='remove')
    @perms.check()
    async def queue_remove(self, ctx, index: int):
        """Remove a song from the queue"""
        status = await self._check_music_status(ctx, ctx.guild)
        if not status:
            return

        # Try to remove song from queue using the specified index
        try:
            if index < 1:
                raise IndexError('Position can\'t be less than 1')
            song = self.song_queue[ctx.guild.id][index]
            self.song_queue[ctx.guild.id].pop(index)
        except IndexError:
            embed = discord.Embed(
                colour=constants.EMBED_TYPE['warn'],
                description=f"That's an invalid queue position")
            await ctx.send(embed=embed)
            return
        
        # Output result to chat
        duration = await self._get_duration(song.duration)
        embed = discord.Embed(
            colour=constants.EMBED_TYPE['accept'],
            description=f"[{song.title}]({song.webpage_url}) "
            f"`{duration}` has been removed from position #{index} "
            "of the queue")
        await ctx.send(embed=embed)

    @queue.command(name='clear')
    @perms.check()
    async def queue_clear(self, ctx):
        """Clears the entire queue"""
        status = await self._check_music_status(ctx, ctx.guild)
        if not status:
            return

        # Try to remove all but the currently playing song from the queue
        if len(self.song_queue[ctx.guild.id]) < 2:
            embed = discord.Embed(
                colour=constants.EMBED_TYPE['warn'],
                description=f"There's nothing in the queue to clear")
            await ctx.send(embed=embed)
            return
        self.song_queue[ctx.guild.id] = [self.song_queue[ctx.guild.id][0]]

        # Output result to chat
        embed = discord.Embed(
            colour=constants.EMBED_TYPE['accept'],
            description=f"All songs have been removed from the queue")
        await ctx.send(embed=embed)

    @commands.group(invoke_without_command=True)
    @perms.check()
    async def playlist(self, ctx):
        """Configure music playlists. Defaults to list subcommand."""
        # Run the queue list subcommand if no subcommand is specified
        await ctx.invoke(self.playlist_list)

    @playlist.command(name='create')
    @perms.check()
    async def playlist_create(self, ctx, *, playlist_name):
        """Create a new playlist"""
        # Limit playlist name to 30 chars
        if len(playlist_name) > 30:
            embed = discord.Embed(
                colour=constants.EMBED_TYPE['warn'],
                description=f"Playlist name is too long")
            await ctx.send(embed=embed)
            return

        # Alert if playlist with specified name already exists
        try:
            await self._get_playlist(ctx, playlist_name)
            embed = discord.Embed(
                colour=constants.EMBED_TYPE['warn'],
                description=f"Playlist `{playlist_name}` already exists")
            await ctx.send(embed=embed)
            return
        except ValueError:
            pass

        # Add playlist to database
        db = sqlite3.connect(constants.DATA_DIR + 'spacecat.db')
        cursor = db.cursor()
        values = (playlist_name, ctx.guild.id)
        cursor.execute(
            'INSERT INTO playlist(name, server_id) VALUES (?,?)', values)
        db.commit()
        db.close()

        embed = discord.Embed(
            colour=constants.EMBED_TYPE['accept'],
            description=f"Playlist `{playlist_name}` has been created")
        await ctx.send(embed=embed)

    @playlist.command(name='destroy')
    @perms.check()
    async def playlist_destroy(self, ctx, *, playlist_name):
        """Deletes an existing playlist"""
        # Alert if playlist doesn't exist in db
        try:
            playlist = await self._get_playlist(ctx, playlist_name)
        except ValueError:
            embed = discord.Embed(
                colour=constants.EMBED_TYPE['warn'],
                description=f"Playlist `{playlist_name}` doesn't exist")
            await ctx.send(embed=embed)
            return

        # Remove playlist from database and all songs linked to it
        db = sqlite3.connect(constants.DATA_DIR + 'spacecat.db')
        cursor = db.cursor()
        values = (playlist[0],)
        cursor.execute(
            'DELETE FROM playlist_music WHERE playlist_id=?', values)
        values = (playlist_name, ctx.guild.id)
        cursor.execute(
            'DELETE FROM playlist WHERE name=? AND server_id=?', values)
        db.commit()
        db.close()

        # Output result to chat
        embed = discord.Embed(
            colour=constants.EMBED_TYPE['accept'],
            description=f"Playlist `{playlist_name}` has been destroyed")
        await ctx.send(embed=embed)
    
    @playlist.command(name='description')
    @perms.check()
    async def playlist_description(self, ctx, playlist_name, *, description):
        """Sets the description for the playlist"""
        # Alert if playlist doesn't exist
        try:
            playlist = await self._get_playlist(ctx, playlist_name)
        except ValueError:
            embed = discord.Embed(
                colour=constants.EMBED_TYPE['warn'],
                description=f"Playlist `{playlist_name}` doesn't exist")
            await ctx.send(embed=embed)
            return

        # Limit playlist description to 300 chars
        if len(playlist_name) > 300:
            embed = discord.Embed(
                colour=constants.EMBED_TYPE['warn'],
                description=f"Playlist name is too long")
            await ctx.send(embed=embed)
            return

        # Rename playlist in database
        db = sqlite3.connect(constants.DATA_DIR + 'spacecat.db')
        cursor = db.cursor()
        values = (description, playlist[0],)
        cursor.execute(
            'UPDATE playlist SET description=? WHERE id=?', values)
        db.commit()
        db.close()

        # Output result to chat
        embed = discord.Embed(
            colour=constants.EMBED_TYPE['accept'],
            description=f"Description set for playlist `{playlist_name}`")
        await ctx.send(embed=embed)

    @playlist.command(name='rename')
    @perms.check()
    async def playlist_rename(self, ctx, playlist_name, new_name):
        """Rename an existing playlist"""
        # Alert if playlist doesn't exist
        try:
            playlist = await self._get_playlist(ctx, playlist_name)
        except ValueError:
            embed = discord.Embed(
                colour=constants.EMBED_TYPE['warn'],
                description=f"Playlist `{playlist_name}` doesn't exist")
            await ctx.send(embed=embed)
            return

        # Rename playlist in database
        db = sqlite3.connect(constants.DATA_DIR + 'spacecat.db')
        cursor = db.cursor()
        values = (new_name, playlist[0],)
        cursor.execute(
            'UPDATE playlist SET name=? WHERE id=?', values)
        db.commit()
        db.close()

        # Output result to chat
        embed = discord.Embed(
            colour=constants.EMBED_TYPE['accept'],
            description=f"Playlist `{playlist}` has been renamed to "
            f"`{new_name}`")
        await ctx.send(embed=embed)

    @playlist.command(name='list')
    @perms.check()
    async def playlist_list(self, ctx):
        """List all available playlists"""
        # Alert if no playlists exist
        playlists = await self._get_playlist(ctx)
        if not playlists:
            embed = discord.Embed(
                colour=constants.EMBED_TYPE['warn'],
                description=f"There are no playlists available")
            await ctx.send(embed=embed)
            return

        # Get all playlist names and duration
        playlist_names = []
        for playlist in playlists:
            songs = await self._get_songs(ctx, playlist[1])
            song_duration = 0
            for song in songs:
                song_duration += song[2]
            playlist_names.append([playlist[1], song_duration])

        # Format playlist songs into pretty list
        playlist_info = []
        for index, playlist_name in enumerate(islice(playlist_names, 0, 10)):
            duration = await self._get_duration(playlist_name[1])
            playlist_info.append(
                f"{index + 1}. {playlist_name[0]} `{duration}`")

        # Output results to chat
        embed = discord.Embed(colour=constants.EMBED_TYPE['info'])
        image = discord.File(
            constants.EmbedIcon.MUSIC.value, filename="image.png")
        embed.set_author(
            name="Music Playlists", icon_url="attachment://image.png")
        playlist_output = '\n'.join(playlist_info)
        embed.add_field(
            name=f"{len(playlists)} available",
            value=playlist_output, inline=False)
        await ctx.send(file=image, embed=embed)
        
    @playlist.command(name='add')
    @perms.check()
    async def playlist_add(self, ctx, playlist_name, *, url):
        """Adds a song to a playlist"""
        # Alert if playlist doesn't exist in db
        try:
            playlist = await self._get_playlist(ctx, playlist_name)
        except ValueError:
            embed = discord.Embed(
                colour=constants.EMBED_TYPE['warn'],
                description=f"Playlist `{playlist_name}` doesn't exist")
            await ctx.send(embed=embed)
            return

        songs = await self._get_songs(ctx, playlist_name)
        if len(songs) > 100:
            embed = discord.Embed(
                colour=constants.EMBED_TYPE['warn'],
                description="There's too many songs in the playlist. Remove"
                "some songs to be able to add more")
            await ctx.send(embed=embed)
            return

        # Get song source to add to song list
        try:
            source, _ = await self._process_song(ctx, url)
        except VideoTooLongError:
            embed = discord.Embed(
                colour=constants.EMBED_TYPE['warn'],
                description="Woops, that video is too long")
            await ctx.send(embed=embed)
            return
        except VideoUnavailableError:
            embed = discord.Embed(
                colour=constants.EMBED_TYPE['warn'],
                description="Woops, that video is unavailable")
            await ctx.send(embed=embed)
            return
        
        # Set previous song as the last song in the playlist
        if not songs:
            previous_song = None
        else:
            song_ids = []
            previous_ids = []
            for song in songs:
                song_ids.append(song[0])
                previous_ids.append(song[4])
            previous_song = list(set(song_ids) - set(previous_ids))[0]

        # Add song to playlist
        db = sqlite3.connect(constants.DATA_DIR + 'spacecat.db')
        cursor = db.cursor()
        values = (
            source.title, source.duration, source.webpage_url,
            previous_song, playlist[0])
        cursor.execute(
            'INSERT INTO playlist_music'
            '(title, duration, url, previous_song, playlist_id) '
            'VALUES (?,?,?,?,?)', values)
        db.commit()
        db.close()

        # Output result to chat
        duration = await self._get_duration(source.duration)
        embed = discord.Embed(
            colour=constants.EMBED_TYPE['accept'],
            description=f"Added [{source.title}]({source.webpage_url}) "
            f"`{duration}` to position #{len(songs) + 1} "
            f"in playlist `{playlist_name}`")
        await ctx.send(embed=embed)

    @playlist.command(name='remove')
    @perms.check()
    async def playlist_remove(self, ctx, playlist_name, index):
        """Removes a song from a playlist"""
        # Fetch songs from playlist if it exists
        try:
            songs = await self._get_songs(ctx, playlist_name)
        except ValueError:
            embed = discord.Embed(
                colour=constants.EMBED_TYPE['warn'],
                description=f"Playlist `{playlist_name}` doesn't exist")
            await ctx.send(embed=embed)
            return

        # Fetch selected song and the song after
        db = sqlite3.connect(constants.DATA_DIR + 'spacecat.db')
        cursor = db.cursor()
        selected_song = songs[int(index) - 1]
        
        # Edit next song's previous song id if it exists
        try:
            next_song = songs[int(index)]
            values = (selected_song[4], next_song[0],)
            cursor.execute(
                'UPDATE playlist_music SET previous_song=? WHERE id=?', values)
        except IndexError:
            pass
        
        # Remove selected song from playlist
        values = (selected_song[0],)
        cursor.execute(
            'DELETE FROM playlist_music WHERE id=?', values)
        db.commit()
        db.close()

        # Output result to chat
        duration = await self._get_duration(selected_song[2])
        embed = discord.Embed(
            colour=constants.EMBED_TYPE['accept'],
            description=f"[{selected_song[1]}]({selected_song[3]}) "
            f"`{duration}` has been removed from `{playlist_name}`")
        await ctx.send(embed=embed)

    @playlist.command(name='move')
    @perms.check()
    async def playlist_move(self, ctx, playlist_name, original_pos, new_pos):
        """Moves a song to a specified position in a playlist"""
        # Fetch songs from playlist if it exists
        try:
            songs = await self._get_songs(ctx, playlist_name)
        except ValueError:
            embed = discord.Embed(
                colour=constants.EMBED_TYPE['warn'],
                description=f"Playlist `{playlist_name}` does not exist")
            await ctx.send(embed=embed)
            return

        # Edit db to put selected song in other song's position
        selected_song = songs[int(original_pos) - 1]
        other_song = songs[int(new_pos) - 1]
        
        # If moving down, shift other song down the list
        if new_pos > original_pos:
            values = [(other_song[0], selected_song[0])]
            try:
                after_new_song = songs[int(new_pos)]
                values.append((selected_song[0], after_new_song[0]))
            except IndexError:
                pass
        # If moving up, shift other song up the list
        else:
            values = [
                (other_song[4], selected_song[0]),
                (selected_song[0], other_song[0])]

        # Connect the two songs beside the original song position
        try:
            after_selected_song = songs[int(original_pos)]
            values.append((selected_song[4], after_selected_song[0]))
        except IndexError:
            pass
        
        # Execute all those values
        db = sqlite3.connect(constants.DATA_DIR + 'spacecat.db')
        cursor = db.cursor()
        for value in values:
            cursor.execute(
                'UPDATE playlist_music SET previous_song=? WHERE id=?', value)
        db.commit()
        db.close()

        # Output result to chat
        duration = await self._get_duration(selected_song[2])
        embed = discord.Embed(
                colour=constants.EMBED_TYPE['accept'],
                description=f"[{selected_song[1]}]({selected_song[3]}) "
                f"`{duration}` has been moved to position #{new_pos} "
                f"in playlist `{playlist_name}`")
        await ctx.send(embed=embed)
        
    @playlist.command(name='view')
    @perms.check()
    async def playlist_view(self, ctx, playlist_name, page=1):
        """List all songs in a playlist"""
        # Fetch songs from playlist if it exists
        try:
            playlist = await self._get_playlist(ctx, playlist_name)
            songs = await self._get_songs(ctx, playlist_name)
        except ValueError:
            embed = discord.Embed(
                colour=constants.EMBED_TYPE['warn'],
                description=f"Playlist `{playlist_name}` does not exist")
            await ctx.send(embed=embed)
            return

        # Modify page variable to get every ten results
        page -= 1
        if page > 0: page = page * 10

        # Get total duration
        total_duration = 0
        for song in songs:
            total_duration += song[2]

        # Make a formatted list of 10 aliases based on the page
        formatted_songs = []
        for index, song in enumerate(islice(songs, page, page + 10)):
            # Cut off song name to 90 chars
            if len(song[1]) > 90:
                song_name = f"{song[1][:87]}..." 
            else:
                song_name = song[1]

            duration = await self._get_duration(song[2])
            formatted_songs.append(
                f"{page + index + 1}. [{song_name}]({song[3]}) `{duration}`")

        # Alert if no songs are on the specified page
        if not formatted_songs:
            embed = discord.Embed(
                colour=constants.EMBED_TYPE['warn'],
                description=f"There are no songs on that page")
            await ctx.send(embed=embed)
            return

        # Output results to chat
        embed = discord.Embed(colour=constants.EMBED_TYPE['info'])
        image = discord.File(constants.EmbedIcon.MUSIC.value, filename="image.png")
        embed.set_author(
            name=f"Playlist '{playlist_name}' Contents",
            icon_url="attachment://image.png")
        if playlist[2] and page == 0:
            embed.description = playlist[2]
        formatted_duration = await self._get_duration(total_duration)
        playlist_music_output = '\n'.join(formatted_songs)
        embed.add_field(
            name=f"{len(songs)} songs available `{formatted_duration}`",
            value=playlist_music_output, inline=False)
        await ctx.send(file=image, embed=embed)

    @playlist.command(name='play')
    @perms.check()
    async def playlist_play(self, ctx, playlist):
        """Play from a locally saved playlist"""
        # Join user's voice channel if not in one already
        if ctx.voice_client is None:
            await ctx.invoke(self.join)

            # End function if bot failed to join a voice channel.
            if ctx.voice_client is None:
                return

        # Get all songs in playlist
        try:
            songs = await self._get_songs(ctx, playlist)
        except TypeError:
            embed = discord.Embed(
                colour=constants.EMBED_TYPE['warn'],
                description=f"Playlist `{playlist}` does not exist")
            await ctx.send(embed=embed)
            return
        song_links = {}
        for song in songs:
            song_links[song[4]] = [song[0], song]

        # Play first song if no song is currently playing
        next_song = song_links.get(None)
        unavailable_songs = []
        index = 0
        if len(self.song_queue[ctx.guild.id]) == 0: 
            # Loop until available playlist song is found  
            while True:
                index += 1
                try:
                    source, _ = await self._process_song(ctx, next_song[1][3])
                except VideoUnavailableError:
                    duration = await self._get_duration(next_song[1][2])
                    unavailable_songs.append(
                        f"{index}. [{next_song[1][1]}]({next_song[1][3]}) "
                        f"`{duration}`")
                    continue
                finally:
                    next_song = song_links.get(next_song[0])
                self.song_queue[ctx.guild.id].append(source)
                self.song_start_time[ctx.guild.id] = time()
                ctx.voice_client.play(source, after=lambda e: self._next(ctx))
                embed = discord.Embed(
                    colour=constants.EMBED_TYPE['accept'],
                    description=f"Now playing playlist `{playlist}`")
                await ctx.send(embed=embed)
                break
        else:
            embed = discord.Embed(
            colour=constants.EMBED_TYPE['accept'],
            description=f"Added playlist `{playlist}` to queue")
            await ctx.send(embed=embed)

        # Add remaining songs to queue
        while next_song:
            index += 1
            try:
                source, _ = await self._process_song(ctx, next_song[1][3])
            except VideoUnavailableError:
                duration = await self._get_duration(next_song[1][2])
                unavailable_songs.append(
                    f"{index}. [{next_song[1][1]}]({next_song[1][3]}) "
                    f"`{duration}`")
                continue
            finally:
                next_song = song_links.get(next_song[0])
            self.song_queue[ctx.guild.id].append(source)

        # Alert user of unavailable songs
        if unavailable_songs:
            for index, song in enumerate(unavailable_songs):
                song_format = "\n".join(unavailable_songs)
            embed = discord.Embed(
                colour=constants.EMBED_TYPE['warn'],
                description=f"These songs in playlist `{playlist}` "
                f"are unavailable: \n{song_format}")
            await ctx.send(embed=embed)

    @commands.group(invoke_without_command=True)
    @perms.exclusive()
    async def musicsettings(self, ctx):
        """Configure music playlists. Defaults to list subcommand."""
        # Run the queue list subcommand if no subcommand is specified
        await ctx.send("Please specify a valid subcommand.")

    @musicsettings.command(name='autodisconnect')
    @perms.exclusive()
    async def musicsettings_autodisconnect(self, ctx):
        """
        Toggles if the bot should auto disconnect from a voice channel
        Turning this value on will allow the bot to disconnect after
        a set amount of time after a song has finished playing, or if
        all users have left the voice channel. This saves on system
        resources.
        """
        config = toml.load(constants.DATA_DIR + 'config.toml')

        # Toggle auto_disconnect config setting
        if config['music']['auto_disconnect']:
            config['music']['auto_disconnect'] = False
            result_text = "disabled"
        else:
            config['music']['auto_disconnect'] = True
            result_text = "enabled"

        with open(constants.DATA_DIR + "config.toml", "w") as config_file:
            toml.dump(config, config_file)

        embed = discord.Embed(
            colour=constants.EMBED_TYPE['accept'],
            description=f"Music player auto disconnect {result_text}")
        await ctx.send(embed=embed)

    @musicsettings.command(name='disconnecttime')
    @perms.exclusive()
    async def musicsettings_disconnecttime(self, ctx, seconds: int):
        """
        Sets a time for when the bot should disconnect from voice
        A time in seconds specifies when the bot should disconnect after
        the bot is not playing any songs if auto disconnect has been
        enabled.
        """
        config = toml.load(constants.DATA_DIR + 'config.toml')

        # Set disconnect_time config variable
        config['music']['disconnect_time'] = seconds
        with open(constants.DATA_DIR + "config.toml", "w") as config_file:
            toml.dump(config, config_file)

        embed = discord.Embed(
            colour=constants.EMBED_TYPE['accept'],
            description=f"Music player auto disconnect timer set to "
                f"{seconds} seconds")
        await ctx.send(embed=embed)
        return

    def _next(self, ctx):
        config = toml.load(constants.DATA_DIR + 'config.toml')
        self.disconnect_time[ctx.guild.id] = time() \
            + config['music']['disconnect_time']
        # If looping, grab source from url again
        if self.loop_toggle[ctx.guild.id] and not self.skip_toggle[ctx.guild.id]:
            get_source = YTDLSource.from_url(self.song_queue[ctx.guild.id][0].url)
            coroutine = asyncio.run_coroutine_threadsafe(get_source, self.bot.loop)
            source = coroutine.result()
            self.song_start_time[ctx.guild.id] = time()
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
            self.song_start_time[ctx.guild.id] = time()
            ctx.voice_client.play(self.song_queue[ctx.guild.id][0], after=lambda e: self._next(ctx))
            return

    # Format duration based on what values there are
    async def _get_duration(self, seconds):
        try:
            duration = strftime("%H:%M:%S", gmtime(seconds)).lstrip("0:")
            if len(duration) < 1:
                duration = "0:00"
            if len(duration) < 2:
                duration = f"0:0{duration}"
            elif len(duration) < 3:
                duration = f"0:{duration}"
            return duration
        except:
            return "N/A"

    async def _add_server_keys(self, server):
        config = toml.load(constants.DATA_DIR + 'config.toml')
        self.song_queue = {server.id: []}
        self.loop_toggle = {server.id: False}
        self.skip_toggle = {server.id: False}
        self.song_start_time = {server.id: None}
        self.song_pause_time = {server.id: None}
        self.disconnect_time = {server.id: time() +
            config['music']['disconnect_time']}

    async def _remove_server_keys(self, server):
        self.song_queue.pop(server.id, None)
        self.loop_toggle.pop(server.id, None)
        self.skip_toggle.pop(server.id, None)
        self.song_start_time.pop(server.id, None)
        self.song_pause_time.pop(server.id, None)
        self.disconnect_time = {server.id, None}

    async def _check_music_status(self, ctx, server):
        try:
            self.loop_toggle[server.id]
            return True
        except KeyError:
            embed = discord.Embed(
                colour=constants.EMBED_TYPE['warn'],
                description="I need to be in a voice channel to execute music "
                "commands. \nUse **!join** or **!play** to connect me to a channel")
            await ctx.send(embed=embed)
            return False

    async def _get_playlist(self, ctx, playlist_name=None):
        """Gets playlist data from name"""
        db = sqlite3.connect(constants.DATA_DIR + 'spacecat.db')
        cursor = db.cursor()

        # Fetch all or specific playlist depending on argument
        if not playlist_name:
            values = (ctx.guild.id,)
            cursor.execute(
                'SELECT * FROM playlist WHERE server_id=?', values)
            playlist = cursor.fetchall()
        else:
            values = (playlist_name, ctx.guild.id)
            cursor.execute(
                'SELECT * FROM playlist WHERE name=? AND server_id=?', values)
            playlist = cursor.fetchone()
            if playlist is None:
                raise ValueError('That playlist is unavailable')

        db.close()
        return playlist

    async def _get_songs(self, ctx, playlist_name):
        """Gets playlist songs from name"""
        playlist = await self._get_playlist(ctx, playlist_name)
        if playlist is None:
            raise ValueError('That playlist is unavailable')

        # Get list of all songs in playlist
        db = sqlite3.connect(constants.DATA_DIR + 'spacecat.db')
        cursor = db.cursor()
        values = (playlist[0],)
        cursor.execute(
            'SELECT * FROM playlist_music WHERE playlist_id=?', values)
        songs = cursor.fetchall()
        db.close()
        
        # Use dictionary to pair songs with the next song
        song_links = {}
        for song in songs:
            song_links[song[4]] = [song[0], song]

        # Order playlist songs
        ordered_songs = []
        next_song = song_links.get(None)
        while next_song is not None:
            ordered_songs.append(next_song[1])
            next_song = song_links.get(next_song[0])

        return ordered_songs

    async def _process_song(self, ctx, url):
        """Grab audio source from YouTube and check if longer than 3 hours"""
        source = await YTDLSource.from_url(url)

        if not source:
            raise VideoUnavailableError('Specified song is unavailable')

        if source.duration >= 10800:
            raise VideoTooLongError('Specified song is longer than 3 hours')
            
        duration = await self._get_duration(source.duration)
        name = f"[{source.title}]({source.webpage_url}) `{duration}`"
        return source, name

    @tasks.loop(seconds=30)
    async def _disconnect_timer(self):
        config = toml.load(constants.DATA_DIR + 'config.toml')
        for server_id in self.disconnect_time:
            server = await self.bot.fetch_guild(server_id)
            voice_client = server.voice_client
            if (time() > self.disconnect_time[server_id] and
                    not voice_client.is_playing() and
                    config['music']['auto_disconnect']):
                await voice_client.disconnect()


def setup(bot):
    bot.add_cog(Alexa(bot))