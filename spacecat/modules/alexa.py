import asyncio
import random
import sqlite3
from itertools import islice
from time import gmtime, strftime, time

from bs4 import BeautifulSoup as bs

import discord
from discord import app_commands
from discord.ext import commands, tasks

import requests

import toml

import youtube_dl

from spacecat.helpers import constants
from spacecat.helpers import perms
from spacecat.helpers import reaction_buttons

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
    'noplaylist': False,
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


class YTDLStream:
    def __init__(self, metadata):
        self.title = metadata.get('title')
        self.duration = metadata.get('duration')
        self.webpage_url = metadata.get('webpage_url')
        self.playlist = metadata.get('playlist')

    async def create_steam(self):
        before_args = "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5"
        loop = asyncio.get_event_loop()
        metadata = await loop.run_in_executor(None, lambda: ytdl.extract_info(self.webpage_url, download=False))
        return discord.PCMVolumeTransformer(
            discord.FFmpegPCMAudio(metadata['url'], **ffmpeg_options, before_options=before_args), 0.5)

    @classmethod
    async def from_url(cls, webpage_url):
        loop = asyncio.get_event_loop()
        metadata = await loop.run_in_executor(None, lambda: ytdl.extract_info(webpage_url, download=False))
        songs = []
        try:
            if 'entries' in metadata:
                for entry in metadata['entries']:
                    try:
                        songs.append(YTDLStream(entry))
                    except AttributeError:
                        continue
            else:
                songs.append(YTDLStream(metadata))
        except TypeError:
            return

        return songs


class SourceFactory:
    async def from_url(self, webpage_url):
        if " " in webpage_url:
            song_metadatas = await YTDLStream.from_url(webpage_url)
        elif "youtube" in webpage_url or "youtu.be" in webpage_url:
            song_metadatas = await YTDLStream.from_url(webpage_url)
        else:
            song_metadatas = await YTDLStream.from_url(webpage_url)

        return song_metadatas

class MusicPlayer:
    def __init__(self, voice_client, bot):
        self.bot = bot
        self.voice_client = voice_client
        self.song_queue = []
        self.song_start_time = 0
        self.song_pause_time = 0
        self.loop_toggle = False
        self.skip_toggle = False

        config = toml.load(constants.DATA_DIR + 'config.toml')
        #self.disconnect_time = time() + config['music']['disconnect_time']
        #self._disconnect_timer.start()

    async def play(self, song):
        self.song_queue.insert(0, song)
        self.song_start_time = time()
        stream = await song.create_steam()
        self.voice_client.play(stream, after=lambda e: self.bot.loop.create_task(self.play_next()))

    async def play_next(self):
        config = toml.load(constants.DATA_DIR + 'config.toml')
        self.disconnect_time = time() + config['music']['disconnect_time']
        # If looping, grab source from url again
        if self.loop_toggle and not self.skip_toggle:
            coroutine = asyncio.run_coroutine_threadsafe(self.song_queue[0].create_stream(), self.bot.loop)
            audio_stream = coroutine.result()
            self.song_start_time = time()
            self.voice_client.play(audio_stream, after=lambda e: self.bot.loop.create_task(self.play_next()))
            return

        # Disable skip toggle to indicate that a skip has been completed
        if self.skip_toggle:
            self.skip_toggle = False

        # Remove next in queue
        try:
            self.song_queue.pop(0)
        except IndexError:
            return

        # Play the new first song in list
        if self.song_queue:
            self.song_start_time = time()
            coroutine = asyncio.run_coroutine_threadsafe(self.song_queue[0].create_stream(), self.bot.loop)
            audio_stream = coroutine.result()
            self.voice_client.play(audio_stream, after=lambda e: self.bot.loop.create_task(self.play_next()))
            return

    async def stop(self):
        self.song_queue.clear()
        self.voice_client.stop()

    @tasks.loop(seconds=30)
    async def _disconnect_timer(self):
        config = toml.load(constants.DATA_DIR + 'config.toml')
        if time() > self.disconnect_time and not self.voice_client.is_playing() and config['music']['auto_disconnect']:
            await self.voice_client.disconnect()


class Playlist:
    def __init__(self, id_, name, description, guild_id):
        self.id = id_
        self.name = name
        self.description = description
        self.guild_id = guild_id


class Alexa(commands.Cog):
    """Play some funky music in a voice chat"""
    NOT_CONNECTED_EMBED = discord.Embed(
        colour=constants.EmbedStatus.FAIL.value,
        description="I need to be in a voice channel to execute music "
                    "commands. \nUse **/join** or **/play** to connect me to a channel")

    def __init__(self, bot):
        self.bot = bot
        self.music_players = {}

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
        with open(constants.DATA_DIR + 'config.toml', 'w') as config_file:
            toml.dump(config, config_file)

        # Create playlist table if it don't exist
        db = sqlite3.connect(constants.DATA_DIR + 'spacecat.db')
        cursor = db.cursor()
        cursor.execute('PRAGMA foreign_keys = ON')

        cursor.execute(
            'CREATE TABLE IF NOT EXISTS playlist'
            '(id INTEGER PRIMARY KEY, name TEXT, description TEXT, server_id INTEGER)')

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
        # If bot disconnects from voice, remove music player
        if member.id == self.bot.user.id and after.channel is None:
            try:
                pass
                self.music_players.pop(member.guild.id)
            except KeyError:
                pass

        # Check if bot voice client isn't active
        voice_client = member.guild.voice_client
        if not voice_client:
            return

        # Check if auto disconnect is disabled
        config = toml.load(constants.DATA_DIR + 'config.toml')
        if not config['music']['auto_disconnect']:
            return

        # Check if user isn't in same channel or not a disconnect/move event
        if voice_client.channel != before.channel or before.channel == after.channel:
            return

        # Disconnect if the bot is the only user left
        if len(voice_client.channel.members) < 2:
            await voice_client.disconnect()

    queue_group = app_commands.Group(name="queue", description="Handles songs that will be played next.")
    playlist_group = app_commands.Group(name="playlist", description="Saved songs that can be played later.")
    musicsettings_group = app_commands.Group(name="musicsettings", description="Modify music settings.")

    @app_commands.command()
    @perms.check()
    async def join(self, interaction, channel: discord.VoiceChannel = None):
        """Joins a voice channel"""
        # Alert if user is not in a voice channel and no channel is specified
        if channel is None and not interaction.user.voice:
            embed = discord.Embed(
                colour=constants.EmbedStatus.FAIL.value,
                description="You must specify or be in a voice channel")
            await interaction.response.send_message(embed=embed)
            return

        # Alert if the specified voice channel is the same as the current channel
        if interaction.guild.voice_client and channel == interaction.guild.voice_client.channel:
            embed = discord.Embed(
                colour=constants.EmbedStatus.FAIL.value,
                description="I'm already in that voice channel")
            await interaction.response.send_message(embed=embed)
            return

        # Joins player's current voice channel
        if interaction.guild.voice_client is None:
            self.music_players[interaction.guild_id] = MusicPlayer(interaction.guild.voice_client, self.bot)

            if channel is None:
                channel = interaction.user.voice.channel

            await channel.connect()
            self.music_players[interaction.guild_id] = MusicPlayer(interaction.guild.voice_client, self.bot)
            embed = discord.Embed(
                colour=constants.EmbedStatus.YES.value,
                description=f"Joined voice channel `{channel.name}`")
            await interaction.response.send_message(embed=embed)
            return

        # Move to specified channel if already connected
        previous_channel_name = interaction.guild.voice_client.channel.name
        await interaction.guild.voice_client.move_to(channel)
        embed = discord.Embed(
            colour=constants.EmbedStatus.YES.value,
            description=f"Moved from voice channel `{previous_channel_name}` to "
                        f"voice channel `{channel.name}`")
        await interaction.response.send_message(embed=embed)
        return

    @app_commands.command()
    @perms.check()
    async def leave(self, interaction):
        """Stops and leaves the voice channel"""
        # Alert of not in voice channel
        if not interaction.guild.voice_client:
            interaction.response.send_message(embed=self.NOT_CONNECTED_EMBED)
            return

        # Stop and Disconnect from voice channel
        voice_channel_name = interaction.guild.voice_client.channel.name
        self.music_players.pop(interaction.guild_id)
        await interaction.guild.voice_client.disconnect()
        embed = discord.Embed(
            colour=constants.EmbedStatus.YES.value,
            description=f"Disconnected from voice channel `{voice_channel_name}`")
        await interaction.response.send_message(embed=embed)
        return

    @app_commands.command()
    @perms.check()
    async def play(self, interaction, url: str):
        """Plays from a url (almost anything youtube_dl supports)"""
        # Join channel and create music player instance if it doesn't exist
        if not interaction.guild.voice_client:
            await interaction.user.voice.channel.connect()
        music_player = await self._get_music_player(interaction.guild)

        # Alert due to song errors
        await interaction.response.defer()
        try:
            songs = await self._fetch_songs(url)
        except VideoTooLongError:
            embed = discord.Embed(
                colour=constants.EmbedStatus.FAIL.value,
                description="Woops, that video is too long")
            await interaction.followup.send(embed=embed)
            return
        except VideoUnavailableError:
            embed = discord.Embed(
                colour=constants.EmbedStatus.FAIL.value,
                description="Woops, that video is unavailable")
            await interaction.followup.send(embed=embed)
            return

        # Playlists
        if len(songs) > 1:
            # Add to queue if song already playing
            if len(music_player.song_queue) > 0:
                music_player.song_queue.append(songs)
                embed = discord.Embed(
                    colour=constants.EmbedStatus.YES.value,
                    description=f"Added `{len(songs)}` songs from playlist {songs} to "
                                f"#{len(music_player.song_queue) - 1} in queue")
                await interaction.followup.send(embed=embed)
                return

            # Instantly play song if no song currently playing
            await music_player.play(songs[0])
            music_player.song_queue.extend(songs[1:])
            embed = discord.Embed(
                colour=constants.EmbedStatus.YES.value,
                description=f"Now playing playlist {songs[0].playlist}")
            await interaction.followup.send(embed=embed)
            return

        # Send to queue_add function if there is a song playing
        duration = await self._get_duration(songs[0].duration)
        song_name = f"[{songs[0].title}]({songs[0].webpage_url}) `{duration}`"
        if len(music_player.song_queue) > 0:
            music_player.song_queue.extend(songs)
            embed = discord.Embed(
                colour=constants.EmbedStatus.YES.value,
                description=f"Song {song_name} added to #{len(music_player.song_queue) - 1} in queue")
            await interaction.followup.send(embed=embed)
            return

        # Instantly play song if no song currently playing
        await music_player.play(songs[0])
        embed = discord.Embed(
            colour=constants.EmbedStatus.YES.value,
            description=f"Now playing {song_name}")
        await interaction.followup.send(embed=embed)
        return

    @cog_ext.cog_slash()
    @perms.check()
    async def playsearch(self, ctx, *, search):
        # Join user's voice channel if not in one already
        if ctx.guild.voice_client is None:
            await self.bot.slash.invoke_command(self.join, ctx, [])

            # End function if bot failed to join a voice channel.
            if ctx.guild.voice_client is None:
                return

        # Set urls to be used by the searcher
        base_url = "https://www.youtube.com"
        search_url = f"https://www.youtube.com/results?search_query={search}"

        # Query youtube with a search term and grab the title, duration and url
        # of all videos on the page
        headers = {'User-Agent': 'Mozilla/5.0 (compatible; Googlebot/2.1; "\
            "+http://www.google.com/bot.html)'}
        source = requests.get(search_url, headers=headers)
        soup = bs(source.text, 'lxml')
        titles = soup.find_all('a', attrs={'class': 'yt-uix-tile-link'})
        durations = soup.find_all('span', attrs={'class': 'video-time'})
        urls = []
        for title in titles:
            urls.append(f"{base_url}{title.attrs['href']}")

        # Alert user if search term returns no results
        if not titles:
            embed = discord.Embed(
                colour=constants.EmbedStatus.FAIL.value,
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
        embed = discord.Embed(
            colour=constants.EmbedStatus.INFO.value,
            title=f"{constants.EmbedIcon.MUSIC} Search Query")
        results_output = '\n'.join(results_format)
        embed.add_field(
            name=f"Results for '{search}'",
            value=results_output, inline=False)
        msg = await ctx.send(embed=embed)

        # Add reaction button for every result
        reactions = []
        for index in range(len(results_format)):
            emoji = reaction_buttons.number_to_emoji(index + 1)
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
                    colour=constants.EmbedStatus.FAIL.value,
                    description="Song selection timed out.")
            embed.set_author(name="Search Query", icon_url="attachment://image.png")
            await msg.clear_reactions()
            await msg.edit(file=None, embed=embed)
            return

        # Play selected song
        number = reaction_buttons.emoji_to_number(str(reaction))
        selected_song = urls[number - 1]
        await self.bot.slash.invoke_command(self.play, ctx, [selected_song])

    @cog_ext.cog_slash()
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
        ctx.guild.voice_client.stop()
        embed = discord.Embed(
            colour=constants.EmbedStatus.YES.value,
            description="Music has been stopped & queue has been cleared")
        await ctx.send(embed=embed)

    @cog_ext.cog_slash()
    @perms.check()
    async def resume(self, ctx):
        """Resumes music if paused"""
        status = await self._check_music_status(ctx, ctx.guild)
        if not status:
            return

        # Check if music is paused
        if not ctx.guild.voice_client.is_paused():
            embed = discord.Embed(
                colour=constants.EmbedStatus.FAIL.value,
                description="Music isn't paused")
            await ctx.send(embed=embed)
            return

        # Resumes music playback
        ctx.guild.voice_client.resume()
        self.song_start_time[ctx.guild.id] = time() - self.song_pause_time[ctx.guild.id]
        self.song_pause_time[ctx.guild.id] = None
        embed = discord.Embed(
            colour=constants.EmbedStatus.YES.value,
            description="Music has been resumed")
        await ctx.send(embed=embed)

    @cog_ext.cog_slash()
    @perms.check()
    async def pause(self, ctx):
        """Pauses the music"""
        status = await self._check_music_status(ctx, ctx.guild)
        if not status:
            return

        # Check if music is paused
        if ctx.guild.voice_client.is_paused():
            embed = discord.Embed(
                colour=constants.EmbedStatus.FAIL.value,
                description="Music is already paused")
            await ctx.send(embed=embed)
            return

        # Pauses music playback
        config = toml.load(constants.DATA_DIR + 'config.toml')
        self.disconnect_time[ctx.guild.id] = time() \
            + config['music']['disconnect_time']
        ctx.guild.voice_client.pause()
        self.song_pause_time[ctx.guild.id] = time() - self.song_start_time[ctx.guild.id]
        embed = discord.Embed(
            colour=constants.EmbedStatus.YES.value,
            description="Music has been paused")
        await ctx.send(embed=embed)

    @cog_ext.cog_slash()
    @perms.check()
    async def skip(self, ctx):
        """Skip the current song and play the next song"""
        status = await self._check_music_status(ctx, ctx.guild)
        if not status:
            return

        # Check if there's queue is empty
        if len(self.song_queue[ctx.guild.id]) <= 1:
            embed = discord.Embed(
                colour=constants.EmbedStatus.FAIL.value,
                description="There's nothing in the queue after this")
            await ctx.send(embed=embed)
            return

        # Stop current song and flag that it has been skipped
        self.skip_toggle[ctx.guild.id] = True
        ctx.guild.voice_client.stop()

    @cog_ext.cog_slash()
    @perms.check()
    async def shuffle(self, ctx):
        """Randomly moves the contents of the queue around"""
        # Alert if queue is empty
        if len(self.song_queue[ctx.guild.id]) < 2:
            embed = discord.Embed(
                colour=constants.EmbedStatus.FAIL.value,
                description="There's nothing in the queue to shuffle")
            await ctx.send(embed=embed)
            return

        # Create temp queue excluding currently playing song to shuffle
        temp_queue = self.song_queue[ctx.guild.id][1:]
        random.shuffle(temp_queue)
        self.song_queue[ctx.guild.id][1:] = temp_queue

        # Output result to chat
        embed = discord.Embed(
            colour=constants.EmbedStatus.YES.value,
            description="Queue has been shuffled")
        await ctx.send(embed=embed)
        return

    @cog_ext.cog_slash()
    @perms.check()
    async def loop(self, ctx):
        """Loop the currently playing song"""
        status = await self._check_music_status(ctx, ctx.guild)
        if not status:
            return

        # Disable loop if enabled
        if self.loop_toggle[ctx.guild.id]:
            self.loop_toggle[ctx.guild.id] = False
            embed = discord.Embed(
                colour=constants.EmbedStatus.NO.value,
                description="Loop disabled")
            await ctx.send(embed=embed)
            return

        # Enable loop if disabled
        self.loop_toggle[ctx.guild.id] = True
        embed = discord.Embed(
            colour=constants.EmbedStatus.YES.value,
            description="Loop enabled")
        await ctx.send(embed=embed)
        return

    #@cog_ext.cog_slash()
    #@perms.check()
    #async def queue(self, ctx, arg: int = 1):
    #    """View and modify the current song queue. Defaults to the list subcommand."""
        # Run the queue list subcommand if no subcommand is specified
    #    await self.bot.slash.invoke_command(self.queue_list, arg)

    @cog_ext.cog_subcommand(base="queue", name="list")
    @perms.check()
    async def queue_list(self, ctx, page: int = 1):
        """List the current song queue"""
        status = await self._check_music_status(ctx, ctx.guild)
        if not status:
            return

        # Notify user if nothing is in the queue
        if not self.song_queue[ctx.guild.id]:
            embed = discord.Embed(
                colour=constants.EmbedStatus.FAIL.value,
                description="There's nothing in the queue right now")
            await ctx.send(embed=embed)
            return

        # Output first in queue as currently playing
        embed = discord.Embed(
            colour=constants.EmbedStatus.INFO.value,
            title=f"{constants.EmbedIcon.MUSIC} Music Queue")
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
            value=f"{self.song_queue[ctx.guild.id][0].title} "
            f"`{current_time}/{duration}` \n{spacer}")

        # List remaining songs in queue plus total duration
        if queue_status:
            queue_info = []

            # Modify page variable to get every ten results
            page -= 1
            if page > 0:
                page = page * 10

            total_duration = -self.song_queue[ctx.guild.id][0].duration
            for song in self.song_queue[ctx.guild.id]:
                total_duration += song.duration

            for index, song in enumerate(
                    islice(self.song_queue[ctx.guild.id], page + 1, page + 11)):
                duration = await self._get_duration(song.duration)
                queue_info.append(f"{page + index + 1}. {song.title} `{duration}`")

            # Alert if no songs are on the specified page
            if page > 0 and not queue_info:
                embed = discord.Embed(
                    colour=constants.EmbedStatus.FAIL.value,
                    description="There are no songs on that page")
                await ctx.send(embed=embed)
                return

            # Omit songs past 10 and just display amount instead
            if len(self.song_queue[ctx.guild.id]) > page + 11:
                queue_info.append(
                    f"`+{len(self.song_queue[ctx.guild.id]) - 11 - page} more in queue`")

            # Output results to chat
            duration = await self._get_duration(total_duration)
            queue_output = '\n'.join(queue_info)
            embed.add_field(
                name=f"Queue  `{duration}`",
                value=queue_output, inline=False)
        await ctx.send(embed=embed)

    @cog_ext.cog_subcommand(base="queue", name="move")
    @perms.check()
    async def queue_move(self, ctx, original_pos: int, new_pos: int):
        """Move a song to a different position in the queue"""
        status = await self._check_music_status(ctx, ctx.guild)
        if not status:
            return

        # Try to remove song from queue using the specified index
        try:
            if original_pos < 1:
                raise IndexError("Position can\'t be be less than 1")
            song = self.song_queue[ctx.guild.id][original_pos]
        except IndexError:
            embed = discord.Embed(
                colour=constants.EmbedStatus.FAIL.value,
                description="There's no song at that position")
            await ctx.send(embed=embed)
            return

        # Move song into new position in queue
        if not 1 <= new_pos < len(self.song_queue[ctx.guild.id]):
            embed = discord.Embed(
                colour=constants.EmbedStatus.FAIL.value,
                description="You can't move the song into that position")
            await ctx.send(embed=embed)
            return
        self.song_queue[ctx.guild.id].pop(original_pos)
        self.song_queue[ctx.guild.id].insert(new_pos, song)

        # Output result to chat
        duration = await self._get_duration(song.duration)
        embed = discord.Embed(
            colour=constants.EmbedStatus.YES.value,
            description=f"[{song.title}]({song.webpage_url}) "
            f"`{duration}` has been moved from position #{original_pos} "
            f"to position #{new_pos}")
        await ctx.send(embed=embed)

    @cog_ext.cog_subcommand(base="queue", name="add")
    @perms.check()
    async def queue_add(self, ctx, url):
        """Adds a song to the queue"""
        # Alert if too many songs in queue
        if len(self.song_queue[ctx.guild.id]) > 100:
            embed = discord.Embed(
                colour=constants.EmbedStatus.FAIL.value,
                description="Too many songs in queue. Calm down.")
            await ctx.send(embed=embed)
            return

        # Add the song to the queue and output result
        try:
            source, song_name = await self._process_song(ctx, url)
        except VideoTooLongError:
            embed = discord.Embed(
                colour=constants.EmbedStatus.FAIL.value,
                description="Woops, that video is too long")
            await ctx.send(embed=embed)
            return
        except VideoUnavailableError:
            embed = discord.Embed(
                colour=constants.EmbedStatus.FAIL.value,
                description="Woops, that video is unavailable")
            await ctx.send(embed=embed)
            return
        self.song_queue[ctx.guild.id].append(source)
        embed = discord.Embed(
            colour=constants.EmbedStatus.YES.value,
            description=f"Added {song_name} to "
            f"#{len(self.song_queue[ctx.guild.id]) - 1} in queue")
        await ctx.send(embed=embed)
        return

    @cog_ext.cog_subcommand(base="queue", name="remove")
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
                colour=constants.EmbedStatus.FAIL.value,
                description="That's an invalid queue position")
            await ctx.send(embed=embed)
            return

        # Output result to chat
        duration = await self._get_duration(song.duration)
        embed = discord.Embed(
            colour=constants.EmbedStatus.NO.value,
            description=f"[{song.title}]({song.webpage_url}) "
            f"`{duration}` has been removed from position #{index} "
            "of the queue")
        await ctx.send(embed=embed)

    @cog_ext.cog_subcommand(base="queue", name="clear")
    @perms.check()
    async def queue_clear(self, ctx):
        """Clears the entire queue"""
        status = await self._check_music_status(ctx, ctx.guild)
        if not status:
            return

        # Try to remove all but the currently playing song from the queue
        if len(self.song_queue[ctx.guild.id]) < 2:
            embed = discord.Embed(
                colour=constants.EmbedStatus.FAIL.value,
                description="There's nothing in the queue to clear")
            await ctx.send(embed=embed)
            return
        self.song_queue[ctx.guild.id] = [self.song_queue[ctx.guild.id][0]]

        # Output result to chat
        embed = discord.Embed(
            colour=constants.EmbedStatus.NO.value,
            description="All songs have been removed from the queue")
        await ctx.send(embed=embed)

    #@cog_ext.cog_slash()
    #@perms.check()
    #async def playlist(self, ctx):
    #    """Configure music playlists. Defaults to list subcommand."""
        # Run the queue list subcommand if no subcommand is specified
    #    await self.bot.slash.invoke_command(self.playlist_list)

    @cog_ext.cog_subcommand(base="playlist", name="create")
    @perms.check()
    async def playlist_create(self, ctx, *, playlist_name):
        """Create a new playlist"""
        # Limit playlist name to 30 chars
        if len(playlist_name) > 30:
            embed = discord.Embed(
                colour=constants.EmbedStatus.FAIL.value,
                description="Playlist name is too long")
            await ctx.send(embed=embed)
            return

        # Alert if playlist with specified name already exists
        try:
            await self._get_playlist(ctx, playlist_name)
            embed = discord.Embed(
                colour=constants.EmbedStatus.FAIL.value,
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
            colour=constants.EmbedStatus.NO.value,
            description=f"Playlist `{playlist_name}` has been created")
        await ctx.send(embed=embed)

    @cog_ext.cog_subcommand(base="playlist", name="destroy")
    @perms.check()
    async def playlist_destroy(self, ctx, *, playlist_name):
        """Deletes an existing playlist"""
        # Alert if playlist doesn't exist in db
        try:
            playlist = await self._get_playlist(ctx, playlist_name)
        except ValueError:
            embed = discord.Embed(
                colour=constants.EmbedStatus.FAIL.value,
                description=f"Playlist `{playlist_name}` doesn't exist")
            await ctx.send(embed=embed)
            return

        # Remove playlist from database and all songs linked to it
        db = sqlite3.connect(constants.DATA_DIR + 'spacecat.db')
        cursor = db.cursor()
        values = (playlist[0],)
        cursor.execute(
            'DELETE FROM playlist_music '
            'WHERE playlist_id=?', values)
        values = (playlist_name, ctx.guild.id)
        cursor.execute(
            'DELETE FROM playlist '
            'WHERE name=? AND server_id=?', values)
        db.commit()
        db.close()

        # Output result to chat
        embed = discord.Embed(
            colour=constants.EmbedStatus.NO.value,
            description=f"Playlist `{playlist_name}` has been destroyed")
        await ctx.send(embed=embed)

    @cog_ext.cog_subcommand(base="playlist", name="description")
    @perms.check()
    async def playlist_description(self, ctx, playlist_name, *, description):
        """Sets the description for the playlist"""
        # Alert if playlist doesn't exist
        try:
            playlist = await self._get_playlist(ctx, playlist_name)
        except ValueError:
            embed = discord.Embed(
                colour=constants.EmbedStatus.FAIL.value,
                description=f"Playlist `{playlist_name}` doesn't exist")
            await ctx.send(embed=embed)
            return

        # Limit playlist description to 300 chars
        if len(playlist_name) > 300:
            embed = discord.Embed(
                colour=constants.EmbedStatus.FAIL.value,
                description="Playlist name is too long")
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
            colour=constants.EmbedStatus.YES.value,
            description=f"Description set for playlist `{playlist_name}`")
        await ctx.send(embed=embed)

    @cog_ext.cog_subcommand(base="playlist", name="rename")
    @perms.check()
    async def playlist_rename(self, ctx, playlist_name, new_name):
        """Rename an existing playlist"""
        # Alert if playlist doesn't exist
        try:
            playlist = await self._get_playlist(ctx, playlist_name)
        except ValueError:
            embed = discord.Embed(
                colour=constants.EmbedStatus.FAIL.value,
                description=f"Playlist `{playlist_name}` doesn't exist")
            await ctx.send(embed=embed)
            return

        # Rename playlist in database
        db = sqlite3.connect(constants.DATA_DIR + 'spacecat.db')
        cursor = db.cursor()
        values = (new_name, playlist[0],)
        cursor.execute('UPDATE playlist SET name=? WHERE id=?', values)
        db.commit()
        db.close()

        # Output result to chat
        embed = discord.Embed(
            colour=constants.EmbedStatus.YES.value,
            description=f"Playlist `{playlist}` has been renamed to "
            f"`{new_name}`")
        await ctx.send(embed=embed)

    @cog_ext.cog_subcommand(base="playlist", name="list")
    @perms.check()
    async def playlist_list(self, ctx):
        """List all available playlists"""
        # Alert if no playlists exist
        playlists = await self._get_playlist(ctx)
        if not playlists:
            embed = discord.Embed(
                colour=constants.EmbedStatus.FAIL.value,
                description="There are no playlists available")
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
        embed = discord.Embed(
            colour=constants.EmbedStatus.INFO.value,
            title=f"{constants.EmbedIcon.MUSIC} Music Playlists")
        playlist_output = '\n'.join(playlist_info)
        embed.add_field(
            name=f"{len(playlists)} available",
            value=playlist_output, inline=False)
        await ctx.send(embed=embed)

    @cog_ext.cog_subcommand(base="playlist", name="add")
    @perms.check()
    async def playlist_add(self, ctx, playlist_name, *, url):
        """Adds a song to a playlist"""
        # Alert if playlist doesn't exist in db
        try:
            playlist = await self._get_playlist(ctx, playlist_name)
        except ValueError:
            embed = discord.Embed(
                colour=constants.EmbedStatus.FAIL.value,
                description=f"Playlist `{playlist_name}` doesn't exist")
            await ctx.send(embed=embed)
            return

        songs = await self._get_songs(ctx, playlist_name)
        if len(songs) > 100:
            embed = discord.Embed(
                colour=constants.EmbedStatus.FAIL.value,
                description="There's too many songs in the playlist. Remove"
                "some songs to be able to add more")
            await ctx.send(embed=embed)
            return

        # Get song source to add to song list
        try:
            source, _ = await self._process_song(ctx, url)
        except VideoTooLongError:
            embed = discord.Embed(
                colour=constants.EmbedStatus.FAIL.value,
                description="Woops, that video is too long")
            await ctx.send(embed=embed)
            return
        except VideoUnavailableError:
            embed = discord.Embed(
                colour=constants.EmbedStatus.FAIL.value,
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
            'INSERT INTO playlist_music(title, duration, url, previous_song, playlist_id) '
            'VALUES (?,?,?,?,?)', values)
        db.commit()
        db.close()

        # Output result to chat
        duration = await self._get_duration(source.duration)
        embed = discord.Embed(
            colour=constants.EmbedStatus.YES.value,
            description=f"Added [{source.title}]({source.webpage_url}) "
            f"`{duration}` to position #{len(songs) + 1} "
            f"in playlist `{playlist_name}`")
        await ctx.send(embed=embed)

    @cog_ext.cog_subcommand(base="playlist", name="remove")
    @perms.check()
    async def playlist_remove(self, ctx, playlist_name, index):
        """Removes a song from a playlist"""
        # Fetch songs from playlist if it exists
        try:
            songs = await self._get_songs(ctx, playlist_name)
        except ValueError:
            embed = discord.Embed(
                colour=constants.EmbedStatus.FAIL.value,
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
                'UPDATE playlist_music SET previous_song=? '
                'WHERE id=?', values)
        except IndexError:
            pass

        # Remove selected song from playlist
        values = (selected_song[0],)
        cursor.execute('DELETE FROM playlist_music WHERE id=?', values)
        db.commit()
        db.close()

        # Output result to chat
        duration = await self._get_duration(selected_song[2])
        embed = discord.Embed(
            colour=constants.EmbedStatus.NO.value,
            description=f"[{selected_song[1]}]({selected_song[3]}) "
            f"`{duration}` has been removed from `{playlist_name}`")
        await ctx.send(embed=embed)

    @cog_ext.cog_subcommand(base="playlist", name="move")
    @perms.check()
    async def playlist_move(self, ctx, playlist_name, original_pos, new_pos):
        """Moves a song to a specified position in a playlist"""
        # Fetch songs from playlist if it exists
        try:
            songs = await self._get_songs(ctx, playlist_name)
        except ValueError:
            embed = discord.Embed(
                colour=constants.EmbedStatus.FAIL.value,
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
                'UPDATE playlist_music SET previous_song=? '
                'WHERE id=?', value)
        db.commit()
        db.close()

        # Output result to chat
        duration = await self._get_duration(selected_song[2])
        embed = discord.Embed(
                colour=constants.EmbedStatus.YES.value,
                description=f"[{selected_song[1]}]({selected_song[3]}) "
                f"`{duration}` has been moved to position #{new_pos} "
                f"in playlist `{playlist_name}`")
        await ctx.send(embed=embed)

    @cog_ext.cog_subcommand(base="playlist", name="view")
    @perms.check()
    async def playlist_view(self, ctx, playlist_name, page=1):
        """List all songs in a playlist"""
        # Fetch songs from playlist if it exists
        try:
            playlist = await self._get_playlist(ctx, playlist_name)
            songs = await self._get_songs(ctx, playlist_name)
        except ValueError:
            embed = discord.Embed(
                colour=constants.EmbedStatus.FAIL.value,
                description=f"Playlist `{playlist_name}` does not exist")
            await ctx.send(embed=embed)
            return

        # Modify page variable to get every ten results
        page -= 1
        if page > 0:
            page = page * 10

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
                colour=constants.EmbedStatus.FAIL.value,
                description="There are no songs on that page")
            await ctx.send(embed=embed)
            return

        # Output results to chat
        embed = discord.Embed(
            colour=constants.EmbedStatus.INFO.value,
            title=f"{constants.EmbedIcon.MUSIC} Playlist '{playlist_name}' Contents")
        if playlist[2] and page == 0:
            embed.description = playlist[2]
        formatted_duration = await self._get_duration(total_duration)
        playlist_music_output = '\n'.join(formatted_songs)
        embed.add_field(
            name=f"{len(songs)} songs available `{formatted_duration}`",
            value=playlist_music_output, inline=False)
        await ctx.send(embed=embed)

    @cog_ext.cog_subcommand(base="playlist", name="play")
    @perms.check()
    async def playlist_play(self, ctx, playlist):
        """Play from a locally saved playlist"""
        # Join user's voice channel if not in one already
        if ctx.guild.voice_client is None:
            await self.bot.slash.invoke_command(self.join, ctx, [])

            # End function if bot failed to join a voice channel.
            if ctx.guild.voice_client is None:
                return

        # Get all songs in playlist
        try:
            songs = await self._get_songs(ctx, playlist)
        except TypeError:
            embed = discord.Embed(
                colour=constants.EmbedStatus.FAIL.value,
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
                ctx.guild.voice_client.play(source, after=lambda e: self._next(ctx))
                embed = discord.Embed(
                    colour=constants.EmbedStatus.YES.value,
                    description=f"Now playing playlist `{playlist}`")
                await ctx.send(embed=embed)
                break
        else:
            embed = discord.Embed(
                colour=constants.EmbedStatus.YES.value,
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
                colour=constants.EmbedStatus.FAIL.value,
                description=f"These songs in playlist `{playlist}` "
                f"are unavailable: \n{song_format}")
            await ctx.send(embed=embed)

    @cog_ext.cog_slash()
    @perms.exclusive()
    async def musicsettings(self, ctx):
        """Configure music playlists. Defaults to list subcommand."""
        # Run the queue list subcommand if no subcommand is specified
        await ctx.send("Please specify a valid subcommand.")

    @cog_ext.cog_subcommand(base="musicsettings", name="autodisconnect")
    @perms.exclusive()
    async def musicsettings_autodisconnect(self, ctx):
        """Toggles if the bot should auto disconnect from a voice channel."""
        config = toml.load(constants.DATA_DIR + 'config.toml')

        # Toggle auto_disconnect config setting
        if config['music']['auto_disconnect']:
            config['music']['auto_disconnect'] = False
            result_text = "disabled"
        else:
            config['music']['auto_disconnect'] = True
            result_text = "enabled"

        with open(constants.DATA_DIR + 'config.toml', 'w') as config_file:
            toml.dump(config, config_file)

        embed = discord.Embed(
            colour=constants.EmbedStatus.YES.value,
            description=f"Music player auto disconnect {result_text}")
        await ctx.send(embed=embed)

    @cog_ext.cog_subcommand(base="musicsettings", name="disconnecttime")
    @perms.exclusive()
    async def musicsettings_disconnecttime(self, ctx, seconds: int):
        """Sets a time for when the bot should auto disconnect from voice if not playing"""
        config = toml.load(constants.DATA_DIR + 'config.toml')

        # Set disconnect_time config variable
        config['music']['disconnect_time'] = seconds
        with open(constants.DATA_DIR + 'config.toml', 'w') as config_file:
            toml.dump(config, config_file)

        embed = discord.Embed(
            colour=constants.EmbedStatus.YES.value,
            description=f"Music player auto disconnect timer set to {seconds} seconds")
        await ctx.send(embed=embed)
        return

    async def _get_music_player(self, guild):
        try:
            music_player = self.music_players[guild.id]
        except KeyError:
            music_player = MusicPlayer(guild.voice_client, self.bot)
            self.music_players[guild.id] = music_player
        return music_player

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
        except ValueError:
            return "N/A"

    async def _get_all_playlists(self, guild):
        """Get list of all playlists for a guild"""
        db = sqlite3.connect(constants.DATA_DIR + 'spacecat.db')
        cursor = db.cursor()
        values = guild.id
        cursor.execute('SELECT * FROM playlist WHERE server_id=?', values)
        rows = cursor.fetchall()
        db.close()

        playlists = []
        for row in rows:
            playlists.append(Playlist(row[0], row[1], row[2], row[3]))
        return playlists

    async def _get_playlist(self, guild, playlist_name=None):
        """Gets playlist data from name"""
        db = sqlite3.connect(constants.DATA_DIR + 'spacecat.db')
        cursor = db.cursor()
        values = (playlist_name, guild.id)
        cursor.execute('SELECT * FROM playlist WHERE name=? AND server_id=?', values)
        row = cursor.fetchone()
        db.close()

        if row is None:
            raise ValueError("That playlist is unavailable")
        return Playlist(row[0], row[1], row[2], row[3])

    async def _get_playlist_songs(self, guild, playlist_name):
        """Gets playlist songs from name"""
        # Alert if playlist doesn't exist
        playlist = await self._get_playlist(guild, playlist_name)
        if playlist is None:
            raise ValueError("That playlist doesn't exist")

        # Get list of all songs in playlist
        db = sqlite3.connect(constants.DATA_DIR + 'spacecat.db')
        cursor = db.cursor()
        values = (playlist.id,)
        cursor.execute('SELECT * FROM playlist_music WHERE playlist_id=?', values)
        songs = cursor.fetchall()
        db.close()

        # Use dictionary to pair songs with the next song
        song_links = {}
        for song in songs:
            song_links[song[4]] = [song[0], song]

        # Order playlist songs into list
        ordered_songs = []
        next_song = song_links.get(None)
        while next_song is not None:
            ordered_songs.append(next_song[1])
            next_song = song_links.get(next_song[0])

        return ordered_songs

    async def _fetch_songs(self, url):
        """Grab audio source from YouTube and check if longer than 3 hours"""
        source_factory = SourceFactory()
        songs = await source_factory.from_url(url)

        #if not songs:
        #    raise VideoUnavailableError("Specified song is unavailable")

        #if songs.duration >= 10800:
        #    raise VideoTooLongError("Specified song is longer than 3 hours")

        return songs


async def setup(bot):
    await bot.add_cog(Alexa(bot))
