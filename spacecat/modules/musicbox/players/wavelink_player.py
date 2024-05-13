"""
Module for playing music using the Wavelink library.

This module provides a wrapper for the Wavelink library to make it easier
to use. It provides a streamlined way of playing music and handling
playlists.
"""

from __future__ import annotations

import random
from collections import deque
from time import time
from typing import TYPE_CHECKING, Self, override

import toml
import wavelink
from discord.ext import tasks

from spacecat.helpers import constants
from spacecat.modules.musicbox.music_player import (
    MusicPlayer,
    OriginalSource,
    PlayerResult,
    Song,
    SongUnavailableError,
)

if TYPE_CHECKING:
    import discord

    from spacecat.modules.musicbox.playlist import Playlist, PlaylistSong


class WavelinkSong(Song):
    """Represents a song using data from wavelink."""

    def __init__(
        self: WavelinkSong,
        track: wavelink.Playable,
        original_source: OriginalSource,
        url: str,
        group: str | None,
        group_url: str | None,
        title: str,
        artist: str | None,
        duration: int | None,
        requester_id: int,
    ) -> None:
        """
        Initializes a WavelinkSong object.

        Args:
            track (wavelink.Playable): The playable track object.
            original_source (OriginalSource): The original source of the
                song.
            url (str): The URL of the song.
            group (str | None): The group the song belongs to.
            group_url (str | None): The URL of the group.
            title (str): The title of the song.
            artist (str): The artist name of the song.
            duration (int | None): The duration of the song in seconds.
            requester_id (int): The user ID of the requester.
        """
        self._track: wavelink.Playable = track
        self._original_source: OriginalSource = original_source
        self._url = url
        self._playlist = group
        self._playlist_url = group_url
        self._title = title
        self._artist = artist
        self._duration = duration
        self._requester_id = requester_id

    @property
    @override
    def stream(self: Self) -> wavelink.Playable:
        return self._track

    @property
    @override
    def title(self: Self) -> str:
        return self._title if self._title else self._track.title

    @property
    @override
    def artist(self: Self) -> str | None:
        return self._artist if self._artist else self._track.author

    @property
    @override
    def duration(self: Self) -> int:
        return self._duration if self._duration else int(self._track.length)

    @property
    @override
    def url(self: Self) -> str:
        return self._url

    @property
    @override
    def group(self: Self) -> str | None:
        return self._playlist

    @property
    @override
    def group_url(self: Self) -> str | None:
        return self._playlist_url

    @property
    @override
    def original_source(self: Self) -> OriginalSource:
        return self._original_source

    @property
    @override
    def requester_id(self: Self) -> int:
        return self._requester_id

    @classmethod
    async def from_local(
        cls: type[WavelinkSong],
        requester: discord.User,
        playlist_song: PlaylistSong,
        playlist: Playlist,
    ) -> list[WavelinkSong]:
        """
        Creates a Wavelink song object from a local playlist song.

        Parameters:
            requester (discord.User): The user requesting the song.
            playlist_song (PlaylistSong): The playlist song object
                containing the song details.
            playlist (Playlist, optional): The playlist to which the
                song belongs. Defaults to None.

        Returns:
            list['WavelinkSong']: A list containing WavelinkSong objects
                created from the local playlist song.
        """
        track = await wavelink.Playable.search(playlist_song.url)
        return [
            cls(
                track[0],
                OriginalSource.LOCAL,
                playlist_song.url,
                title=playlist_song.title,
                artist=playlist_song.artist,
                duration=playlist_song.duration,
                group=playlist.name,
                group_url=None,
                requester_id=requester.id,
            )
        ]

    @classmethod
    async def from_query(
        cls: type[WavelinkSong], query: str, requester: discord.User
    ) -> list[WavelinkSong]:
        """
        Creates a wavelink song object from a search query.

        Parameters:
            query (str): The query used to search for the track.
            requester (discord.User): The user requesting the track.

        Returns:
            list['WavelinkSong']: A list containing WavelinkSong objects
                created from the query.
        """
        tracks = await wavelink.Playable.search(query)
        if not tracks:
            raise SongUnavailableError

        if tracks[0].playlist is None:
            return await cls._process_single(query, tracks[0], requester)
        return await cls._process_multiple(query, tracks, requester)

    @classmethod
    async def _process_single(
        cls: type[WavelinkSong], query: str, track: wavelink.Playable, requester: discord.User
    ) -> list[WavelinkSong]:
        """
        Process a single track to convert into a Wavelink song object.

        This takes the object that is returned from wavelink and
        extracts useful data out of it.

        Parameters:
            query (str): The query that was used to obtain the track.
            track (wavelink.Playable): The track to create the
                WavelinkSong from.
            requester (discord.User): The user requesting the track.

        Returns:
            list['WavelinkSong']: A list containing a single
                WavelinkSong object created from the query.
        """
        if "youtube.com" in query or "youtu.be" in query:
            if "music" in query:
                source = OriginalSource.YOUTUBE_SONG
            elif "watch" in query:
                source = OriginalSource.YOUTUBE_VIDEO
        elif "open.spotify.com" in query:
            source = OriginalSource.SPOTIFY_SONG
        else:
            source = OriginalSource.UNKNOWN

        return [
            cls(
                track,
                source,
                track.uri if track.uri is not None else "",
                "",
                "",
                track.title,
                track.author,
                track.length,
                requester.id,
            )
        ]

    @classmethod
    async def _process_multiple(
        cls: type[WavelinkSong],
        query: str,
        tracks: wavelink.Search,
        requester: discord.User,
    ) -> list[WavelinkSong]:
        """
        Process a track grouping to convert into Wavelink song objects.

        This should be utilised to handle groups of songs such as
        playlists and albums. As the group is expected to come from the
        same source, the playlist source will only be taken from the
        first track to simplify processing.

        Parameters:
            query (str): The query used to obtain the tracks.
            tracks (wavelink.Playlist): The playlist containing tracks
                to process.
            requester (discord.User): The user requesting the tracks.

        Returns:
            list['WavelinkSong']: A list containing multiple
                WavelinkSong objects created from the tracks.
        """
        source = OriginalSource.UNKNOWN
        url = query
        playlist_name = ""

        if tracks[0].playlist:
            if "youtube.com" in query or "youtu.be" in query:
                if tracks[0].playlist is not None and "Album - " in tracks[0].playlist.name:
                    source, playlist_name = (
                        OriginalSource.YOUTUBE_ALBUM,
                        tracks[0].playlist.name[8:],
                    )
                elif tracks[0].playlist is not None and "playlist" in query:
                    source, playlist_name = (
                        OriginalSource.YOUTUBE_PLAYLIST,
                        tracks[0].playlist.name,
                    )
            elif "open.spotify.com" in query:
                if "playlist" in query:
                    source, url, playlist_name = (
                        OriginalSource.SPOTIFY_PLAYLIST,
                        tracks[0].playlist.url,
                        tracks[0].playlist.name,
                    )
                elif "album" in query:
                    source, url, playlist_name = (
                        OriginalSource.SPOTIFY_ALBUM,
                        tracks[0].playlist.url,
                        tracks[0].playlist.name,
                    )

        return [
            cls(
                track,
                source,
                track.uri if track.uri is not None else "",
                playlist_name,
                url,
                track.title,
                track.author,
                track.length,
                requester.id,
            )
            for track in tracks
        ]


class WavelinkMusicPlayer(MusicPlayer[WavelinkSong]):
    """
    A music player implementation using the Wavelink library.

    Utilising this type of music player requires the use of a seperate
    program called "Lavalink" in order to function. It provides a number
    of advantages over a local implementation such as pooling and
    caching to speed up operations.
    """

    def __init__(self: WavelinkMusicPlayer, player: wavelink.Player) -> None:
        """
        Initializes a new instance of the WavelinkMusicPlayer class.

        Args:
            self (WavelinkMusicPlayer): The WavelinkMusicPlayer
                instance.
            player (wavelink.Player): The Wavelink player object.
        """
        self._player: wavelink.Player = player
        self._current: WavelinkSong | None = None
        self._next_queue: deque[WavelinkSong] = deque()
        self._previous_queue: deque[WavelinkSong] = deque()
        self._is_looping = False
        self._is_skipping = False
        self._queue_reverse = False
        self._disconnect_time = time() + self._get_disconnect_time_limit()
        self._disconnect_job.start()

    @classmethod
    async def connect(
        cls: type[WavelinkMusicPlayer], channel: discord.VoiceChannel
    ) -> WavelinkMusicPlayer:
        """
        Initialises and connects the Wavelink player to a voice channel.

        This is the recommended way to initialise the music player, as
        it automatically creates the player object and connects to the
        specified channel.

        Args:
            channel (discord.VoiceChannel): The voice channel to connect
                to.

        Returns:
            WavelinkMusicPlayer: The connected player instance.
        """
        player: wavelink.Player = await channel.connect(cls=wavelink.Player, self_deaf=True)
        return cls(player)

    @property
    @override
    def is_paused(self: Self) -> bool:
        return self._player.paused

    @property
    @override
    def is_looping(self: Self) -> bool:
        return self._is_looping

    @is_looping.setter
    def is_looping(self: Self, value: bool) -> None:
        self._is_looping = value

    @property
    @override
    def playing(self: Self) -> WavelinkSong | None:
        return self._current

    @property
    @override
    def seek_position(self: Self) -> int:
        return int(self._player.position)

    @property
    @override
    def next_queue(self: Self) -> list[WavelinkSong]:
        return list(self._next_queue)

    @property
    @override
    def previous_queue(self: Self) -> list[WavelinkSong]:
        return list(self._previous_queue)

    @override
    async def disconnect(self: Self) -> None:
        await self._player.disconnect()

    @override
    async def play(self: Self, audio_source: WavelinkSong) -> None:
        self._refresh_disconnect_timer()
        await self._player.play(audio_source.stream)

    @override
    async def play_multiple(self: Self, songs: list[WavelinkSong]) -> None:
        self._refresh_disconnect_timer()
        await self._player.play(songs[0].stream)
        for song in songs[1:]:
            self._next_queue.appendleft(song)

    @override
    async def add(self: Self, audio_source: WavelinkSong, index: int = -1) -> PlayerResult:
        if not self._current:
            self._refresh_disconnect_timer()
            await self._player.play(audio_source.stream)
            self._current = audio_source
            return PlayerResult.PLAYING

        if index >= 0:
            self._next_queue.insert(index, audio_source)
            return PlayerResult.QUEUEING

        self._next_queue.append(audio_source)
        return PlayerResult.QUEUEING

    @override
    async def add_multiple(
        self: Self, audio_sources: list[WavelinkSong], index: int = -1
    ) -> PlayerResult:
        if not self._current:
            self._refresh_disconnect_timer()
            await self._player.play(audio_sources[0].stream)
            self._current = audio_sources[0]
            for audio_source in audio_sources[1:]:
                self._next_queue.append(audio_source)
            return PlayerResult.PLAYING

        if index >= 0:
            insert_index = index
            for audio_source in audio_sources:
                self._next_queue.insert(insert_index, audio_source)
                insert_index += 1

        for audio_source in audio_sources:
            self._next_queue.append(audio_source)
        return PlayerResult.QUEUEING

    @override
    async def remove(self: Self, index: int = -1) -> None:
        if index >= 0:
            del self._next_queue[index]
            return
        self._next_queue.pop()

    @override
    async def clear(self: Self) -> None:
        self._next_queue.clear()
        self._previous_queue.clear()

    @override
    async def seek(self: Self, position: int) -> None:
        await self._player.seek(position)

    @override
    async def pause(self: Self) -> None:
        await self._player.pause(True)  # noqa: FBT003

    @override
    async def resume(self: Self) -> None:
        await self._player.pause(False)  # noqa: FBT003

    @override
    async def loop(self: Self) -> None:
        self._is_looping = True

    @override
    async def unloop(self: Self) -> None:
        self._is_looping = False

    @override
    async def move(self: Self, first_index: int, second_index: int) -> None:
        song = self._next_queue[first_index]
        await self.remove(first_index)
        await self.add(song, second_index)

    @override
    async def shuffle(self: Self) -> None:
        random.shuffle(self._next_queue)

    @override
    async def stop(self: Self) -> None:
        await self._player.stop()

    @override
    async def next(self: Self) -> bool:
        if not self._player.playing:
            return False
        self._queue_reverse = False
        self._is_skipping = True
        await self._player.stop()
        return True

    @override
    async def previous(self: Self) -> None:
        self._queue_reverse = True
        self._is_skipping = True
        await self._player.stop()

    @override
    async def process_song_end(self: Self) -> None:
        self._refresh_disconnect_timer()

        # Play current song again if set to loop.
        if self._is_looping and not self._is_skipping and self._current:
            await self.play(self._current)
            return
        self._is_skipping = False

        # Play next or previous based on direction toggle
        if self._queue_reverse:
            await self._play_previous_song()
            return
        await self._play_next_song()
        self._queue_reverse = False

    async def _play_next_song(self: Self) -> None:
        next_song = None
        try:
            next_song = self._next_queue.popleft()
            await self._player.play(next_song.stream)
        except IndexError:
            pass

        if self._current:
            self._previous_queue.appendleft(self._current)
            self._current = next_song

    async def _play_previous_song(self: Self) -> None:
        previous_song = None
        try:
            previous_song = self._previous_queue.popleft()
            await self._player.play(previous_song.stream)
        except IndexError:
            pass

        if self._current:
            self._next_queue.appendleft(self._current)
            self._current = previous_song

    async def enable_auto_disconnect(self: Self) -> None:
        """Enables auto disconnection after a set inactivity time."""
        self._disconnect_job.start()

    async def disable_auto_disconnect(self: Self) -> None:
        """Disables auto disconnection after aset inactivity time."""
        self._disconnect_job.cancel()

    @tasks.loop(seconds=30)
    async def _disconnect_job(self: Self) -> None:
        if (
            self._is_auto_disconnect()
            and time() > self._disconnect_time
            and not self._player.playing
        ):
            await self.disconnect()

    def _refresh_disconnect_timer(self: Self) -> None:
        self._disconnect_time = time() + self._get_disconnect_time_limit()

    def _get_disconnect_time_limit(self: Self) -> int:
        config = toml.load(constants.DATA_DIR + "config.toml")
        return config["music"]["disconnect_time"]

    def _is_auto_disconnect(self: Self) -> bool:
        config = toml.load(constants.DATA_DIR + "config.toml")
        return config["music"]["auto_disconnect"]
