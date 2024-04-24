import datetime
import sqlite3

import discord
from discord import app_commands
from discord.ext import commands

from enum import Enum

import toml

import uuid

import wavelink

from spacecat.helpers import constants
from spacecat.helpers import perms
from spacecat.helpers.views import PaginatedView, EmptyPaginatedView


class SongUnavailableError(ValueError):
    pass


class PlayerResult(Enum):
    PLAYING = 0
    QUEUEING = 1


class OriginalSource(Enum):
    LOCAL = "Saved Playlist"
    YOUTUBE_VIDEO = "YouTube"
    YOUTUBE_SONG = "YouTube Music"
    YOUTUBE_PLAYLIST = "YouTube Playlist"
    YOUTUBE_ALBUM = "YouTube Album"
    SPOTIFY_SONG = "Spotify"
    SPOTIFY_PLAYLIST = "Spotify Playlist"
    SPOTIFY_ALBUM = "Spotify Album"
    UNKNOWN = "Unknown"




class Musicbox(commands.Cog):
    """Stream your favourite beats right to your local VC"""
    NOT_CONNECTED_EMBED = discord.Embed(
        colour=constants.EmbedStatus.FAIL.value,
        description="I need to be in a voice channel to execute music "
                    "commands. \nUse **/join** or **/play** to connect me to a channel.")

    NO_VOICE_CHANNEL_EMBED = discord.Embed(
        colour=constants.EmbedStatus.FAIL.value,
        description="You need to be in a voice channel to start playing songs.")

    def __init__(self, bot):
        self.bot = bot
        self.music_players: dict[int, MusicPlayer] = {}
        self.database = sqlite3.connect(constants.DATA_DIR + "spacecat.db")
        self.playlists = PlaylistRepository(self.database)
        self.playlist_songs = PlaylistSongRepository(self.database)

    async def cog_load(self):
        """
        Loads the cog by initializing configuration settings and Wavelink for music streaming.
        """
        await self.init_config()
        await self.init_wavelink()

    @staticmethod
    async def init_config():
        """
        Initialises configuration settings for the music streaming feature.
        Loads the config file, sets default values for lavalink address, port, and password if not present,
        and writes the updated config back to the file.
        """
        config = toml.load(constants.DATA_DIR + 'config.toml')
        if 'lavalink' not in config:
            config['lavalink'] = {}
        if 'address' not in config['lavalink']:
            config['lavalink']['address'] = "http://localhost"
        if 'port' not in config['lavalink']:
            config['lavalink']['port'] = "2333"
        if 'password' not in config['lavalink']:
            config['lavalink']['password'] = "password1"

        with open(constants.DATA_DIR + 'config.toml', 'w') as config_file:
            toml.dump(config, config_file)

    async def init_wavelink(self):
        """
        Initializes the Wavelink client for music streaming.

        This function loads the configuration settings from the 'config.toml' file located in the 'constants.DATA_DIR' directory. It creates a Wavelink node using the provided address, port, and password. Then, it connects the Wavelink client to the node using the provided Discord bot.
        """
        config = toml.load(constants.DATA_DIR + 'config.toml')
        node = wavelink.Node(uri=f"{config['lavalink']['address']}:{config['lavalink']['port']}",
                             password=config['lavalink']['password'])
        await wavelink.Pool.connect(nodes=[node], client=self.bot)

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

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        """Disconnect the bot if the last user leaves the channel"""
        # If bot disconnects from voice, remove music player
        if member.id == self.bot.user.id and after.channel is None:
            try:
                music_player = self.music_players.pop(member.guild.id)
                await music_player.disable_auto_disconnect()
            except KeyError:
                pass

        # Check if bot voice client isn't active
        voice_client = member.guild.voice_client
        if not voice_client:
            return

        # Check if auto channel disconnect is disabled
        config = toml.load(constants.DATA_DIR + 'config.toml')
        if not config['music']['auto_disconnect']:
            return

        # Check if user isn't in same channel or not a disconnect/move event
        if voice_client.channel != before.channel or before.channel == after.channel:
            return

        # Disconnect if the bot is the only user left
        if len(voice_client.channel.members) < 2:
            await voice_client.disconnect()

    @commands.Cog.listener()
    async def on_wavelink_track_end(self, payload: wavelink.TrackEndEventPayload):
        if payload.player is None:
            return

        music_player = await self._get_music_player(payload.player.channel)
        await music_player.process_song_end()

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
                description="You must be in or specify a voice channel.")
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
            if channel is None:
                channel = interaction.user.voice.channel

            await self._get_music_player(channel)
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
            await interaction.response.send_message(embed=self.NOT_CONNECTED_EMBED)
            return
        music_player = await self._get_music_player(interaction.user.voice.channel)

        # Stop and Disconnect from voice channel
        voice_channel_name = interaction.guild.voice_client.channel.name
        await music_player.disconnect()
        embed = discord.Embed(
            colour=constants.EmbedStatus.YES.value,
            description=f"Disconnected from voice channel `{voice_channel_name}`")
        await interaction.response.send_message(embed=embed)
        return

    @app_commands.command()
    @perms.check()
    async def play(self, interaction: discord.Interaction, url: str, position: int = -1):
        """Plays from a url or search query"""
        # Join channel and create music player instance if it doesn't exist
        try:
            music_player = await self._get_music_player(interaction.user.voice.channel)
        except AttributeError:
            await interaction.response.send_message(embed=self.NO_VOICE_CHANNEL_EMBED)
            return

        if position > len(music_player.next_queue) or position < 1:
            position = len(music_player.next_queue) + 1

        # Defer response due to long processing times when provided a large playlist
        await interaction.response.defer()

        try:
            songs = await self._get_songs(url, interaction.user)
        except SongUnavailableError:
            embed = discord.Embed(
                colour=constants.EmbedStatus.FAIL.value,
                description="That song is unavailable. Maybe the link is invalid?")
            await interaction.followup.send(embed=embed)
            return

        # Add playlist
        if songs[0].original_source == OriginalSource.YOUTUBE_PLAYLIST \
                or songs[0].original_source == OriginalSource.SPOTIFY_PLAYLIST:
            result = await music_player.add_multiple(songs, position-1)
            if result == PlayerResult.PLAYING:
                embed = discord.Embed(
                    colour=constants.EmbedStatus.YES.value,
                    description=f"Now playing playlist [{songs[0].group}]({songs[0].group_url})")
                await interaction.followup.send(embed=embed)
                return
            elif result == PlayerResult.QUEUEING:
                embed = discord.Embed(
                    colour=constants.EmbedStatus.YES.value,
                    description=f"Added `{len(songs)}` songs from playlist "
                                f"[{songs[0].group}]({songs[0].group_url}) to "
                                f"#{position} in queue")
                await interaction.followup.send(embed=embed)
                return

        # Add album
        if songs[0].original_source == OriginalSource.YOUTUBE_ALBUM \
                or songs[0].original_source == OriginalSource.SPOTIFY_ALBUM:
            result = await music_player.add_multiple(songs, position-1)
            if result == PlayerResult.PLAYING:
                embed = discord.Embed(
                    colour=constants.EmbedStatus.YES.value,
                    description=f"Now playing album [{songs[0].group}]({songs[0].group_url})")
                await interaction.followup.send(embed=embed)
                return
            elif result == PlayerResult.QUEUEING:
                embed = discord.Embed(
                    colour=constants.EmbedStatus.YES.value,
                    description=f"Added `{len(songs)}` songs from album "
                                f"[{songs[0].group}]({songs[0].group_url}) to "
                                f"#{position} in queue")
                await interaction.followup.send(embed=embed)
                return

        # Add song
        song = songs[0]
        result = await music_player.add(song, position-1)
        duration = await self._format_duration(song.duration)
        artist = ""
        if song.artist:
            artist = f"{song.artist} - "
        song_name = f"[{artist}{song.title}]({song.url}) `{duration}`"
        if result == PlayerResult.PLAYING:
            embed = discord.Embed(
                colour=constants.EmbedStatus.YES.value,
                description=f"Now playing {song_name}")
            await interaction.followup.send(embed=embed)
            return
        elif result == PlayerResult.QUEUEING:
            embed = discord.Embed(
                colour=constants.EmbedStatus.YES.value,
                description=f"Song {song_name} added to #{position} in queue")
            await interaction.followup.send(embed=embed)
            return

    @app_commands.command()
    @perms.check()
    async def playsearch(self, interaction: discord.Interaction, search: str):
        # Alert user if search term returns no results
        songs = await self._get_songs(search, interaction.user)
        if not songs:
            embed = discord.Embed(
                colour=constants.EmbedStatus.FAIL.value,
                description="Search query returned no results")
            await interaction.response.send_message(embed=embed)
            return

        # Format the data to be in a usable list
        results_format = []
        for i in range(0, 5):
            results_format.append(f"{i+1}. [{songs[i].title}]({songs[i].url}) `{songs[i].duration}`")

        # Output results to chat
        embed = discord.Embed(
            colour=constants.EmbedStatus.INFO.value,
            title=f"{constants.EmbedIcon.MUSIC} Search Query")
        results_output = '\n'.join(results_format)
        embed.add_field(
            name=f"Results for '{search}'",
            value=results_output, inline=False)
        await interaction.response.send_message(embed=embed)

    @app_commands.command()
    @perms.check()
    async def stop(self, interaction: discord.Interaction):
        """Stops and clears the queue"""
        if not interaction.guild.voice_client:
            await interaction.response.send_message(embed=self.NOT_CONNECTED_EMBED)
            return
        music_player = await self._get_music_player(interaction.user.voice.channel)

        await music_player.clear()
        await music_player.stop()
        embed = discord.Embed(
            colour=constants.EmbedStatus.YES.value,
            description="Music has been stopped & queue has been cleared")
        await interaction.response.send_message(embed=embed)

    @app_commands.command()
    @perms.check()
    async def resume(self, interaction):
        """Resumes music if paused"""
        if not interaction.guild.voice_client:
            await interaction.response.send_message(embed=self.NOT_CONNECTED_EMBED)
            return
        music_player = await self._get_music_player(interaction.user.voice.channel)

        # Alert if music isn't paused
        if not music_player.is_paused:
            embed = discord.Embed(
                colour=constants.EmbedStatus.FAIL.value,
                description="Music isn't paused")
            await interaction.response.send_message(embed=embed)
            return

        # Resumes music playback
        await music_player.resume()
        embed = discord.Embed(
            colour=constants.EmbedStatus.YES.value,
            description="Music has been resumed")
        await interaction.response.send_message(embed=embed)

    @app_commands.command()
    @perms.check()
    async def pause(self, interaction):
        """Pauses the music"""
        # Get music player
        if not interaction.guild.voice_client:
            await interaction.response.send_message(embed=self.NOT_CONNECTED_EMBED)
            return
        music_player = await self._get_music_player(interaction.user.voice.channel)

        # Check if music is paused
        if music_player.is_paused:
            embed = discord.Embed(
                colour=constants.EmbedStatus.FAIL.value,
                description="Music is already paused")
            await interaction.response.send_message(embed=embed)
            return

        # Pauses music playback
        await music_player.pause()
        embed = discord.Embed(
            colour=constants.EmbedStatus.YES.value,
            description="Music has been paused")
        await interaction.response.send_message(embed=embed)

    @app_commands.command()
    @perms.check()
    async def seek(self, interaction: discord.Interaction, timestamp: str):
        # Get music player
        if not interaction.guild.voice_client:
            await interaction.response.send_message(embed=self.NOT_CONNECTED_EMBED)
            return
        music_player = await self._get_music_player(interaction.user.voice.channel)

        # Pauses music playback
        seconds = self._parse_time(timestamp)
        await music_player.seek(seconds)
        embed = discord.Embed(
            colour=constants.EmbedStatus.YES.value,
            description=f"Song timeline moved to position `{timestamp}`")
        await interaction.response.send_message(embed=embed)

    @app_commands.command()
    @perms.check()
    async def skip(self, interaction: discord.Interaction):
        """Skip the current song and play the next song"""
        # Get music player
        if not interaction.guild.voice_client:
            await interaction.response.send_message(embed=self.NOT_CONNECTED_EMBED)
            return
        music_player = await self._get_music_player(interaction.user.voice.channel)

        # Check if there's queue is empty
        if len(music_player.next_queue) < 1:
            await interaction.response.send_message(embed=discord.Embed(
                colour=constants.EmbedStatus.FAIL.value,
                description="There's nothing in the queue after this."))
            return

        # Stop current song and flag that it has been skipped
        result = await music_player.next()
        if not result:
            await interaction.response.send_message(embed=discord.Embed(
                colour=constants.EmbedStatus.FAIL.value,
                description="Please slow down, you can't skip while the next song hasn't even started yet."))
            return
        await interaction.response.send_message(embed=discord.Embed(
            colour=constants.EmbedStatus.YES.value,
            description="Song has been skipped."))

    @app_commands.command()
    @perms.check()
    async def prev(self, interaction: discord.Interaction):
        """Go back in the queue to an already played song"""
        # Get music player
        if not interaction.guild.voice_client:
            await interaction.response.send_message(embed=self.NOT_CONNECTED_EMBED)
            return
        music_player = await self._get_music_player(interaction.user.voice.channel)

        # Check if there's queue is empty
        if len(music_player.previous_queue) < 1:
            await interaction.response.send_message(embed=discord.Embed(
                colour=constants.EmbedStatus.FAIL.value,
                description="There are no previously played songs."))
            return

        # Stop current song and flag that it has been skipped
        await music_player.previous()
        await interaction.response.send_message(embed=discord.Embed(
            colour=constants.EmbedStatus.YES.value,
            description="Playing previous song."))

    @app_commands.command()
    @perms.check()
    async def shuffle(self, interaction):
        """Randomly moves the contents of the queue around"""
        # Get music player
        if not interaction.guild.voice_client:
            await interaction.response.send_message(embed=self.NOT_CONNECTED_EMBED)
            return
        music_player = await self._get_music_player(interaction.user.voice.channel)

        # Alert if not enough songs in queue
        if len(music_player.next_queue) < 2:
            embed = discord.Embed(
                colour=constants.EmbedStatus.FAIL.value,
                description="There's nothing in the queue to shuffle")
            await interaction.response.send_message(embed=embed)
            return

        # Shuffle queue
        await music_player.shuffle()
        embed = discord.Embed(
            colour=constants.EmbedStatus.YES.value,
            description="Queue has been shuffled")
        await interaction.response.send_message(embed=embed)
        return

    @app_commands.command()
    @perms.check()
    async def loop(self, interaction):
        """Loop the currently playing song."""
        # Get music player
        if not interaction.guild.voice_client:
            await interaction.response.send_message(embed=self.NOT_CONNECTED_EMBED)
            return
        music_player = await self._get_music_player(interaction.user.voice.channel)

        # Disable loop if enabled
        if music_player.is_looping:
            embed = discord.Embed(
                colour=constants.EmbedStatus.FAIL.value,
                description="Song is already looping.")
            await interaction.response.send_message(embed=embed)
            return

        # Enable loop if disabled
        music_player.is_looping = True
        embed = discord.Embed(
            colour=constants.EmbedStatus.YES.value,
            description="Loop enabled.")
        await interaction.response.send_message(embed=embed)
        return

    @app_commands.command()
    @perms.check()
    async def unloop(self, interaction: discord.Interaction):
        """Unloops so that the queue resumes as usual."""
        # Get music player
        if not interaction.guild.voice_client:
            await interaction.response.send_message(embed=self.NOT_CONNECTED_EMBED)
            return
        music_player = await self._get_music_player(interaction.user.voice.channel)

        # Disable loop if enabled
        if not music_player.is_looping:
            embed = discord.Embed(
                colour=constants.EmbedStatus.FAIL.value,
                description="Song is not currently looping.")
            await interaction.response.send_message(embed=embed)
            return

        # Enable loop if disabled
        music_player.is_looping = False
        embed = discord.Embed(
            colour=constants.EmbedStatus.YES.value,
            description="Loop disabled.")
        await interaction.response.send_message(embed=embed)
        return

    @app_commands.command()
    async def song(self, interaction: discord.Interaction):
        """List information about the currently playing song."""
        # Get music player
        if not interaction.guild.voice_client:
            await interaction.response.send_message(embed=self.NOT_CONNECTED_EMBED)
            return
        music_player = await self._get_music_player(interaction.user.voice.channel)

        # Alert if nothing is playing
        song = music_player.playing
        if not song:
            await interaction.response.send_message(embed=discord.Embed(
                colour=constants.EmbedStatus.FAIL.value,
                description="There's nothing currently playing."))
            return

        # Output playing song
        duration = await self._format_duration(song.duration)
        current_time = await self._format_duration(music_player.seek_position)
        artist = ""
        if song.artist:
            artist = f"{song.artist} - "
        embed = discord.Embed(
            colour=constants.EmbedStatus.INFO.value,
            title=f"{constants.EmbedIcon.MUSIC} Currently Playing",
            description=f"[{artist}{song.title}]({song.url}) "
                  f"`{current_time}/{duration}`\n\u200B")

        if song.original_source == OriginalSource.YOUTUBE_ALBUM \
                or song.original_source == OriginalSource.SPOTIFY_ALBUM \
                or song.original_source == OriginalSource.YOUTUBE_PLAYLIST \
                or song.original_source == OriginalSource.SPOTIFY_PLAYLIST \
                or song.original_source == OriginalSource.LOCAL:
            embed.add_field(
                name=f"Fetched from {song.original_source.value}",
                value=f"[{song.group}]({song.group_url})",
                inline=False)
        elif song.original_source == OriginalSource.YOUTUBE_VIDEO:
            embed.add_field(
                name=f"Fetched from Site",
                value=f"[{song.original_source.value}](https://youtube.com)",
                inline=False)
        elif song.original_source == OriginalSource.YOUTUBE_SONG:
            embed.add_field(
                name=f"Fetched from Site",
                value=f"[{song.original_source.value}](https://music.youtube.com)",
                inline=False)
        elif song.original_source == OriginalSource.SPOTIFY_SONG:
            embed.add_field(
                name=f"Fetched from Site",
                value=f"[{song.original_source.value}](https://open.spotify.com)",
                inline=False)

        if song.artist:
            embed.add_field(
                name="Artist",
                value=f"{song.artist}")

        if song.requester_id:
            embed.add_field(
                name="Requested By",
                value=f"<@{song.requester_id}>")

        await interaction.response.send_message(embed=embed)

    @queue_group.command(name="list")
    @perms.check()
    async def queue_list(self, interaction: discord.Interaction, page: int = 1):
        """List the current song queue"""
        if not interaction.guild.voice_client:
            await interaction.response.send_message(embed=self.NOT_CONNECTED_EMBED)
            return
        music_player = await self._get_music_player(interaction.user.voice.channel)

        # Notify user if nothing is in the queue
        playing = music_player.playing
        queue = music_player.next_queue
        if not playing and not queue:
            embed = discord.Embed(
                colour=constants.EmbedStatus.FAIL.value,
                description="There's nothing in the queue right now.")
            await interaction.response.send_message(embed=embed)
            return

        # Output currently playing song
        embed = discord.Embed(
            colour=constants.EmbedStatus.INFO.value,
            title=f"{constants.EmbedIcon.MUSIC} Music Queue")
        header = "Currently Playing (Looping)" if music_player.is_looping else "Currently Playing"
        artist = f"{playing.artist} - " if playing.artist else ""
        current_time = await self._format_duration(music_player.seek_position)
        duration = await self._format_duration(playing.duration)
        spacer = "\u200B" if len(queue) >= 1 else ""
        embed.add_field(
            name=header,
            value=f"[{artist}{playing.title}]({playing.url}) "
                  f"`{current_time}/{duration}` \n{spacer}")

        # List songs in queue and calculate the total duration
        queue_display_items = []
        total_duration = 0
        for song in queue:
            total_duration += song.duration
            duration = await self._format_duration(song.duration)
            artist = f"{song.artist} - " if song.artist else ""
            queue_display_items.append(
                f"[{artist}{song.title}]({song.url}) `{duration}` | <@{playing.requester_id}>")

        # Output results to chat
        if queue_display_items:
            duration = await self._format_duration(total_duration)
            paginated_view = PaginatedView(embed, f"Queue  `{duration}`", queue_display_items, 5, page)
        else:
            paginated_view = EmptyPaginatedView(
                embed, f"Queue `0:00`", "Nothing else is queued up. Add more songs and they will appear here.")
        await paginated_view.send(interaction)

    @queue_group.command(name="prevlist")
    async def queue_prevlist(self, interaction: discord.Interaction, page: int = 1):
        """List the current song queue"""
        if not interaction.guild.voice_client:
            await interaction.response.send_message(embed=self.NOT_CONNECTED_EMBED)
            return
        music_player = await self._get_music_player(interaction.user.voice.channel)

        # Notify user if nothing is in the queue
        playing = music_player.playing
        queue = music_player.previous_queue
        if not playing and not queue:
            embed = discord.Embed(
                colour=constants.EmbedStatus.FAIL.value,
                description="There's nothing in the previous played song list.")
            await interaction.response.send_message(embed=embed)
            return

        # Output currently playing song
        embed = discord.Embed(
            colour=constants.EmbedStatus.INFO.value,
            title=f"{constants.EmbedIcon.MUSIC} Music Queue")
        header = "Currently Playing (Looping)" if music_player.is_looping else "Currently Playing"
        artist = f"{playing.artist} - " if playing.artist else ""
        current_time = await self._format_duration(music_player.seek_position)
        duration = await self._format_duration(playing.duration)
        spacer = "\u200B" if len(queue) >= 1 else ""
        embed.add_field(
            name=header,
            value=f"[{artist}{playing.title}]({playing.url}) "
                  f"`{current_time}/{duration}` \n{spacer}")

        # List remaining songs in queue plus total duration
        queue_display_items = []
        total_duration = 0
        for song in queue:
            total_duration += song.duration
            duration = await self._format_duration(song.duration)
            artist = f"{song.artist} - " if song.artist else ""
            queue_display_items.append(f"[{artist}{song.title}]({song.url}) `{duration}`")

        # Output results to chat
        if queue_display_items:
            duration = await self._format_duration(total_duration)
            paginated_view = PaginatedView(embed, f"Queue  `{duration}`", queue_display_items, 5, page)
        else:
            paginated_view = EmptyPaginatedView(
                embed, f"Queue `0:00`", "Nothing here yet. Songs that have previously played with appear here.")
        await paginated_view.send(interaction)

    @queue_group.command(name="reorder")
    @perms.check()
    async def queue_reorder(self, interaction, original_pos: int, new_pos: int):
        """Move a song to a different position in the queue"""
        # Get music player
        if not interaction.guild.voice_client:
            await interaction.response.send_message(embed=self.NOT_CONNECTED_EMBED)
            return
        music_player = await self._get_music_player(interaction.user.voice.channel)

        # Try to remove song from queue using the specified index
        queue = music_player.next_queue
        try:
            if original_pos < 1:
                raise IndexError("Position can\'t be be less than 1")
            song = queue[original_pos-1]
        except IndexError:
            embed = discord.Embed(
                colour=constants.EmbedStatus.FAIL.value,
                description="There's no song at that position")
            await interaction.response.send_message(embed=embed)
            return

        # Move song into new position in queue
        if not 1 <= new_pos <= len(queue):
            embed = discord.Embed(
                colour=constants.EmbedStatus.FAIL.value,
                description="You can't move the song into that position")
            await interaction.response.send_message(embed=embed)
            return
        await music_player.move(original_pos-1, new_pos-1)

        # Output result to chat
        duration = await self._format_duration(song.duration)
        embed = discord.Embed(
            colour=constants.EmbedStatus.YES.value,
            description=f"[{song.title}]({song.url}) "
                        f"`{duration}` has been moved from position #{original_pos} "
                        f"to position #{new_pos}")
        await interaction.response.send_message(embed=embed)

    @queue_group.command(name="remove")
    @perms.check()
    async def queue_remove(self, interaction, position: int):
        """Remove a song from the queue"""
        # Get music player
        if not interaction.guild.voice_client:
            await interaction.response.send_message(embed=self.NOT_CONNECTED_EMBED)
            return
        music_player = await self._get_music_player(interaction.user.voice.channel)

        # Try to remove song from queue using the specified index
        queue = music_player.next_queue
        try:
            if position < 1:
                raise IndexError('Position can\'t be less than 1')
            song = queue[position-1]
            await music_player.remove(position-1)
        except IndexError:
            embed = discord.Embed(
                colour=constants.EmbedStatus.FAIL.value,
                description="That's an invalid queue position.")
            await interaction.response.send_message(embed=embed)
            return

        # Output result to chat
        duration = await self._format_duration(song.duration)
        embed = discord.Embed(
            colour=constants.EmbedStatus.YES.value,
            description=f"[{song.title}]({song.url}) `{duration}` "
                        f"has been removed from position #{position} of the queue")
        await interaction.response.send_message(embed=embed)

    @queue_group.command(name="clear")
    @perms.check()
    async def queue_clear(self, interaction):
        """Clears the entire queue"""
        if not interaction.guild.voice_client:
            await interaction.response.send_message(embed=self.NOT_CONNECTED_EMBED)
            return
        music_player = await self._get_music_player(interaction.user.voice.channel)

        # Try to remove all but the currently playing song from the queue
        if len(music_player.next_queue) < 1:
            embed = discord.Embed(
                colour=constants.EmbedStatus.FAIL.value,
                description="There's nothing in the queue to clear")
            await interaction.response.send_message(embed=embed)
            return

        await music_player.clear()
        embed = discord.Embed(
            colour=constants.EmbedStatus.FAIL.value,
            description="All songs have been removed from the queue")
        await interaction.response.send_message(embed=embed)

    @playlist_group.command(name='create')
    @perms.check()
    async def playlist_create(self, interaction: discord.Interaction, playlist_name: str):
        """Create a new playlist"""
        # Limit playlist name to 30 chars
        if len(playlist_name) > 30:
            embed = discord.Embed(
                colour=constants.EmbedStatus.FAIL.value,
                description="Playlist name is too long")
            await interaction.response.send_message(embed=embed)
            return

        # Alert if playlist with specified name already exists
        if self.playlists.get_by_name_in_guild(playlist_name, interaction.guild):
            embed = discord.Embed(
                colour=constants.EmbedStatus.FAIL.value,
                description=f"Playlist `{playlist_name}` already exists")
            await interaction.response.send_message(embed=embed)
            return

        # Add playlist to database
        self.playlists.add(Playlist.create_new(playlist_name, interaction.guild, interaction.user))
        embed = discord.Embed(
            colour=constants.EmbedStatus.YES.value,
            description=f"Playlist `{playlist_name}` has been created")
        await interaction.response.send_message(embed=embed)

    @playlist_group.command(name='destroy')
    @perms.check()
    async def playlist_destroy(self, interaction, playlist_name: str):
        """Deletes an existing playlist"""
        # Alert if playlist doesn't exist in db
        playlist = self.playlists.get_by_name_in_guild(playlist_name, interaction.guild)
        if not playlist:
            await interaction.response.send_message(embed=discord.Embed(
                colour=constants.EmbedStatus.FAIL.value,
                description=f"Playlist `{playlist_name}` doesn't exist"))
            return

        # Remove playlist from database and all songs linked to it
        playlist_songs = self.playlist_songs.get_by_playlist(playlist.id)
        for song in playlist_songs:
            self.playlist_songs.remove(song.id)
        self.playlists.remove(playlist.id)
        embed = discord.Embed(
            colour=constants.EmbedStatus.YES.value,
            description=f"Playlist `{playlist_name}` has been destroyed")
        await interaction.response.send_message(embed=embed)

    @playlist_group.command(name='description')
    @perms.check()
    async def playlist_description(self, interaction, playlist_name: str, description: str):
        """Sets the description for the playlist"""
        # Alert if playlist doesn't exist
        playlist = self.playlists.get_by_name_in_guild(playlist_name, interaction.guild)
        if not playlist:
            embed = discord.Embed(
                colour=constants.EmbedStatus.FAIL.value,
                description=f"Playlist '{playlist_name}' doesn't exist")
            await interaction.response.send_message(embed=embed)
            return

        # Limit playlist description to 300 chars
        if len(description) > 300:
            embed = discord.Embed(
                colour=constants.EmbedStatus.FAIL.value,
                description="Description is too long")
            await interaction.response.send_message(embed=embed)
            return

        # Update playlist last modified
        playlist.modified_date = datetime.datetime.now(tz=datetime.timezone.utc)
        self.playlists.update(playlist)

        # Update playlist description
        playlist.description = description
        self.playlists.update(playlist)
        embed = discord.Embed(
            colour=constants.EmbedStatus.YES.value,
            description=f"Description set for playlist '{playlist_name}'")
        await interaction.response.send_message(embed=embed)

    @playlist_group.command(name='rename')
    @perms.check()
    async def playlist_rename(self, interaction, playlist_name: str, new_name: str):
        """Rename an existing playlist"""
        # Get the playlist
        playlist = self.playlists.get_by_name_in_guild(playlist_name, interaction.guild)
        if not playlist:
            embed = discord.Embed(
                colour=constants.EmbedStatus.FAIL.value,
                description=f"Playlist '{playlist_name}' doesn't exist")
            await interaction.response.send_message(embed=embed)
            return

        # Update playlist last modified
        playlist.modified_date = datetime.datetime.now(tz=datetime.timezone.utc)
        self.playlists.update(playlist)

        # Update playlist name
        playlist.name = new_name
        self.playlists.update(playlist)
        embed = discord.Embed(
            colour=constants.EmbedStatus.YES.value,
            description=f"Playlist '{playlist_name}' has been renamed to '{new_name}'")
        await interaction.response.send_message(embed=embed)

    @playlist_group.command(name='list')
    @perms.check()
    async def playlist_list(self, interaction: discord.Interaction, page: int = 1):
        """List all available playlists"""
        # Get playlist from repo
        playlists = self.playlists.get_by_guild(interaction.guild)
        if not playlists:
            embed = discord.Embed(
                colour=constants.EmbedStatus.FAIL.value,
                description="There are no playlists available")
            await interaction.response.send_message(embed=embed)
            return

        # Format playlist info
        playlist_info = []
        for playlist in playlists:
            songs = self.playlist_songs.get_by_playlist(playlist.id)
            song_duration = 0
            for song in songs:
                song_duration += song.duration
            duration = await self._format_duration(song_duration)
            playlist_info.append(f"{playlist.name} `{duration}` | Created by <@{playlist.creator_id}>")

        # Output results to chat
        embed = discord.Embed(
            colour=constants.EmbedStatus.INFO.value,
            title=f"{constants.EmbedIcon.MUSIC} Music Playlists")
        paginated_view = PaginatedView(embed, f"{len(playlists)} available", playlist_info, 5, page)
        await paginated_view.send(interaction)

    @playlist_group.command(name='add')
    @perms.check()
    async def playlist_add(self, interaction, playlist_name: str, url: str):
        """Adds a song to a playlist"""
        # Get playlist from repo
        playlist = self.playlists.get_by_name_in_guild(playlist_name, interaction.guild)
        if not playlist:
            embed = discord.Embed(
                colour=constants.EmbedStatus.FAIL.value,
                description="There are no playlists available")
            await interaction.response.send_message(embed=embed)
            return

        # Check if playlist limit has been reached
        playlist_songs = self.playlist_songs.get_by_playlist(playlist.id)
        if len(playlist_songs) > 100:
            embed = discord.Embed(
                colour=constants.EmbedStatus.FAIL.value,
                description="There's too many songs in the playlist. Remove"
                            "some songs to be able to add more")
            await interaction.response.send_message(embed=embed)
            return

        # Defer response due to long processing times when provided a large playlist
        await interaction.response.defer()

        # Find song from the specified query
        try:
            songs = await self._get_songs(url, interaction.user)
        except SongUnavailableError:
            embed = discord.Embed(
                colour=constants.EmbedStatus.FAIL.value,
                description="That song is unavailable. Maybe the link is invalid?")
            await interaction.followup.send(embed=embed)
            return

        # Update playlist last modified
        playlist.modified_date = datetime.datetime.now(tz=datetime.timezone.utc)
        self.playlists.update(playlist)

        # Set previous song as the last song in the playlist
        if not playlist_songs:
            previous_id = uuid.UUID(int=0)
        else:
            song_ids = []
            previous_ids = []
            for playlist_song in playlist_songs:
                song_ids.append(playlist_song.id)
                previous_ids.append(playlist_song.previous_id)
            previous_id = list(set(song_ids) - set(previous_ids))[0]

        # Add playlist
        if songs[0].original_source == OriginalSource.YOUTUBE_PLAYLIST \
                or songs[0].original_source == OriginalSource.SPOTIFY_PLAYLIST:
            for song in songs:
                new_playlist_song = PlaylistSong.create_new(
                    playlist.id, interaction.user.id, song.title, song.artist, song.duration, song.url, previous_id)
                self.playlist_songs.add(new_playlist_song)
                previous_id = new_playlist_song.id
            embed = discord.Embed(
                colour=constants.EmbedStatus.YES.value,
                description=f"Added `{len(songs)}` songs from playlist "
                            f"[{songs[0].group}]({songs[0].group_url}) to "
                            f"#{len(playlist_songs) + 1} in playlist '{playlist_name}'")
            await interaction.followup.send(embed=embed)
            return

        # Add album
        if songs[0].original_source == OriginalSource.YOUTUBE_ALBUM \
                or songs[0].original_source == OriginalSource.SPOTIFY_ALBUM:
            for song in songs:
                new_playlist_song = PlaylistSong.create_new(
                    playlist.id, interaction.user.id, song.title, song.artist, song.duration, song.url, previous_id)
                self.playlist_songs.add(new_playlist_song)
                previous_id = new_playlist_song.id
            embed = discord.Embed(
                colour=constants.EmbedStatus.YES.value,
                description=f"Added `{len(songs)}` songs from album "
                            f"[{songs[0].group}]({songs[0].group_url}) to "
                            f"#{len(playlist_songs) + 1} in playlist '{playlist_name}'")
            await interaction.followup.send(embed=embed)
            return

        song = songs[0]
        new_playlist_song = PlaylistSong.create_new(
            playlist.id, interaction.user.id, song.title, song.artist, song.duration, song.url, previous_id)
        self.playlist_songs.add(new_playlist_song)
        artist = ""
        if songs[0].artist:
            artist = f"{songs[0].artist} - "
        await interaction.followup.send(embed=discord.Embed(
            colour=constants.EmbedStatus.YES.value,
            description=f"Added [{artist}{songs[0].title}]({songs[0].url}) "
                        f"`{await self._format_duration(songs[0].duration)}` to position #{len(playlist_songs) + 1} "
                        f"in playlist '{playlist_name}'"))

    @playlist_group.command(name='remove')
    @perms.check()
    async def playlist_remove(self, interaction, playlist_name: str, index: int):
        """Removes a song from a playlist"""
        # Get playlist from repo
        playlist = self.playlists.get_by_name_in_guild(playlist_name, interaction.guild)
        if not playlist:
            embed = discord.Embed(
                colour=constants.EmbedStatus.FAIL.value,
                description=f"Playlist `{playlist_name}` doesn't exist")
            await interaction.response.send_message(embed=embed)
            return

        # Fetch selected song and the song after
        songs: list[PlaylistSong] = await self._order_playlist_songs(self.playlist_songs.get_by_playlist(playlist.id))
        selected_song = songs[int(index) - 1]

        # Edit next song's previous song id if it exists
        try:
            next_song = songs[int(index)]
            next_song.previous_id = selected_song.previous_id
            self.playlist_songs.update(next_song)
        except IndexError:
            pass

        # Update playlist last modified
        playlist.modified_date = datetime.datetime.now(tz=datetime.timezone.utc)
        self.playlists.update(playlist)

        # Remove selected song from playlist
        self.playlist_songs.remove(selected_song.id)
        duration = await self._format_duration(selected_song.duration)
        embed = discord.Embed(
            colour=constants.EmbedStatus.FAIL.value,
            description=f"[{selected_song.title}]({selected_song.url}) "
                        f"`{duration}` has been removed from `{playlist_name}`")
        await interaction.response.send_message(embed=embed)

    @playlist_group.command(name='reorder')
    @perms.check()
    async def playlist_reorder(self, interaction, playlist_name: str, original_pos: int, new_pos: int):
        """Moves a song to a specified position in a playlist"""
        # Get playlist from repo
        playlist = self.playlists.get_by_name_in_guild(playlist_name, interaction.guild)
        if not playlist:
            embed = discord.Embed(
                colour=constants.EmbedStatus.FAIL.value,
                description=f"Playlist `{playlist_name}` doesn't exist")
            await interaction.response.send_message(embed=embed)
            return

        songs = await self._order_playlist_songs(self.playlist_songs.get_by_playlist(playlist.id))

        if new_pos > len(songs):
            new_pos = len(songs)
        elif new_pos < 1:
            new_pos = 1

        selected_song = songs[original_pos - 1]
        song_at_new_position = songs[new_pos - 1]

        # If moving up, song after new position should be re-referenced to moved song
        if new_pos > original_pos:
            selected_song.previous_id = song_at_new_position.id
            try:
                song_after_new_position = songs[new_pos]
                song_after_new_position.previous_id = selected_song.id
                self.playlist_songs.update(song_after_new_position)
            except IndexError:
                pass

        # If moving down, song at new position should be re-referenced to moved song
        else:
            selected_song.previous_id = song_at_new_position.previous_id
            song_at_new_position.previous_id = selected_song.id
            self.playlist_songs.update(song_at_new_position)

        # Fill in the gap at the original song position
        try:
            song_after_old_position = songs[original_pos]
            song_before_old_position = songs[original_pos - 2]
            song_after_old_position.previous_id = song_before_old_position.id
            self.playlist_songs.update(song_after_old_position)
        except IndexError:
            pass

        # Update playlist last modified
        playlist.modified_date = datetime.datetime.now(tz=datetime.timezone.utc)
        self.playlists.update(playlist)

        # Output result to chat
        self.playlist_songs.update(selected_song)
        duration = await self._format_duration(selected_song.duration)
        embed = discord.Embed(
            colour=constants.EmbedStatus.YES.value,
            description=f"[{selected_song.title}]({selected_song.url}) "
                        f"`{duration}` has been moved to position #{new_pos} "
                        f"in playlist '{playlist_name}'")
        await interaction.response.send_message(embed=embed)

    @playlist_group.command(name='view')
    @perms.check()
    async def playlist_view(self, interaction, playlist_name: str, page: int = 1):
        """List all songs in a playlist"""
        # Fetch songs from playlist if it exists
        playlist = self.playlists.get_by_name_in_guild(playlist_name, interaction.guild)
        if not playlist:
            embed = discord.Embed(
                colour=constants.EmbedStatus.FAIL.value,
                description=f"Playlist `{playlist_name}` does not exist")
            await interaction.response.send_message(embed=embed)
            return
        songs = await self._order_playlist_songs(self.playlist_songs.get_by_playlist(playlist.id))

        # Format the text of each song
        total_duration = 0
        formatted_songs = []
        for song in songs:
            total_duration += song.duration
            song_name = song.title[:87] + "..." if len(song.title) > 90 else song.title
            duration = await self._format_duration(song.duration)
            artist = f"{song.artist} - " if song.artist else ""
            formatted_songs.append(f"[{artist}{song_name}]({song.url}) `{duration}` | <@{song.requester_id}>")

        # Output results to chat
        embed = discord.Embed(
            colour=constants.EmbedStatus.INFO.value,
            title=f"{constants.EmbedIcon.MUSIC} Playlist '{playlist_name}'")
        embed.description = f"Created by: <@{playlist.creator_id}>\n"
        embed.description += playlist.description + "\n\u200B" if playlist.description else "\u200B"
        formatted_duration = await self._format_duration(total_duration)
        paginated_view = PaginatedView(embed, f"{len(songs)} Songs `{formatted_duration}`", formatted_songs, 5, page)
        await paginated_view.send(interaction)

    @playlist_group.command(name='play')
    @perms.check()
    async def playlist_play(self, interaction: discord.Interaction, playlist_name: str):
        """Play from a locally saved playlist"""
        # Get music player
        try:
            music_player = await self._get_music_player(interaction.user.voice.channel)
        except AttributeError:
            await interaction.response.send_message(embed=self.NO_VOICE_CHANNEL_EMBED)
            return

        # Fetch songs from playlist if it exists
        playlist = self.playlists.get_by_name_in_guild(playlist_name, interaction.guild)
        if not playlist:
            embed = discord.Embed(
                colour=constants.EmbedStatus.FAIL.value,
                description=f"Playlist `{playlist_name}` does not exist")
            await interaction.response.send_message(embed=embed)
            return

        songs = await self._order_playlist_songs(self.playlist_songs.get_by_playlist(playlist.id))
        if not songs:
            embed = discord.Embed(
                colour=constants.EmbedStatus.FAIL.value,
                description=f"Playlist `{playlist.name}` does not contain any songs")
            await interaction.response.send_message(embed=embed)
            return

        stream = await self._get_song_from_saved(songs[0], playlist, interaction.user)
        result = await music_player.add(stream[0])
        if result == PlayerResult.PLAYING:
            embed = discord.Embed(
                colour=constants.EmbedStatus.YES.value,
                description=f"Now playing saved playlist '{playlist.name}'")
            await interaction.response.send_message(embed=embed)
        else:
            embed = discord.Embed(
                colour=constants.EmbedStatus.YES.value,
                description=f"Adding saved playlist '{playlist.name}' to queue")
            await interaction.response.send_message(embed=embed)

        # Add remaining songs to queue
        for i in range(1, len(songs)):
            stream = await self._get_song_from_saved(songs[i], playlist, interaction.user)
            await music_player.add(stream[0])

    @musicsettings_group.command(name='autodisconnect')
    @perms.exclusive()
    async def musicsettings_autodisconnect(self, interaction):
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
        await interaction.response.send_message(embed=embed)

    @musicsettings_group.command(name='disconnecttime')
    @perms.exclusive()
    async def musicsettings_disconnecttime(self, interaction, seconds: int):
        """Sets a time for when the bot should auto disconnect from voice if not playing"""
        config = toml.load(constants.DATA_DIR + 'config.toml')

        # Set disconnect_time config variable
        config['music']['disconnect_time'] = seconds
        with open(constants.DATA_DIR + 'config.toml', 'w') as config_file:
            toml.dump(config, config_file)

        embed = discord.Embed(
            colour=constants.EmbedStatus.YES.value,
            description=f"Music player auto disconnect timer set to {seconds} seconds")
        await interaction.response.send_message(embed=embed)
        return

    async def _get_music_player(self, channel: discord.VoiceChannel) -> WavelinkMusicPlayer:
        """
        Retrieves the music player associated with the given voice channel.

        Args:
            channel (discord.VoiceChannel): The voice channel for which to retrieve the music player.

        Returns:
            WavelinkMusicPlayer: The music player associated with the given voice channel.
        """
        try:
            music_player = self.music_players[channel.guild.id]
        except KeyError:
            music_player = WavelinkMusicPlayer()
            await music_player.connect(channel)
            self.music_players[channel.guild.id] = music_player
        return music_player

    @staticmethod
    async def _get_songs(query: str, requester: discord.User) -> list['WavelinkSong']:
        """
        Get songs based on a query and requester.

        Args:
            query (str): The query used to search for songs.
            requester (discord.User): The user requesting the songs.

        Returns:
            list['WavelinkSong']: A list of WavelinkSong objects representing the songs.
        """
        return await WavelinkSong.from_query(query, requester)

    @staticmethod
    async def _get_song_from_saved(playlist_song: PlaylistSong, playlist: Playlist, requester: discord.User) -> list['WavelinkSong']:
        """
        Get a song from a saved playlist.

        Args:
            playlist_song (PlaylistSong): The playlist song object.
            playlist (Playlist): The playlist object.
            requester (discord.User): The user requesting the song.

        Returns:
            WavelinkSong: The song object obtained from the saved playlist.
        """
        return await WavelinkSong.from_local(requester, playlist_song, playlist)

    @staticmethod
    async def _format_duration(milliseconds) -> str:
        """
        Format the duration in milliseconds into a human-readable format.

        Args:
            milliseconds (int): The duration in milliseconds.

        Returns:
            str: The formatted duration in the format HH:MM:SS.
        """
        # Convert milliseconds to seconds
        seconds = milliseconds // 1000

        hours, remainder = divmod(seconds, 3600)
        minutes, seconds = divmod(remainder, 60)

        formatted = ""
        if hours:
            if hours < 10:
                formatted += f"0{str(hours)}:"
            else:
                formatted += f"{str(hours)}:"

        if minutes:
            if minutes < 10:
                formatted += f"0{minutes}:"
            else:
                formatted += f"{minutes}:"
        else:
            if hours:
                formatted += "00:"
            else:
                formatted += "0:"

        if seconds:
            if seconds < 10:
                formatted += f"0{seconds}"
            else:
                formatted += f"{seconds}"
        else:
            formatted += "00"

        return formatted


    @staticmethod
    async def _order_playlist_songs(playlist_songs) -> list[PlaylistSong]:
        """
        Orders a list of playlist songs based on their song ID ordering.

        Args:
            playlist_songs (List[PlaylistSong]): A list of playlist songs.

        Returns:
            List[PlaylistSong]: A list of playlist songs ordered based on their previous song IDs.

        """
        # Use dictionary to pair songs with the next song
        song_links = {}
        for song in playlist_songs:
            song_links[song.previous_id] = song

        # Order playlist songs into list
        ordered_songs = []
        next_song = song_links.get(uuid.UUID(int=0))
        while next_song is not None:
            ordered_songs.append(next_song)
            next_song = song_links.get(next_song.id)

        return ordered_songs

    @staticmethod
    def _parse_time(time_string) -> int:
        """
        Parses a time string and returns the equivalent time in milliseconds.

        Args:
            time_string (str): The time string to be parsed. The string should be in the format HH:MM:SS or MM:SS.

        Returns:
            int: The equivalent time in milliseconds.
        """
        time_split = time_string.split(':')
        hours, minutes, seconds = 0, 0, 0
        if len(time_split) >= 3:
            hours = time_split[-3]
        if len(time_split) >= 2:
            minutes = time_split[-2]
        if len(time_split) >= 1:
            seconds = time_split[-1]
        return int(hours) * 3600000 + int(minutes) * 60000 + int(seconds) * 1000


async def setup(bot):
    await bot.add_cog(Musicbox(bot))
