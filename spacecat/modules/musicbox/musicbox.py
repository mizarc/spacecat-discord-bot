"""
This module provides a cog for music related functionality.

Features within this module include the ability to stream music from
YouTube and other sources, as well as the ability to save playlists of
songs.

The provided commands are expected to be used while the user is in a
voice channel with the bot, and shouldn't be used in DMs.
"""

from __future__ import annotations

import datetime
import sqlite3
import uuid
from typing import TYPE_CHECKING, Self

import discord
import wavelink
from discord import app_commands
from discord.ext import commands

from spacecat.helpers import constants, permissions
from spacecat.helpers.views import EmptyPaginatedView, PaginatedView
from spacecat.modules.musicbox.music_player import (
    OriginalSource,
    PlayerResult,
    Song,
    SongUnavailableError,
)
from spacecat.modules.musicbox.players.wavelink_player import WavelinkMusicPlayer, WavelinkSong
from spacecat.modules.musicbox.playlist import (
    Playlist,
    PlaylistRepository,
    PlaylistSong,
    PlaylistSongRepository,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

    from spacecat.modules.musicbox.music_player import MusicPlayer
    from spacecat.spacecat import SpaceCat

MINIMUM_QUEUE_SIZE = 2
MAX_PLAYLIST_NAME_LENGTH = 30
MAX_PLAYLIST_DESCRIPTION_LENGTH = 300
MAX_DISPLAY_SONG_NAME_LENGTH = 90
PLAYLIST_SONG_LIMIT = 100

VocalGuildChannel = discord.VoiceChannel | discord.StageChannel


class Musicbox(commands.Cog):
    """Stream your favourite beats right to your local VC."""

    NOT_IN_SERVER_EMBED = discord.Embed(
        colour=constants.EmbedStatus.FAIL.value,
        description="You can't run this command in DMs.",
    )

    NOT_CONNECTED_EMBED = discord.Embed(
        colour=constants.EmbedStatus.FAIL.value,
        description="I need to be in a voice channel to execute music commands. \nUse **/join** "
        "or **/play** to connect me to a channel.",
    )

    NOT_USER_CONNECTED_EMBED = discord.Embed(
        colour=constants.EmbedStatus.FAIL.value,
        description="You need to be in a voice channel with the bot to perform this action.",
    )

    NOT_SUPPORTED_EMBED = discord.Embed(
        colour=constants.EmbedStatus.FAIL.value,
        description="I'm not in a supported voice channel.",
    )

    def __init__(self: Musicbox, bot: SpaceCat) -> None:
        """
        Initializes a new instance of the Musicbox class.

        Args:
            bot (commands.Bot): The Discord bot instance.
        """
        self.bot = bot
        self.music_players: dict[int, MusicPlayer] = {}
        self.database = sqlite3.connect(constants.DATA_DIR + "spacecat.db")
        self.playlists = PlaylistRepository(self.database)
        self.playlist_songs = PlaylistSongRepository(self.database)
        self.player_type = "wavelink"

    async def cog_load(self: Self) -> None:
        """Initialises configurations on cog load."""
        await self.init_config()
        await self.init_wavelink()

    async def init_config(self: Self) -> None:
        """
        Initialises configuration settings for the music streaming.

        Loads the config file, sets default values for lavalink
        address, port, and password if not present, and writes the
        updated config back to the file.
        """
        config = self.bot.instance.get_config()
        if "lavalink" not in config:
            config["lavalink"] = {}
        if "address" not in config["lavalink"]:
            config["lavalink"]["address"] = "http://localhost"
        if "port" not in config["lavalink"]:
            config["lavalink"]["port"] = "2333"
        if "password" not in config["lavalink"]:
            config["lavalink"]["password"] = "password1"  # noqa: S105

        self.bot.instance.save_config(config)

    async def init_wavelink(self: Self) -> None:
        """
        Initializes the Wavelink client for music streaming.

        This function loads the configuration settings from the
        instance's config. It creates a Wavelink node using the provided
        address, port, and password. Then, it connects the Wavelink
        client to the node using the provided Discord bot.
        """
        config = self.bot.instance.get_config()
        node = wavelink.Node(
            uri=f"{config['lavalink']['address']}:{config['lavalink']['port']}",
            password=config["lavalink"]["password"],
        )
        await wavelink.Pool.connect(nodes=[node], client=self.bot)

    @commands.Cog.listener()
    async def on_ready(self: Self) -> None:
        """Initialises configurations on cog load."""
        # Add config keys
        config = self.bot.instance.get_config()
        if "music" not in config:
            config["music"] = {}
        if "auto_disconnect" not in config["music"]:
            config["music"]["auto_disconnect"] = True
        if "disconnect_time" not in config["music"]:
            config["music"]["disconnect_time"] = 300
        self.bot.instance.save_config(config)

    @commands.Cog.listener()
    async def on_voice_state_update(
        self: Self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState
    ) -> None:
        """Disconnect the bot if the last user leaves the channel."""
        # If bot disconnects from voice, remove music player
        if self.bot.user and member.id == self.bot.user.id and after.channel is None:
            try:
                music_player = self.music_players.pop(member.guild.id)
                await music_player.disable_auto_disconnect()
            except KeyError:
                pass

        # Check if bot voice client isn't active
        voice_client = member.guild.voice_client
        if not voice_client or not isinstance(voice_client.channel, VocalGuildChannel):
            return

        # Check if auto channel disconnect is disabled
        config = self.bot.instance.get_config()
        if not config["music"]["auto_disconnect"]:
            return

        # Check if user isn't in same channel or not a disconnect/move event
        if voice_client.channel != before.channel or before.channel == after.channel:
            return

        # Disconnect if the bot is the only user left
        min_users = 2
        if len(voice_client.channel.members) < min_users:
            await voice_client.disconnect(force=False)

    @commands.Cog.listener()
    async def on_wavelink_track_end(self: Self, payload: wavelink.TrackEndEventPayload) -> None:
        """
        Listener that processses actions when a track ends.

        Args:
            payload (wavelink.TrackEndEventPayload): The payload
                containing information about the track that ended.
        """
        if payload.player is None:
            return

        music_player = await self._get_music_player(payload.player.channel)
        await music_player.process_song_end()

    queue_group = app_commands.Group(
        name="queue", description="Handles songs that will be played next."
    )
    playlist_group = app_commands.Group(
        name="playlist", description="Saved songs that can be played later."
    )
    musicsettings_group = app_commands.Group(
        name="musicsettings", description="Modify music settings."
    )

    @app_commands.command()
    @permissions.check()
    async def join(
        self: Self,
        interaction: discord.Interaction,
        channel: discord.VoiceChannel | discord.StageChannel | None = None,
    ) -> None:
        """Joins a voice channel."""
        # Alert if user is not running command in server
        if interaction.guild is None or not isinstance(interaction.user, discord.Member):
            embed = discord.Embed(
                colour=constants.EmbedStatus.FAIL.value,
                description="You can't run this command in DMs.",
            )
            await interaction.response.send_message(embed=embed)
            return

        # Set channel to join to specified, otherwise use user's current channel
        if channel:
            channel_to_join = channel
        elif interaction.user.voice:
            channel_to_join = interaction.user.voice.channel

        # Alert if user is not in a voice channel and no channel is specified
        if channel_to_join is None:
            embed = discord.Embed(
                colour=constants.EmbedStatus.FAIL.value,
                description="You must be in or specify a voice channel.",
            )
            await interaction.response.send_message(embed=embed)
            return

        # Alert if the specified voice channel is the same as the current channel
        if interaction.guild.voice_client and channel == interaction.guild.voice_client.channel:
            embed = discord.Embed(
                colour=constants.EmbedStatus.FAIL.value,
                description="I'm already in that voice channel",
            )
            await interaction.response.send_message(embed=embed)
            return

        # Joins player's current voice channel
        if interaction.guild.voice_client is None:
            if interaction.user.voice is None:
                return
            await self._get_music_player(channel_to_join)
            embed = discord.Embed(
                colour=constants.EmbedStatus.YES.value,
                description=f"Joined voice channel `{channel_to_join.name}`",
            )
            await interaction.response.send_message(embed=embed)
            return

        # Move to specified channel if already connected
        if isinstance(interaction.guild.voice_client, discord.VoiceClient | discord.StageChannel):
            previous_channel_name = interaction.guild.voice_client.channel.name
            await interaction.guild.voice_client.move_to(channel)
            embed = discord.Embed(
                colour=constants.EmbedStatus.YES.value,
                description=(
                    f"Moved from voice channel `{previous_channel_name}` "
                    f"to voice channel `{channel_to_join.name}`"
                ),
            )
            await interaction.response.send_message(embed=embed)
            return

    @app_commands.command()
    @permissions.check()
    async def leave(self: Self, interaction: discord.Interaction) -> None:
        """Stops and leaves the voice channel."""
        music_player, voice_channel = await self._find_music_player(interaction)
        if music_player is None or voice_channel is None:
            return

        await music_player.disconnect()
        embed = discord.Embed(
            colour=constants.EmbedStatus.YES.value,
            description=f"Disconnected from voice channel `{voice_channel.name}`",
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command()
    @permissions.check()
    async def play(
        self: Self, interaction: discord.Interaction, url: str, position: int = -1
    ) -> None:
        """Plays from a url or search query."""
        music_player, voice_channel = await self._find_or_create_music_player(interaction)

        if music_player is None or voice_channel is None:
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
                description="That song is unavailable. Maybe the link is invalid?",
            )
            await interaction.followup.send(embed=embed)
            return

        if not songs:
            embed = discord.Embed(
                colour=constants.EmbedStatus.FAIL.value,
                description="No songs found. Please check the link and try again.",
            )
            await interaction.followup.send(embed=embed)
            return

        # Determine the source type and add songs accordingly
        source_type = songs[0].original_source
        if source_type in (
            OriginalSource.YOUTUBE_PLAYLIST,
            OriginalSource.SPOTIFY_PLAYLIST,
            OriginalSource.YOUTUBE_ALBUM,
            OriginalSource.SPOTIFY_ALBUM,
        ):
            result = await music_player.add_multiple(songs, position - 1)
            type_name = "playlist" if "PLAYLIST" in source_type.name else "album"
            embed_description = (
                f"Now playing {type_name} [{songs[0].group}]({songs[0].group_url})"
                if result == PlayerResult.PLAYING
                else f"Added `{len(songs)}` songs from {type_name} "
                f"[{songs[0].group}]({songs[0].group_url}) to "
                f"#{position} in queue"
            )
        else:
            song = songs[0]
            result = await music_player.add(song, position - 1)
            duration = await self._format_duration(song.duration)
            artist = f"{song.artist} - " if song.artist else ""
            song_name = f"[{artist}{song.title}]({song.url}) `{duration}`"
            embed_description = (
                f"Now playing {song_name}"
                if result == PlayerResult.PLAYING
                else f"Song {song_name} added to #{position} in queue"
            )

        embed_colour = constants.EmbedStatus.YES.value
        embed = discord.Embed(colour=embed_colour, description=embed_description)
        await interaction.followup.send(embed=embed)

    @app_commands.command()
    @permissions.check()
    async def playsearch(self: Self, interaction: discord.Interaction, search: str) -> None:
        """Queries a list of songs to play."""
        # Alert user if search term returns no results
        songs = await self._get_songs(search, interaction.user)
        if not songs:
            embed = discord.Embed(
                colour=constants.EmbedStatus.FAIL.value,
                description="Search query returned no results",
            )
            await interaction.response.send_message(embed=embed)
            return

        # Format the data to be in a usable list
        results_format = [
            f"{i+1}. [{song.title}]({song.url}) `{song.duration}`"
            for i, song in enumerate(songs[:5])
        ]

        # Output results to chat
        embed = discord.Embed(
            colour=constants.EmbedStatus.INFO.value,
            title=f"{constants.EmbedIcon.MUSIC} Search Query",
        )
        results_output = "\n".join(results_format)
        embed.add_field(name=f"Results for '{search}'", value=results_output, inline=False)
        await interaction.response.send_message(embed=embed)

    @app_commands.command()
    @permissions.check()
    async def stop(self: Self, interaction: discord.Interaction) -> None:
        """Stops and clears the queue."""
        music_player, _ = await self._find_music_player(interaction)
        if music_player is None:
            return

        await music_player.clear()
        await music_player.stop()
        embed = discord.Embed(
            colour=constants.EmbedStatus.YES.value,
            description="Music has been stopped & queue has been cleared",
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command()
    @permissions.check()
    async def resume(self: Self, interaction: discord.Interaction) -> None:
        """Resumes music if paused."""
        music_player, _ = await self._find_music_player(interaction)
        if music_player is None:
            return

        # Alert if music isn't paused
        if not music_player.is_paused:
            embed = discord.Embed(
                colour=constants.EmbedStatus.FAIL.value,
                description="Music isn't paused",
            )
            await interaction.response.send_message(embed=embed)
            return

        # Resumes music playback
        await music_player.resume()
        embed = discord.Embed(
            colour=constants.EmbedStatus.YES.value, description="Music has been resumed"
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command()
    @permissions.check()
    async def pause(self: Self, interaction: discord.Interaction) -> None:
        """Pauses the music."""
        music_player, _ = await self._find_music_player(interaction)
        if music_player is None:
            return

        # Check if music is paused
        if music_player.is_paused:
            embed = discord.Embed(
                colour=constants.EmbedStatus.FAIL.value,
                description="Music is already paused",
            )
            await interaction.response.send_message(embed=embed)
            return

        # Pauses music playback
        await music_player.pause()
        embed = discord.Embed(
            colour=constants.EmbedStatus.YES.value, description="Music has been paused"
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command()
    @permissions.check()
    async def seek(self: Self, interaction: discord.Interaction, timestamp: str) -> None:
        """Seeks to a specific position in the song."""
        music_player, voice_channel = await self._find_music_player(interaction)
        if music_player is None or voice_channel is None:
            return

        seconds = self._parse_time(timestamp)
        await music_player.seek(seconds)
        embed = discord.Embed(
            colour=constants.EmbedStatus.YES.value,
            description=f"Song timeline moved to position `{timestamp}`",
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command()
    @permissions.check()
    async def skip(self: Self, interaction: discord.Interaction) -> None:
        """Skip the current song and play the next song."""
        music_player, _ = await self._find_music_player(interaction)
        if music_player is None:
            return

        # Check if there's queue is empty
        if len(music_player.next_queue) < 1:
            await interaction.response.send_message(
                embed=discord.Embed(
                    colour=constants.EmbedStatus.FAIL.value,
                    description="There's nothing in the queue after this.",
                )
            )
            return

        # Stop current song and flag that it has been skipped
        result = await music_player.next()
        if not result:
            await interaction.response.send_message(
                embed=discord.Embed(
                    colour=constants.EmbedStatus.FAIL.value,
                    description="Please slow down, you can't skip while "
                    "the next song hasn't even started yet.",
                )
            )
            return
        await interaction.response.send_message(
            embed=discord.Embed(
                colour=constants.EmbedStatus.YES.value,
                description="Song has been skipped.",
            )
        )

    @app_commands.command()
    @permissions.check()
    async def prev(self: Self, interaction: discord.Interaction) -> None:
        """Go back in the queue to an already played song."""
        music_player, _ = await self._find_music_player(interaction)
        if music_player is None:
            return

        # Check if there's queue is empty
        if len(music_player.previous_queue) < 1:
            await interaction.response.send_message(
                embed=discord.Embed(
                    colour=constants.EmbedStatus.FAIL.value,
                    description="There are no previously played songs.",
                )
            )
            return

        # Stop current song and flag that it has been skipped
        await music_player.previous()
        await interaction.response.send_message(
            embed=discord.Embed(
                colour=constants.EmbedStatus.YES.value,
                description="Playing previous song.",
            )
        )

    @app_commands.command()
    @permissions.check()
    async def shuffle(self: Self, interaction: discord.Interaction) -> None:
        """Randomly moves the contents of the queue around."""
        music_player, _ = await self._find_music_player(interaction)
        if music_player is None:
            return

        # Alert if not enough songs in queue
        if len(music_player.next_queue) < MINIMUM_QUEUE_SIZE:
            embed = discord.Embed(
                colour=constants.EmbedStatus.FAIL.value,
                description="There's nothing in the queue to shuffle",
            )
            await interaction.response.send_message(embed=embed)
            return

        # Shuffle queue
        await music_player.shuffle()
        embed = discord.Embed(
            colour=constants.EmbedStatus.YES.value,
            description="Queue has been shuffled",
        )
        await interaction.response.send_message(embed=embed)
        return

    @app_commands.command()
    @permissions.check()
    async def loop(self: Self, interaction: discord.Interaction) -> None:
        """Loop the currently playing song."""
        # Get music player
        music_player, _ = await self._find_music_player(interaction)
        if music_player is None:
            return

        # Disable loop if enabled
        if music_player.is_looping:
            embed = discord.Embed(
                colour=constants.EmbedStatus.FAIL.value,
                description="Song is already looping.",
            )
            await interaction.response.send_message(embed=embed)
            return

        # Enable loop if disabled
        music_player.is_looping = True
        embed = discord.Embed(colour=constants.EmbedStatus.YES.value, description="Loop enabled.")
        await interaction.response.send_message(embed=embed)
        return

    @app_commands.command()
    @permissions.check()
    async def unloop(self: Self, interaction: discord.Interaction) -> None:
        """Unloops so that the queue resumes as usual."""
        music_player, _ = await self._find_music_player(interaction)
        if music_player is None:
            return

        # Disable loop if enabled
        if not music_player.is_looping:
            embed = discord.Embed(
                colour=constants.EmbedStatus.FAIL.value,
                description="Song is not currently looping.",
            )
            await interaction.response.send_message(embed=embed)
            return

        # Enable loop if disabled
        music_player.is_looping = False
        embed = discord.Embed(colour=constants.EmbedStatus.YES.value, description="Loop disabled.")
        await interaction.response.send_message(embed=embed)
        return

    @app_commands.command()
    async def song(self: Self, interaction: discord.Interaction) -> None:
        """List information about the currently playing song."""
        music_player, _ = await self._find_music_player(interaction)
        if music_player is None:
            return

        # Alert if nothing is playing
        song = music_player.playing
        if not song:
            await interaction.response.send_message(
                embed=discord.Embed(
                    colour=constants.EmbedStatus.FAIL.value,
                    description="There's nothing currently playing.",
                )
            )
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
            f"`{current_time}/{duration}`\n\u200b",
        )

        if song.original_source in (
            OriginalSource.YOUTUBE_ALBUM,
            OriginalSource.SPOTIFY_ALBUM,
            OriginalSource.YOUTUBE_PLAYLIST,
            OriginalSource.SPOTIFY_PLAYLIST,
            OriginalSource.LOCAL,
        ):
            embed.add_field(
                name=f"Fetched from {song.original_source.value}",
                value=f"[{song.group}]({song.group_url})",
                inline=False,
            )
        elif song.original_source == OriginalSource.YOUTUBE_VIDEO:
            embed.add_field(
                name="Fetched from Site",
                value=f"[{song.original_source.value}](https://youtube.com)",
                inline=False,
            )
        elif song.original_source == OriginalSource.YOUTUBE_SONG:
            embed.add_field(
                name="Fetched from Site",
                value=f"[{song.original_source.value}](https://music.youtube.com)",
                inline=False,
            )
        elif song.original_source == OriginalSource.SPOTIFY_SONG:
            embed.add_field(
                name="Fetched from Site",
                value=f"[{song.original_source.value}](https://open.spotify.com)",
                inline=False,
            )

        if song.artist:
            embed.add_field(name="Artist", value=f"{song.artist}")

        if song.requester_id:
            embed.add_field(name="Requested By", value=f"<@{song.requester_id}>")

        await interaction.response.send_message(embed=embed)

    @queue_group.command(name="list")
    @permissions.check()
    async def queue_list(self: Self, interaction: discord.Interaction, page: int = 1) -> None:
        """List the current song queue."""
        music_player, _ = await self._find_music_player(interaction)
        if music_player is None:
            return

        # Notify user if nothing is in the queue
        playing = music_player.playing
        queue = music_player.next_queue
        if not playing and not queue:
            embed = discord.Embed(
                colour=constants.EmbedStatus.FAIL.value,
                description="There's nothing in the queue right now.",
            )
            await interaction.response.send_message(embed=embed)
            return

        # Output currently playing song
        embed = discord.Embed(
            colour=constants.EmbedStatus.INFO.value,
            title=f"{constants.EmbedIcon.MUSIC} Music Queue",
        )
        header = "Currently Playing (Looping)" if music_player.is_looping else "Currently Playing"
        artist = f"{playing.artist} - " if playing.artist else ""
        current_time = await self._format_duration(music_player.seek_position)
        duration = await self._format_duration(playing.duration)
        spacer = "\u200b" if len(queue) >= 1 else ""
        embed.add_field(
            name=header,
            value=f"[{artist}{playing.title}]({playing.url}) "
            f"`{current_time}/{duration}` \n{spacer}",
        )

        # List songs in queue and calculate the total duration
        queue_display_items = []
        total_duration = 0
        for song in queue:
            total_duration += song.duration
            duration = await self._format_duration(song.duration)
            artist = f"{song.artist} - " if song.artist else ""
            queue_display_items.append(
                f"[{artist}{song.title}]({song.url}) `{duration}` | " f"<@{playing.requester_id}>"
            )

        # Output results to chat
        if queue_display_items:
            duration = await self._format_duration(total_duration)
            paginated_view = PaginatedView(
                embed, f"Queue  `{duration}`", queue_display_items, 5, page
            )
        else:
            paginated_view = EmptyPaginatedView(
                embed,
                "Queue `0:00`",
                "Nothing else is queued up. " "Add more songs and they will appear here.",
            )
        await paginated_view.send(interaction)

    @queue_group.command(name="prevlist")
    async def queue_prevlist(self: Self, interaction: discord.Interaction, page: int = 1) -> None:
        """List the current song queue."""
        music_player, _ = await self._find_music_player(interaction)
        if music_player is None:
            return

        # Notify user if nothing is in the queue
        playing = music_player.playing
        queue = music_player.previous_queue
        if not playing and not queue:
            embed = discord.Embed(
                colour=constants.EmbedStatus.FAIL.value,
                description="There's nothing in the previous played song list.",
            )
            await interaction.response.send_message(embed=embed)
            return

        # Output currently playing song
        embed = discord.Embed(
            colour=constants.EmbedStatus.INFO.value,
            title=f"{constants.EmbedIcon.MUSIC} Music Queue",
        )
        header = "Currently Playing (Looping)" if music_player.is_looping else "Currently Playing"
        artist = f"{playing.artist} - " if playing.artist else ""
        current_time = await self._format_duration(music_player.seek_position)
        duration = await self._format_duration(playing.duration)
        spacer = "\u200b" if len(queue) >= 1 else ""
        embed.add_field(
            name=header,
            value=f"[{artist}{playing.title}]({playing.url}) "
            f"`{current_time}/{duration}` \n{spacer}",
        )

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
            paginated_view = PaginatedView(
                embed, f"Queue  `{duration}`", queue_display_items, 5, page
            )
        else:
            paginated_view = EmptyPaginatedView(
                embed,
                "Queue `0:00`",
                "Nothing here yet. Songs that have previously played with appear here.",
            )
        await paginated_view.send(interaction)

    @queue_group.command(name="reorder")
    @permissions.check()
    async def queue_reorder(
        self: Self, interaction: discord.Interaction, original_pos: int, new_pos: int
    ) -> None:
        """Move a song to a different position in the queue."""
        music_player, _ = await self._find_music_player(interaction)
        if music_player is None:
            return

        # Try to remove song from queue using the specified index
        queue = music_player.next_queue
        if original_pos < 1:
            embed = discord.Embed(
                colour=constants.EmbedStatus.FAIL.value,
                description="There's no song at that position",
            )
            await interaction.response.send_message(embed=embed)
            return

        # Move song into new position in queue
        song = queue[original_pos - 1]
        if not 1 <= new_pos <= len(queue):
            embed = discord.Embed(
                colour=constants.EmbedStatus.FAIL.value,
                description="You can't move the song into that position",
            )
            await interaction.response.send_message(embed=embed)
            return
        await music_player.move(original_pos - 1, new_pos - 1)

        # Output result to chat
        duration = await self._format_duration(song.duration)
        embed = discord.Embed(
            colour=constants.EmbedStatus.YES.value,
            description=f"[{song.title}]({song.url}) `{duration}` has been moved from "
            f"position #{original_pos} to position #{new_pos}",
        )
        await interaction.response.send_message(embed=embed)

    @queue_group.command(name="remove")
    @permissions.check()
    async def queue_remove(self: Self, interaction: discord.Interaction, position: int) -> None:
        """Remove a song from the queue."""
        music_player, _ = await self._find_music_player(interaction)
        if music_player is None:
            return

        # Try to remove song from queue using the specified index
        if position < 1 or position > len(music_player.next_queue):
            embed = discord.Embed(
                colour=constants.EmbedStatus.FAIL.value,
                description="That's an invalid queue position.",
            )
            await interaction.response.send_message(embed=embed)
            return
        song = music_player.next_queue[position - 1]
        await music_player.remove(position - 1)

        # Output result to chat
        duration = await self._format_duration(song.duration)
        embed = discord.Embed(
            colour=constants.EmbedStatus.YES.value,
            description=f"[{song.title}]({song.url}) `{duration}` "
            f"has been removed from position #{position} of the queue",
        )
        await interaction.response.send_message(embed=embed)

    @queue_group.command(name="clear")
    @permissions.check()
    async def queue_clear(self: Self, interaction: discord.Interaction) -> None:
        """Clears the entire queue."""
        music_player, _ = await self._find_music_player(interaction)
        if music_player is None:
            return

        # Try to remove all but the currently playing song from the queue
        if len(music_player.next_queue) < 1:
            embed = discord.Embed(
                colour=constants.EmbedStatus.FAIL.value,
                description="There's nothing in the queue to clear",
            )
            await interaction.response.send_message(embed=embed)
            return

        await music_player.clear()
        embed = discord.Embed(
            colour=constants.EmbedStatus.FAIL.value,
            description="All songs have been removed from the queue",
        )
        await interaction.response.send_message(embed=embed)

    @playlist_group.command(name="create")
    @permissions.check()
    async def playlist_create(
        self: Self, interaction: discord.Interaction, playlist_name: str
    ) -> None:
        """Create a new playlist."""
        if not interaction.guild or not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message(embed=self.NOT_IN_SERVER_EMBED)
            return

        # Limit playlist name to 30 chars
        if len(playlist_name) > MAX_PLAYLIST_NAME_LENGTH:
            embed = discord.Embed(
                colour=constants.EmbedStatus.FAIL.value,
                description="Playlist name is too long",
            )
            await interaction.response.send_message(embed=embed)
            return

        # Alert if playlist with specified name already exists
        if self.playlists.get_by_name_in_guild(playlist_name, interaction.guild):
            embed = discord.Embed(
                colour=constants.EmbedStatus.FAIL.value,
                description=f"Playlist `{playlist_name}` already exists",
            )
            await interaction.response.send_message(embed=embed)
            return

        # Add playlist to database
        self.playlists.add(Playlist.create_new(playlist_name, interaction.guild, interaction.user))
        embed = discord.Embed(
            colour=constants.EmbedStatus.YES.value,
            description=f"Playlist `{playlist_name}` has been created",
        )
        await interaction.response.send_message(embed=embed)

    @playlist_group.command(name="destroy")
    @permissions.check()
    async def playlist_destroy(
        self: Self, interaction: discord.Interaction, playlist_name: str
    ) -> None:
        """Deletes an existing playlist."""
        if not interaction.guild or not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message(embed=self.NOT_IN_SERVER_EMBED)
            return

        # Alert if playlist doesn't exist in db
        playlist = self.playlists.get_by_name_in_guild(playlist_name, interaction.guild)
        if not playlist:
            await interaction.response.send_message(
                embed=discord.Embed(
                    colour=constants.EmbedStatus.FAIL.value,
                    description=f"Playlist `{playlist_name}` doesn't exist",
                )
            )
            return

        # Remove all playlist songs
        playlist_songs = self.playlist_songs.get_by_playlist(playlist.id)
        if playlist_songs:
            for song in playlist_songs:
                self.playlist_songs.remove(song.id)

        # Remove the playlist itself
        self.playlists.remove(playlist.id)
        embed = discord.Embed(
            colour=constants.EmbedStatus.YES.value,
            description=f"Playlist `{playlist_name}` has been destroyed",
        )
        await interaction.response.send_message(embed=embed)

    @playlist_group.command(name="description")
    @permissions.check()
    async def playlist_description(
        self: Self, interaction: discord.Interaction, playlist_name: str, description: str
    ) -> None:
        """Sets the description for the playlist."""
        if not interaction.guild or not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message(embed=self.NOT_IN_SERVER_EMBED)
            return

        # Alert if playlist doesn't exist
        playlist = self.playlists.get_by_name_in_guild(playlist_name, interaction.guild)
        if not playlist:
            embed = discord.Embed(
                colour=constants.EmbedStatus.FAIL.value,
                description=f"Playlist '{playlist_name}' doesn't exist",
            )
            await interaction.response.send_message(embed=embed)
            return

        # Limit playlist description to 300 chars
        if len(description) > MAX_PLAYLIST_DESCRIPTION_LENGTH:
            embed = discord.Embed(
                colour=constants.EmbedStatus.FAIL.value,
                description="Description is too long",
            )
            await interaction.response.send_message(embed=embed)
            return

        # Update playlist last modified
        playlist.modified_date = datetime.datetime.now(tz=datetime.UTC)
        self.playlists.update(playlist)

        # Update playlist description
        playlist.description = description
        self.playlists.update(playlist)
        embed = discord.Embed(
            colour=constants.EmbedStatus.YES.value,
            description=f"Description set for playlist '{playlist_name}'",
        )
        await interaction.response.send_message(embed=embed)

    @playlist_group.command(name="rename")
    @permissions.check()
    async def playlist_rename(
        self: Self, interaction: discord.Interaction, playlist_name: str, new_name: str
    ) -> None:
        """Rename an existing playlist."""
        if not interaction.guild or not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message(embed=self.NOT_IN_SERVER_EMBED)
            return

        # Get the playlist
        playlist = self.playlists.get_by_name_in_guild(playlist_name, interaction.guild)
        if not playlist:
            embed = discord.Embed(
                colour=constants.EmbedStatus.FAIL.value,
                description=f"Playlist '{playlist_name}' doesn't exist",
            )
            await interaction.response.send_message(embed=embed)
            return

        # Update playlist last modified
        playlist.modified_date = datetime.datetime.now(tz=datetime.UTC)
        self.playlists.update(playlist)

        # Update playlist name
        playlist.name = new_name
        self.playlists.update(playlist)
        embed = discord.Embed(
            colour=constants.EmbedStatus.YES.value,
            description=f"Playlist '{playlist_name}' has been renamed to '{new_name}'",
        )
        await interaction.response.send_message(embed=embed)

    @playlist_group.command(name="list")
    @permissions.check()
    async def playlist_list(self: Self, interaction: discord.Interaction, page: int = 1) -> None:
        """List all available playlists."""
        if not interaction.guild or not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message(embed=self.NOT_IN_SERVER_EMBED)
            return

        # Get playlist from repo
        playlists = self.playlists.get_by_guild(interaction.guild)
        if not playlists:
            embed = discord.Embed(
                colour=constants.EmbedStatus.FAIL.value,
                description="There are no playlists available",
            )
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
            playlist_info.append(
                f"{playlist.name} `{duration}` | " f"Created by <@{playlist.creator_id}>"
            )

        # Output results to chat
        embed = discord.Embed(
            colour=constants.EmbedStatus.INFO.value,
            title=f"{constants.EmbedIcon.MUSIC} Music Playlists",
        )
        paginated_view = PaginatedView(
            embed, f"{len(playlists)} available", playlist_info, 5, page
        )
        await paginated_view.send(interaction)

    @playlist_group.command(name="add")
    @permissions.check()
    async def playlist_add(
        self: Self, interaction: discord.Interaction, playlist_name: str, url: str
    ) -> None:
        """Adds a song to a playlist."""
        if not interaction.guild or not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message(embed=self.NOT_IN_SERVER_EMBED)
            return

        # Get playlist from repo
        playlist = self.playlists.get_by_name_in_guild(playlist_name, interaction.guild)
        if not playlist:
            embed = discord.Embed(
                colour=constants.EmbedStatus.FAIL.value,
                description="That playlist does not exist.",
            )
            await interaction.response.send_message(embed=embed)
            return

        # Check if playlist limit has been reached
        playlist_songs = self.playlist_songs.get_by_playlist(playlist.id)
        if len(playlist_songs) > PLAYLIST_SONG_LIMIT:
            embed = discord.Embed(
                colour=constants.EmbedStatus.FAIL.value,
                description="There's too many songs in the playlist. Remove"
                "some songs to be able to add more",
            )
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
                description="That song is unavailable. Maybe the link is invalid?",
            )
            await interaction.followup.send(embed=embed)
            return

        # Update playlist last modified
        playlist.modified_date = datetime.datetime.now(tz=datetime.UTC)
        self.playlists.update(playlist)

        # Add playlist
        if songs[0].original_source in (
            OriginalSource.YOUTUBE_PLAYLIST,
            OriginalSource.SPOTIFY_PLAYLIST,
        ):
            self._add_collection_to_playlist(interaction.user, playlist, songs)
            embed = discord.Embed(
                colour=constants.EmbedStatus.YES.value,
                description=f"Added `{len(songs)}` songs from playlist "
                f"[{songs[0].group}]({songs[0].group_url}) to "
                f"#{len(playlist_songs) + 1} in playlist '{playlist_name}'",
            )
            await interaction.followup.send(embed=embed)

        # Add album
        if songs[0].original_source in (
            OriginalSource.YOUTUBE_ALBUM,
            OriginalSource.SPOTIFY_ALBUM,
        ):
            self._add_collection_to_playlist(interaction.user, playlist, songs)
            embed = discord.Embed(
                colour=constants.EmbedStatus.YES.value,
                description=f"Added `{len(songs)}` songs from album "
                f"[{songs[0].group}]({songs[0].group_url}) to "
                f"#{len(playlist_songs) + 1} in playlist '{playlist_name}'",
            )
            await interaction.followup.send(embed=embed)
            return

        self._add_song_to_playlist(interaction.user, playlist, songs[0])
        artist = ""
        if songs[0].artist:
            artist = f"{songs[0].artist} - "
        await interaction.followup.send(
            embed=discord.Embed(
                colour=constants.EmbedStatus.YES.value,
                description=f"Added [{artist}{songs[0].title}]({songs[0].url}) "
                f"`{await self._format_duration(songs[0].duration)}` "
                f"to position #{len(playlist_songs) + 1} "
                f"in playlist '{playlist_name}'",
            )
        )

    @playlist_group.command(name="remove")
    @permissions.check()
    async def playlist_remove(
        self: Self, interaction: discord.Interaction, playlist_name: str, index: int
    ) -> None:
        """Removes a song from a playlist."""
        if not interaction.guild or not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message(embed=self.NOT_IN_SERVER_EMBED)
            return

        # Get playlist from repo
        playlist = self.playlists.get_by_name_in_guild(playlist_name, interaction.guild)
        if not playlist:
            embed = discord.Embed(
                colour=constants.EmbedStatus.FAIL.value,
                description=f"Playlist `{playlist_name}` doesn't exist",
            )
            await interaction.response.send_message(embed=embed)
            return

        # Fetch selected song and the song after
        songs: list[PlaylistSong] = await self._order_playlist_songs(
            self.playlist_songs.get_by_playlist(playlist.id)
        )
        selected_song = songs[int(index) - 1]

        # Edit next song's previous song id if it exists
        try:
            next_song = songs[int(index)]
            next_song.previous_id = selected_song.previous_id
            self.playlist_songs.update(next_song)
        except IndexError:
            pass

        # Update playlist last modified
        playlist.modified_date = datetime.datetime.now(tz=datetime.UTC)
        self.playlists.update(playlist)

        # Remove selected song from playlist
        self.playlist_songs.remove(selected_song.id)
        duration = await self._format_duration(selected_song.duration)
        embed = discord.Embed(
            colour=constants.EmbedStatus.FAIL.value,
            description=f"[{selected_song.title}]({selected_song.url}) "
            f"`{duration}` has been removed from `{playlist_name}`",
        )
        await interaction.response.send_message(embed=embed)

    @playlist_group.command(name="reorder")
    @permissions.check()
    async def playlist_reorder(
        self: Self,
        interaction: discord.Interaction,
        playlist_name: str,
        original_pos: int,
        new_pos: int,
    ) -> None:
        """Moves a song to a specified position in a playlist."""
        if not interaction.guild or not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message(embed=self.NOT_IN_SERVER_EMBED)
            return

        # Get playlist from repo
        playlist = self.playlists.get_by_name_in_guild(playlist_name, interaction.guild)
        if not playlist:
            embed = discord.Embed(
                colour=constants.EmbedStatus.FAIL.value,
                description=f"Playlist `{playlist_name}` doesn't exist",
            )
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
        playlist.modified_date = datetime.datetime.now(tz=datetime.UTC)
        self.playlists.update(playlist)

        # Output result to chat
        self.playlist_songs.update(selected_song)
        duration = await self._format_duration(selected_song.duration)
        embed = discord.Embed(
            colour=constants.EmbedStatus.YES.value,
            description=f"[{selected_song.title}]({selected_song.url}) "
            f"`{duration}` has been moved to position #{new_pos} "
            f"in playlist '{playlist_name}'",
        )
        await interaction.response.send_message(embed=embed)

    @playlist_group.command(name="view")
    @permissions.check()
    async def playlist_view(
        self: Self, interaction: discord.Interaction, playlist_name: str, page: int = 1
    ) -> None:
        """List all songs in a playlist."""
        if not interaction.guild or not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message(embed=self.NOT_IN_SERVER_EMBED)
            return

        # Fetch songs from playlist if it exists
        playlist = self.playlists.get_by_name_in_guild(playlist_name, interaction.guild)
        if not playlist:
            embed = discord.Embed(
                colour=constants.EmbedStatus.FAIL.value,
                description=f"Playlist `{playlist_name}` does not exist",
            )
            await interaction.response.send_message(embed=embed)
            return
        songs = await self._order_playlist_songs(self.playlist_songs.get_by_playlist(playlist.id))

        # Format the text of each song
        total_duration = 0
        formatted_songs = []
        for song in songs:
            total_duration += song.duration
            song_name = (
                song.title[:87] + "..."
                if len(song.title) > MAX_DISPLAY_SONG_NAME_LENGTH
                else song.title
            )
            duration = await self._format_duration(song.duration)
            artist = f"{song.artist} - " if song.artist else ""
            formatted_songs.append(
                f"[{artist}{song_name}]({song.url}) `{duration}` " f"| <@{song.requester_id}>"
            )

        # Output results to chat
        embed = discord.Embed(
            colour=constants.EmbedStatus.INFO.value,
            title=f"{constants.EmbedIcon.MUSIC} Playlist '{playlist_name}'",
        )
        embed.description = f"Created by: <@{playlist.creator_id}>\n"
        embed.description += (
            playlist.description + "\n\u200b" if playlist.description else "\u200b"
        )
        formatted_duration = await self._format_duration(total_duration)
        paginated_view = PaginatedView(
            embed,
            f"{len(songs)} Songs `{formatted_duration}`",
            formatted_songs,
            5,
            page,
        )
        await paginated_view.send(interaction)

    @playlist_group.command(name="play")
    @permissions.check()
    async def playlist_play(
        self: Self, interaction: discord.Interaction, playlist_name: str
    ) -> None:
        """Play from a locally saved playlist."""
        if not interaction.guild or not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message(embed=self.NOT_IN_SERVER_EMBED)
            return

        # Get music player
        music_player, _ = await self._find_music_player(interaction)
        if music_player is None:
            return

        # Fetch songs from playlist if it exists
        playlist = self.playlists.get_by_name_in_guild(playlist_name, interaction.guild)
        if not playlist:
            embed = discord.Embed(
                colour=constants.EmbedStatus.FAIL.value,
                description=f"Playlist `{playlist_name}` does not exist",
            )
            await interaction.response.send_message(embed=embed)
            return

        songs = await self._order_playlist_songs(self.playlist_songs.get_by_playlist(playlist.id))
        if not songs:
            embed = discord.Embed(
                colour=constants.EmbedStatus.FAIL.value,
                description=f"Playlist `{playlist.name}` does not contain any songs",
            )
            await interaction.response.send_message(embed=embed)
            return

        stream = await self._get_song_from_saved(songs[0], playlist, interaction.user)
        result = await music_player.add(stream[0])
        if result == PlayerResult.PLAYING:
            embed = discord.Embed(
                colour=constants.EmbedStatus.YES.value,
                description=f"Now playing saved playlist '{playlist.name}'",
            )
            await interaction.response.send_message(embed=embed)
        else:
            embed = discord.Embed(
                colour=constants.EmbedStatus.YES.value,
                description=f"Adding saved playlist '{playlist.name}' to queue",
            )
            await interaction.response.send_message(embed=embed)

        # Add remaining songs to queue
        for i in range(1, len(songs)):
            stream = await self._get_song_from_saved(songs[i], playlist, interaction.user)
            await music_player.add(stream[0])

    @musicsettings_group.command(name="autodisconnect")
    @permissions.exclusive()
    async def musicsettings_autodisconnect(self: Self, interaction: discord.Interaction) -> None:
        """
        Toggles if the bot should auto disconnect from a voice channel.

        Args:
            interaction (discord.Interaction): The user interaction.
        """
        config = self.bot.instance.get_config()

        # Toggle auto_disconnect config setting
        if config["music"]["auto_disconnect"]:
            config["music"]["auto_disconnect"] = False
            result_text = "disabled"
        else:
            config["music"]["auto_disconnect"] = True
            result_text = "enabled"

        self.bot.instance.save_config(config)

        embed = discord.Embed(
            colour=constants.EmbedStatus.YES.value,
            description=f"Music player auto disconnect {result_text}",
        )
        await interaction.response.send_message(embed=embed)

    @musicsettings_group.command(name="disconnecttime")
    @permissions.exclusive()
    async def musicsettings_disconnecttime(
        self: Self, interaction: discord.Interaction, seconds: int
    ) -> None:
        """
        Sets a auto disconnect time after a bot has stopped playing.

        This should start the moment the last song has finished playing,
        and resets when another song is played.
        """
        config = self.bot.instance.get_config()

        # Set disconnect_time config variable
        config["music"]["disconnect_time"] = seconds
        self.bot.instance.save_config(config)

        embed = discord.Embed(
            colour=constants.EmbedStatus.YES.value,
            description=f"Music player auto disconnect timer set to {seconds} seconds",
        )
        await interaction.response.send_message(embed=embed)

    async def _get_music_player(self: Self, channel: VocalGuildChannel) -> MusicPlayer:
        """
        Retrieves or creates a music player in a given voice channel.

        Args:
            channel (discord.VoiceChannel): The voice channel for which
            to retrieve the music player.

        Returns:
            WavelinkMusicPlayer: The music player associated with the
            given voice channel.
        """
        try:
            music_player = self.music_players[channel.guild.id]
        except KeyError:
            music_player = await WavelinkMusicPlayer.connect(self.bot.instance, channel)
            self.music_players[channel.guild.id] = music_player
        return music_player

    async def _get_songs(self: Self, query: str, requester: discord.abc.User) -> tuple[Song, ...]:
        """
        Get songs based on a query and requester.

        Args:
            query (str): The query used to search for songs.
            requester (discord.User): The user requesting the songs.

        Returns:
            list['Song']: A list of Song objects
            representing the songs.
        """
        if self.player_type == "wavelink":
            return await WavelinkSong.from_query(query, requester)
        return await Song.from_query(query, requester)

    @staticmethod
    async def _get_song_from_saved(
        playlist_song: PlaylistSong, playlist: Playlist, requester: discord.abc.User
    ) -> list[WavelinkSong]:
        """
        Get a song from a saved playlist.

        Args:
            playlist_song (PlaylistSong): The playlist song object.
            playlist (Playlist): The playlist object.
            requester (discord.User): The user requesting the song.

        Returns:
            WavelinkSong: The song object obtained from the
            saved playlist.
        """
        return await WavelinkSong.from_local(requester, playlist_song, playlist)

    async def _find_music_player(
        self: Self, interaction: discord.Interaction
    ) -> tuple[MusicPlayer | None, VocalGuildChannel | None]:
        """
        Try to find a music player based on the user's state.

        In order for a user to be able to interact with a music player,
        they must exist in the same voice channel as the bot with a
        currently active music player.

        This method will send message alerts depending on what is
        causing it to fail to find a music player.

        Args:
            interaction (discord.Interaction): The user interaction.

        Returns:
            MusicPlayer | None: The music player associated with the
                bot, else None if it cannot be found.
        """
        # Alert if user is not running command in server
        if interaction.guild is None or not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message(embed=self.NOT_IN_SERVER_EMBED)
            return None, None

        # Alert if bot not in voice channel
        if not interaction.guild.voice_client or not interaction.guild.voice_client.channel:
            await interaction.response.send_message(embed=self.NOT_CONNECTED_EMBED)
            return None, None

        # Alert if user not in voice channel.
        if (
            not interaction.user.voice
            or interaction.user.voice.channel != interaction.guild.voice_client.channel
        ):
            await interaction.response.send_message(embed=self.NOT_USER_CONNECTED_EMBED)
            return None, None

        # Alert if bot not in supported voice channel
        voice_channel = interaction.guild.voice_client.channel
        if not isinstance(voice_channel, VocalGuildChannel):
            await interaction.response.send_message(embed=self.NOT_SUPPORTED_EMBED)
            return None, None

        return await self._get_music_player(voice_channel), voice_channel

    async def _find_or_create_music_player(
        self: Self, interaction: discord.Interaction
    ) -> tuple[MusicPlayer | None, VocalGuildChannel | None]:
        """
        Find or create a music player.

        Args:
            interaction (discord.Interaction): The user interaction.

        Returns:
            MusicPlayer | None: The music player associated with the
                bot, else None if it cannot be found.
        """
        # Alert if user is not running command in server
        if interaction.guild is None or not isinstance(interaction.user, discord.Member):
            embed = discord.Embed(
                colour=constants.EmbedStatus.FAIL.value,
                description="You can't run this command in DMs.",
            )
            await interaction.response.send_message(embed=embed)
            return None, None

        # Alert if user is not in a voice channel
        if interaction.user.voice is None:
            await interaction.response.send_message(embed=self.NOT_USER_CONNECTED_EMBED)
            return None, None

        # Alert if bot not in supported voice channel
        voice_channel = interaction.user.voice.channel
        if not isinstance(voice_channel, VocalGuildChannel):
            await interaction.response.send_message(embed=self.NOT_SUPPORTED_EMBED)
            return None, None

        # Join channel and create music player instance if it doesn't exist
        return await self._get_music_player(voice_channel), voice_channel

    async def _get_player_channel(
        self: Self, interaction: discord.Interaction
    ) -> VocalGuildChannel | None:
        """
        Get the voice channel the bot is connected to.

        Returns:
            VocalGuildChannel | None: The voice channel the bot is
                connected to, else None if it cannot be found.
        """
        if (
            not interaction.guild
            or not interaction.guild.voice_client
            or not interaction.guild.voice_client.channel
        ):
            return None

        if not isinstance(interaction.guild.voice_client.channel, VocalGuildChannel):
            return None

        return interaction.guild.voice_client.channel

    @staticmethod
    async def _format_duration(milliseconds: int) -> str:
        """
        Format the duration in milliseconds to a human readable format.

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
        overflow_value = 10
        if hours:
            if hours < overflow_value:
                formatted += f"0{hours!s}:"
            else:
                formatted += f"{hours!s}:"

        if minutes:
            if minutes < overflow_value:
                formatted += f"0{minutes}:"
            else:
                formatted += f"{minutes}:"
        elif hours:
            formatted += "00:"
        else:
            formatted += "0:"

        if seconds:
            if seconds < overflow_value:
                formatted += f"0{seconds}"
            else:
                formatted += f"{seconds}"
        else:
            formatted += "00"

        return formatted

    @staticmethod
    async def _order_playlist_songs(
        playlist_songs: list[PlaylistSong],
    ) -> list[PlaylistSong]:
        """
        Orders a list of playlist songs based on their song ID ordering.

        Args:
            playlist_songs (List[PlaylistSong]): A list of playlist
            songs.

        Returns:
            List[PlaylistSong]: A list of playlist songs ordered based
            on their previous song IDs.

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
    def _parse_time(time_string: str) -> int:
        """
        Parses a time string and returns it in milliseconds.

        Args:
            time_string (str): The time string to be parsed.
            The string should be in the format HH:MM:SS or MM:SS.

        Returns:
            int: The equivalent time in milliseconds.
        """
        time_split = time_string.split(":")
        time_split += ["0"] * (3 - len(time_split))
        hours, minutes, seconds = map(int, time_split)
        return hours * 3600000 + minutes * 60000 + seconds * 1000

    def _add_song_to_playlist(
        self: Self, user: discord.abc.User, playlist: Playlist, song: Song
    ) -> None:
        """
        Add a song to a playlist.

        Args:
            user (discord.abc.User): The user who added the song.
            playlist (Playlist): The playlist to add the song to.
            song (Song): The song to add to the playlist.
        """
        last_song = self._get_last_song_in_playlist(playlist)
        previous_id = last_song.id if last_song else uuid.UUID(int=0)
        new_playlist_song = PlaylistSong.create_new(
            playlist.id,
            user.id,
            song.title,
            song.artist,
            song.duration,
            song.url,
            previous_id,
        )
        self.playlist_songs.add(new_playlist_song)

    def _add_collection_to_playlist(
        self: Self, user: discord.abc.User, playlist: Playlist, songs: Sequence[Song]
    ) -> None:
        """
        Add a list of playlist songs to a playlist.

        Args:
            user (discord.abc.User): The user who added the songs.
            playlist (Playlist): The playlist to add the songs to.
            songs (List[Song]): The songs to add to the playlist.
        """
        last_song = self._get_last_song_in_playlist(playlist)
        previous_id = last_song.id if last_song else uuid.UUID(int=0)
        for song in songs:
            new_playlist_song = PlaylistSong.create_new(
                playlist.id,
                user.id,
                song.title,
                song.artist,
                song.duration,
                song.url,
                previous_id,
            )
            self.playlist_songs.add(new_playlist_song)
            previous_id = new_playlist_song.id

    def _get_last_song_in_playlist(self: Self, playlist: Playlist) -> PlaylistSong | None:
        """
        Get the last song in a playlist.

        Args:
            playlist (Playlist): The playlist to get the last song from.

        Returns:
            PlaylistSong | None: The last song in the playlist, else None
                if the playlist is empty.
        """
        playlist_songs = self.playlist_songs.get_by_playlist(playlist.id)
        if not playlist_songs:
            previous_id = uuid.UUID(int=0)
        else:
            song_ids = []
            previous_ids = []
            for playlist_song in playlist_songs:
                song_ids.append(playlist_song.id)
                previous_ids.append(playlist_song.previous_id)
            previous_id = next(iter(set(song_ids) - set(previous_ids)))
        return self.playlist_songs.get_by_id(previous_id)


async def setup(bot: SpaceCat) -> None:
    """Set up the musicbox cog."""
    await bot.add_cog(Musicbox(bot))
