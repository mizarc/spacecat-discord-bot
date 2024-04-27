from typing import Optional, Any, Generic, TypeVar
from abc import ABC, abstractmethod

from spacecat.modules.musicbox import OriginalSource

class Song(ABC):
    @property
    @abstractmethod
    def stream(self) -> Any:
        """
        Gets the stream object of the song that will be utilised for playback.

        Returns:
            Any: The stream object.
        """
        pass

    @property
    @abstractmethod
    def title(self) -> str:
        """
        Get the title of the song.

        Returns:
            str: The title of the song.
        """
        pass

    @property
    @abstractmethod
    def artist(self) -> Optional[str]:
        """
        Get the artist of the song.

        Returns:
            Optional[str]: The artist of the song, or None if the artist is not available.
        """
        pass

    @property
    @abstractmethod
    def duration(self) -> int:
        """
        Get the duration of the song.

        Returns:
            int: The duration of the song in seconds.
        """
        pass

    @property
    @abstractmethod
    def url(self) -> str:
        """
        Get the URL of the song.

        Returns:
            str: The URL of the song.
        """
        pass

    @property
    @abstractmethod
    def group(self) -> str:
        """
        Get the group that the song exists in. This may be a playlist, album, EP, etc.

        Returns:
            str: The group of the song.
        """
        pass

    @property
    @abstractmethod
    def group_url(self) -> str:
        """
        Get the URL of the group the song belongs in.

        Returns:
            str: The URL of the group.
        """
        pass

    @property
    @abstractmethod
    def original_source(self) -> OriginalSource:
        pass

    @property
    @abstractmethod
    def requester_id(self) -> int:
        """
        Get the discord user ID of the requester of the song.

        Returns:
            int: The ID of the requester.
        """
        pass

T_Song = TypeVar("T_Song", bound=Song)

class MusicPlayer(ABC, Generic[T_Song]):
    @property
    @abstractmethod
    def is_paused(self) -> bool:
        """
        Get the paused state of the music player.

        Returns:
            bool: True if the music player is paused, False otherwise.
        """
        pass

    @property
    @abstractmethod
    def is_looping(self) -> bool:
        """
        Get the looping state of the music player.

        Args:
            bool: True if the music player is looping, False otherwise.
        """
        pass

    @is_looping.setter
    @abstractmethod
    def is_looping(self, value):
        """
        Set the looping state of the music player.

        Args:
            value: The new looping state to set. True to enable looping, False otherwise.
        """
        pass

    @property
    @abstractmethod
    def playing(self) -> T_Song:
        """
        Get the currently playing song.

        Returns:
            T_Song: The currently playing song.
        """
        pass

    @property
    @abstractmethod
    def seek_position(self) -> int:
        """
        Get the current seek position of the music player.

        Returns:
            int: The current seek position in seconds.
        """
        pass

    @property
    @abstractmethod
    def next_queue(self) -> list[T_Song]:
        """
        Get the list of songs that are next in the queue.

        Returns:
            list[T_Song]: The next queue of songs.
        """
        pass

    @property
    @abstractmethod
    def previous_queue(self) -> list[T_Song]:
        """
        Get the list of songs that were played before the current song.

        Returns:
            list[T_Song]: The queue of songs that were played before the current song.
        """
        pass

    @abstractmethod
    async def connect(self, channel):
        """
        Connects the music player to the specified channel.

        Args:
            channel (Channel): The channel to connect to.
        """
        pass

    @abstractmethod
    async def disconnect(self):
        pass

    @abstractmethod
    async def play(self, song: T_Song):
        """
        Plays a given song.

        Args:
            song (T_Song): The song to be played.

        Returns:
            None
        """
        pass

    @abstractmethod
    async def play_multiple(self, songs: list[T_Song]):
        """
        Plays a list of songs, the first song being immediately played and the rest added to queue.

        Args:
            songs (list[T_Song]): A list of songs to be played.

        Returns:
            None
        """
        pass

    @abstractmethod
    async def add(self, song: T_Song, index=0):
        """
        Adds a song to the play queue.

        Args:
            song (T_Song): The song to be added to the queue.
            index (int, optional): The index at which the song should be added. Defaults to the last in queue.

        Returns:
            None
        """
        pass

    @abstractmethod
    async def add_multiple(self, songs: list[T_Song], index=0):
        """
        Adds multiple songs to the play queue.

        Args:
            songs (list[T_Song]): A list of songs to be added to the queue.
            index (int, optional): The index at which the songs should be added. Defaults to the last in queue.

        Returns:
            None
        """
        pass

    @abstractmethod
    async def remove(self, index=0):
        """
        Removes a song from the queue.

        Args:
            index (int, optional): The index of the item to be removed. Defaults to the last in queue.

        Returns:
            None
        """
        pass

    @abstractmethod
    async def clear(self):
        """
        Clears all songs from the queue.
        """
        pass

    @abstractmethod
    async def seek(self, position):
        """
        Sets the play head to a specified position in the song.

        Args:
            position (int): The position in seconds to seek to.

        Returns:
            None
        """
        pass

    @abstractmethod
    async def next(self):
        """
        Plays the next song in the queue.
        """
        pass

    @abstractmethod
    async def previous(self):
        """
        Plays the previous song in the queue.
        """
        pass

    @abstractmethod
    async def pause(self):
        """
        Pauses the music player, keeping the current position of the song saved.
        """
        pass

    @abstractmethod
    async def resume(self):
        """
        Resumes the playback of the music player from the position it was paused.
        """
        pass

    @abstractmethod
    async def loop(self):
        """
        Loops the currently playing song.
        """
        pass

    @abstractmethod
    async def unloop(self):
        """
        Stops looping the currently playing song.
        """
        pass

    @abstractmethod
    async def move(self, first_index, second_index):
        """
        Move a song from one index to another in the playlist.

        Args:
            first_index (int): The index of the song to move.
            second_index (int): The index to move the song to.
        """
        pass

    @abstractmethod
    async def shuffle(self):
        """
        Shuffles the current queue so that all existing entries are in a random order.
        """
        pass

    @abstractmethod
    async def stop(self):
        """
        Stops the currently playing song and clears the queue.
        """
        pass

    @abstractmethod
    async def process_song_end(self):
        """
        Processing when a song completes (Needs consideration to be removed and implemented elsewhere)
        """
        pass

    @abstractmethod
    async def enable_auto_disconnect(self):
        """
        Enables the automatic disconnection of the music player after a set time of inactivity.
        """
        pass

    @abstractmethod
    async def disable_auto_disconnect(self):
        """
        Disables the automatic disconnection of the music player after a set time of inactivity.
        """
        pass