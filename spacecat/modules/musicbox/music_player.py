"""
Module for playing music from various sources.

This module provides commands for playing music from sources such as
YouTube, Spotify, and local files. It also allows users to create
playlists that can store songs and be played.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from enum import Enum
from typing import TYPE_CHECKING, Generic, Self, TypeVar

if TYPE_CHECKING:
    import discord


class OriginalSource(Enum):
    """Enum representing the different original sources of a song."""

    LOCAL = "Saved Playlist"
    YOUTUBE_VIDEO = "YouTube"
    YOUTUBE_SONG = "YouTube Music"
    YOUTUBE_PLAYLIST = "YouTube Playlist"
    YOUTUBE_ALBUM = "YouTube Album"
    SPOTIFY_SONG = "Spotify"
    SPOTIFY_PLAYLIST = "Spotify Playlist"
    SPOTIFY_ALBUM = "Spotify Album"
    UNKNOWN = "Unknown"


class PlayerResult(Enum):
    """Enum representing the result of a player action."""

    PLAYING = 0
    QUEUEING = 1


class SongUnavailableError(ValueError):
    """Exception raised when a song is unavailable."""


StreamType = TypeVar("StreamType")


class Song(ABC, Generic[StreamType]):
    """
    Abstract base class representing a song.

    This class provides the basic structure for a song and defines the
    necessary abstract methods that must be implemented by subclasses.
    """

    @property
    @abstractmethod
    def stream(self: Self) -> StreamType:
        """
        Gets stream object of the song to be used for playback.

        Returns:
            StreamType: The stream object.
        """

    @property
    @abstractmethod
    def title(self: Self) -> str:
        """
        Get the title of the song.

        Returns:
            str: The title of the song.
        """

    @property
    @abstractmethod
    def artist(self: Self) -> str | None:
        """
        Get the artist of the song.

        Returns:
            Optional[str]: The artist of the song, or None if the artist
                is not available.
        """

    @property
    @abstractmethod
    def duration(self: Self) -> int:
        """
        Get the duration of the song.

        Returns:
            int: The duration of the song in seconds.
        """

    @property
    @abstractmethod
    def url(self: Self) -> str:
        """
        Get the URL of the song.

        Returns:
            str: The URL of the song.
        """

    @property
    @abstractmethod
    def group(self: Self) -> str:
        """
        Get the group that the song exists in.

        Groups may include collections such as playlists or albums.

        Returns:
            str: The group of the song.
        """

    @property
    @abstractmethod
    def group_url(self: Self) -> str:
        """
        Get the URL of the group the song belongs in.

        Returns:
            str: The URL of the group.
        """

    @property
    @abstractmethod
    def original_source(self: Self) -> OriginalSource:
        """
        Get the original source of the song.

        Returns:
            OriginalSource: The original source of the song.
        """

    @property
    @abstractmethod
    def requester_id(self: Self) -> int:
        """
        Get the discord user ID of the requester of the song.

        Returns:
            int: The ID of the requester.
        """


T_Song = TypeVar("T_Song", bound=Song)


class MusicPlayer(ABC, Generic[T_Song]):
    """
    Abstract base class for music players.

    This class provides a common interface for music players to
    implement. It defines the basic functionality and properties that a
    music player should have.
    """

    @property
    @abstractmethod
    def is_paused(self: Self) -> bool:
        """
        Get the paused state of the music player.

        Returns:
            bool: True if the music player is paused, False otherwise.
        """

    @property
    @abstractmethod
    def is_looping(self: Self) -> bool:
        """
        Get the looping state of the music player.

        Args:
            bool: True if the music player is looping, False otherwise.
        """

    @is_looping.setter
    @abstractmethod
    def is_looping(self: Self, value: bool) -> None:
        """
        Set the looping state of the music player.

        Args:
            value: The new looping state to set. True to enable looping,
                False otherwise.
        """

    @property
    @abstractmethod
    def playing(self: Self) -> T_Song:
        """
        Get the currently playing song.

        Returns:
            T_Song: The currently playing song.
        """

    @property
    @abstractmethod
    def seek_position(self: Self) -> int:
        """
        Get the current seek position of the music player.

        Returns:
            int: The current seek position in seconds.
        """

    @property
    @abstractmethod
    def next_queue(self: Self) -> list[T_Song]:
        """
        Get the list of songs that are next in the queue.

        Returns:
            list[T_Song]: The next queue of songs.
        """

    @property
    @abstractmethod
    def previous_queue(self: Self) -> list[T_Song]:
        """
        Get the list of songs that were played before the current song.

        Returns:
            list[T_Song]: The queue of songs that were played before the
                current song.
        """

    @abstractmethod
    async def connect(self: Self, channel: discord.VoiceChannel) -> None:
        """
        Connects the music player to the specified channel.

        Args:
            channel (Channel): The channel to connect to.
        """

    @abstractmethod
    async def disconnect(self: Self) -> None:
        """Disconnects the music player from the current channel."""

    @abstractmethod
    async def play(self: Self, song: T_Song) -> None:
        """
        Plays a given song.

        Args:
            song (T_Song): The song to be played.
        """

    @abstractmethod
    async def play_multiple(self: Self, songs: list[T_Song]) -> None:
        """
        Plays a collection of songs, pushing all songs into the queue.

        The first song is immediately played, while the remainder are
        prioritised ahead of all other songs in the queue.

        Args:
            songs (list[T_Song]): A list of songs to be played.
        """

    @abstractmethod
    async def add(self: Self, song: T_Song, index: int = 0) -> PlayerResult:
        """
        Adds a song to the play queue.

        Args:
            song (T_Song): The song to be added to the queue.
            index (int, optional): The index at which the song should be
                added. Defaults to the last in queue.
        """

    @abstractmethod
    async def add_multiple(self: Self, songs: list[T_Song], index: int = 0) -> PlayerResult:
        """
        Adds multiple songs to the play queue.

        Args:
            songs (list[T_Song]): A list of songs to be added to the
                queue.
            index (int, optional): The index at which the songs should
                be added. Defaults to the last in queue.
        """

    @abstractmethod
    async def remove(self: Self, index: int = 0) -> None:
        """
        Removes a song from the queue.

        Args:
            index (int, optional): The index of the item to be removed.
                Defaults to the last in queue.
        """

    @abstractmethod
    async def clear(self: Self) -> None:
        """Clears all songs from the queue."""

    @abstractmethod
    async def seek(self: Self, position: int) -> None:
        """
        Sets the play head to a specified position in the song.

        Args:
            position (int): The position in seconds to seek to.
        """

    @abstractmethod
    async def next(self: Self) -> None:
        """Plays the next song in the queue."""

    @abstractmethod
    async def previous(self: Self) -> None:
        """Plays the previous song in the queue."""

    @abstractmethod
    async def pause(self: Self) -> None:
        """Pauses the song, keeping the current position saved."""

    @abstractmethod
    async def resume(self: Self) -> None:
        """Resumes the song from the position it was paused."""

    @abstractmethod
    async def loop(self: Self) -> None:
        """Loops the currently playing song."""

    @abstractmethod
    async def unloop(self: Self) -> None:
        """Stops looping the currently playing song."""

    @abstractmethod
    async def move(self: Self, first_index: int, second_index: int) -> None:
        """
        Move a song from one index to another in the playlist.

        Args:
            first_index (int): The index of the song to move.
            second_index (int): The index to move the song to.
        """

    @abstractmethod
    async def shuffle(self: Self) -> None:
        """Shuffles the current queue into a random order."""

    @abstractmethod
    async def stop(self: Self) -> None:
        """Stops the currently playing song and clears the queue."""

    @abstractmethod
    async def process_song_end(self: Self) -> None:
        """
        Processing when a song completes.

        (Needs consideration to be removed and implemented elsewhere)
        """

    @abstractmethod
    async def enable_auto_disconnect(self: Self) -> None:
        """Enables auto disconnection after a set inactivity time."""

    @abstractmethod
    async def disable_auto_disconnect(self: Self) -> None:
        """Disables auto disconnection after a set inactivity time."""
