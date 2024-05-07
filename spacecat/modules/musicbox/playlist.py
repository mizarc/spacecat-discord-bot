"""
Module for handling playlists.

Playlists are a way to organize a collection of songs into a list that can
be played by the musicbox module.

"""

from __future__ import annotations

import datetime
import uuid
from typing import TYPE_CHECKING, Self

if TYPE_CHECKING:
    from sqlite3 import Connection

    import discord


class Playlist:
    """Represents a playlist of music."""

    def __init__(
        self: Self,
        id_: uuid.UUID,
        name: str,
        guild_id: int,
        creator_id: int,
        creation_date: datetime.datetime,
        modified_date: datetime.datetime,
        description: str,
    ) -> None:
        """
        Initialise an instance of 'Playlist' using existing values.

        Args:
            id_ (uuid.UUID): The unique identifier of the playlist.
            name (str): The name of the playlist.
            guild_id (int): The ID of the guild associated with the
                playlist.
            creator_id (int): The ID of the user who created the
                playlist.
            creation_date (datetime.datetime): The date and time when
                the playlist was created.
            modified_date (datetime.datetime): The date and time when
                the playlist was last modified.
            description (str): The description of the playlist.
        """
        self._id: uuid.UUID = id_
        self._name = name
        self._guild_id = guild_id
        self._creator_id = creator_id
        self._creation_date: datetime.datetime = creation_date
        self._modified_date: datetime.datetime = modified_date
        self._description = description

    @classmethod
    def create_new(
        cls: type[Self], name: str, guild: discord.Guild, creator: discord.User
    ) -> Self:
        """
        Instantiates a new Playlist with minimum required parameters.

        Args:
            name (str): The name of the playlist.
            guild (discord.Guild): The guild associated with the
                playlist.
            creator (discord.User): The user who created the playlist.

        Returns:
            Playlist: The newly created playlist instance.
        """
        return cls(
            uuid.uuid4(),
            name,
            guild.id,
            creator.id,
            datetime.datetime.now(tz=datetime.timezone.utc),
            datetime.datetime.now(tz=datetime.timezone.utc),
            "",
        )

    @property
    def id(self: Self) -> uuid.UUID:
        """
        Getter for the id property of the Playlist.

        Returns:
            uuid.UUID: The id of the Playlist.
        """
        return self._id

    @property
    def name(self: Self) -> str:
        """
        Getter for the name property of the Playlist.

        Returns:
            str: The name of the Playlist.
        """
        return self._name

    @name.setter
    def name(self: Self, value: str) -> None:
        """
        Setter for the 'name' property of the Playlist.

        Args:
            value (str): The value to set as the name of the Playlist.
        """
        self._name = value

    @property
    def guild_id(self: Self) -> int:
        """
        Getter for the guild_id property of the Playlist.

        Returns:
            int: The guild_id of the Playlist.
        """
        return self._guild_id

    @property
    def creator_id(self: Self) -> int:
        """
        Getter for the creator_id property of the object.

        Returns:
            int: The creator_id of the object.
        """
        return self._creator_id

    @property
    def creation_date(self: Self) -> datetime.datetime:
        """
        Getter for the creation_date property of the object.

        Returns:
            datetime.datetime: The creation_date of the object.
        """
        return self._creation_date

    @property
    def modified_date(self: Self) -> datetime.datetime:
        """
        Getter for the modified_date property of the object.

        Returns:
            datetime.datetime: The modified_date of the object.
        """
        return self._creation_date

    @modified_date.setter
    def modified_date(self: Self, value: datetime.datetime) -> None:
        """
        Set the modified date of the object to the provided value.

        Args:
            value (datetime.datetime): The new value for the modified
                date.
        """
        self._creation_date = value

    @property
    def description(self: Self) -> str:
        """
        Returns the description of the object.

        Returns:
            str: A string representing the description of the object.
        """
        return self._description

    @description.setter
    def description(self: Self, value: str) -> None:
        """
        Set the description of the object to the provided value.

        Args:
            value (str): The new value for the description.
        """
        self._description = value


class PlaylistRepository:
    """Repository for storing and retrieving playlists."""

    def __init__(self: Self, database: Connection) -> None:
        """
        Initialise a new instance of the PlaylistRepository class.

        Args:
            database (Connection): The database connection object.
        """
        self.db = database
        cursor = self.db.cursor()
        cursor.execute("PRAGMA foreign_keys = ON")
        cursor.execute(
            "CREATE TABLE IF NOT EXISTS playlist "
            "(id TEXT PRIMARY KEY, name TEXT, guild_id INTEGER, creator_id INTEGER, "
            "creation_date INTEGER, modified_date INTEGER, description TEXT)"
        )
        self.db.commit()

    def get_all(self: Self) -> list[Playlist | None]:
        """Get list of all playlists."""
        results = self.db.cursor().execute("SELECT * FROM playlist").fetchall()
        return [self._result_to_playlist(result) for result in results]

    def get_by_id(self: Self, id_: uuid.UUID) -> Playlist | None:
        """
        Get a playlist by its ID.

        Args:
            id_ (uuid.UUID): The ID of the playlist to retrieve.

        Returns:
            Playlist | None: The playlist with the specified ID, or
                None if it does not exist.
        """
        result = self.db.cursor().execute("SELECT * FROM playlist WHERE id=?", (id_,)).fetchone()
        return self._result_to_playlist(result)

    def get_by_guild(self: Self, guild: discord.Guild) -> list[Playlist | None]:
        """
        Get list of all playlists in a guild.

        Args:
            guild: The guild associated with the playlist.

        Returns:
            List[Playlist]: List of playlists in the guild
        """
        # Get list of all playlists in a guild
        cursor = self.db.cursor()
        values = (guild.id,)
        cursor.execute("SELECT * FROM playlist WHERE guild_id=?", values)
        results = cursor.fetchall()

        return [self._result_to_playlist(result) for result in results]

    def get_by_name_in_guild(self: Self, name: str, guild: discord.Guild) -> Playlist | None:
        """
        Get a playlist by its name and guild.

        Args:
            name (str): The name of the playlist.
            guild (discord.Guild): The guild associated with the
                playlist.

        Returns:
            Playlist: The playlist with the specified name and guild, or
                None if it does not exist.
        """
        # Get playlist by guild and playlist name
        cursor = self.db.cursor()
        values = (guild.id, name)
        result = cursor.execute(
            "SELECT * FROM playlist WHERE guild_id=? AND name=?", values
        ).fetchone()
        return self._result_to_playlist(result)

    def add(self: Self, playlist: Playlist) -> None:
        """
        Add a new playlist to the database.

        Args:
            playlist: The playlist object to be added.
        """
        cursor = self.db.cursor()
        values = (
            str(playlist.id),
            playlist.name,
            playlist.guild_id,
            playlist.creator_id,
            int(playlist.creation_date.timestamp()),
            int(playlist.modified_date.timestamp()),
            playlist.description,
        )
        cursor.execute("INSERT INTO playlist VALUES (?, ?, ?, ?, ?, ?, ?)", values)
        self.db.commit()

    def update(self: Self, playlist: Playlist) -> None:
        """
        Update a playlist in the database.

        Args:
            playlist (Playlist): The playlist object to be updated.
        """
        cursor = self.db.cursor()
        values = (
            playlist.name,
            playlist.guild_id,
            playlist.creator_id,
            int(playlist.creation_date.timestamp()),
            int(playlist.modified_date.timestamp()),
            playlist.description,
            playlist.id,
        )
        cursor.execute(
            "UPDATE playlist SET name=?, guild_id=?, creator_id=?, creation_date=?, "
            "modified_date=?, description=? WHERE id=?",
            values,
        )
        self.db.commit()

    def remove(self: Self, id_: uuid.UUID) -> None:
        """
        Remove a playlist from the database by its ID.

        Args:
            id_ (uuid.UUID): The ID of the playlist to be removed.
        """
        cursor = self.db.cursor()
        cursor.execute("DELETE FROM playlist WHERE id=?", (str(id_),))
        self.db.commit()

    @staticmethod
    def _result_to_playlist(result: tuple) -> Playlist | None:
        """
        Convert a database result tuple to a Playlist object.

        Args:
            result (tuple): The resulting tuple from the database query.

        Returns:
            Playlist | None: The converted Playlist object, or
                None if the result is empty.
        """
        return (
            Playlist(
                result[0],
                result[1],
                result[2],
                result[3],
                datetime.datetime.fromtimestamp(result[4], tz=datetime.timezone.utc),
                datetime.datetime.fromtimestamp(result[5], tz=datetime.timezone.utc),
                result[6],
            )
            if result
            else None
        )


class PlaylistSong:
    """A song in a playlist."""

    def __init__(
        self: Self,
        id_: uuid.UUID,
        playlist_id: uuid.UUID,
        requester_id: int,
        title: str,
        artist: str,
        duration: int,
        url: str,
        previous_id: uuid.UUID,
    ) -> None:
        """
        Initialise a new instance of the PlaylistSong class.

        Args:
        ----
            self (PlaylistSong): The instance of the class being
                initialized.
            id_ (uuid.UUID): The unique identifier of the song.
            playlist_id (uuid.UUID): The unique identifier of the
                playlist.
            requester_id (int): The ID of the user who requested the
                song.
            title (str): The title of the song.
            artist (str): The artist of the song.
            duration (int): The duration of the song in seconds.
            url (str): The URL of the song.
            previous_id (uuid.UUID): The unique identifier of the
                previous song in the playlist.
        """
        self._id: uuid.UUID = id_
        self._playlist_id = playlist_id
        self._requester_id = requester_id
        self._title = title
        self._artist = artist
        self._url = url
        self._duration = duration
        self._previous_id = previous_id

    @classmethod
    def create_new(
        cls: type[Self],
        playlist_id: uuid.UUID,
        requester_id: int,
        title: str,
        artist: str,
        duration: int,
        url: str,
        previous_id: uuid.UUID,
    ) -> Self:
        """
        A function to create a new instance of the PlaylistSong class.

        Args:
            cls (type[Self]): The class type.
            playlist_id (uuid.UUID): The unique identifier of the
                playlist.
            requester_id (int): The ID of the user who requested the
                song.
            title (str): The title of the song.
            artist (str): The artist of the song.
            duration (int): The duration of the song in seconds.
            url (str): The URL of the song.
            previous_id (uuid.UUID): The unique identifier of the
                previous song in the playlist.

        Returns:
            Self: A new instance of the PlaylistSong class.
        """
        return cls(
            uuid.uuid4(), playlist_id, requester_id, title, artist, duration, url, previous_id
        )

    @property
    def id(self: Self) -> uuid.UUID:
        """
        A property that returns the unique identifier of the object.

        Returns:
            uuid.UUID: The unique identifier of the object.
        """
        return self._id

    @property
    def playlist_id(self: Self) -> uuid.UUID:
        """
        A property that returns the unique identifier of the playlist.

        Returns:
            uuid.UUID: The unique identifier of the playlist.
        """
        return self._playlist_id

    @property
    def requester_id(self: Self) -> int:
        """
        A property that returns the ID of the user who requested the song.

        Returns:
            int: The ID of the user who requested the song.
        """
        return self._requester_id

    @property
    def title(self: Self) -> str:
        """
        A property that returns the title of the song.

        Returns:
            str: The title of the song.
        """
        return self._title

    @property
    def artist(self: Self) -> str | None:
        """
        A property that returns the artist of the song.

        Returns:
            Optional[str]: The artist of the song, or None if the artist
                is not available.
        """
        return self._artist

    @property
    def duration(self: Self) -> int:
        """
        Get the duration of the song.

        Returns:
            int: The duration of the song.
        """
        return self._duration

    @property
    def url(self: Self) -> str:
        """
        Get the URL of the song.

        Returns:
            str: The URL of the song.
        """
        return self._url

    @property
    def previous_id(self: Self) -> uuid.UUID:
        """
        Get the unique identifier of the previous song in the playlist.

        Returns:
            uuid.UUID: The unique identifier of the previous song.
        """
        return self._previous_id

    @previous_id.setter
    def previous_id(self: Self, value: uuid.UUID) -> uuid.UUID | None:
        """
        Set the value of the previous_id attribute.

        Args:
            value (uuid.UUID): The new value for the previous_id attribute.
        """
        self._previous_id = value


class PlaylistSongRepository:
    """Repository for managing playlist songs in the database."""

    def __init__(self: Self, database: Connection) -> None:
        """
        Initialise a new instance of the PlaylistSongRepository class.

        Args:
            database: The database connection object.
        """
        self.db = database
        cursor = self.db.cursor()
        cursor.execute("PRAGMA foreign_keys = ON")
        cursor.execute(
            "CREATE TABLE IF NOT EXISTS playlist_songs (id TEXT PRIMARY KEY, playlist_id TEXT, "
            "requester_id INTEGER, title TEXT, artist TEXT, duration INTEGER, url TEXT, "
            "previous_id INTEGER, FOREIGN KEY(playlist_id) REFERENCES playlist(id))"
        )
        self.db.commit()

    def get_by_id(self: Self, id_: uuid.UUID) -> PlaylistSong | None:
        """
        Get a playlist song by its ID.

        Args:
            id_ (uuid.UUID): The ID of the playlist song to retrieve.

        Returns:
            Any: The playlist song object retrieved by the ID.
        """
        result = (
            self.db.cursor().execute("SELECT * FROM playlist_songs WHERE id=?", (id_,)).fetchone()
        )
        return self._result_to_playlist_song(result)

    def get_by_playlist(self: Self, playlist_id: uuid.UUID) -> list[PlaylistSong | None]:
        """
        Get a list of all songs in a playlist.

        Args:
            playlist_id (uuid.UUID): The ID of the playlist.

        Returns:
            list[PlaylistSong | None]: A list of PlaylistSong objects
                representing the songs in the playlist, or None if no
                songs are found.
        """
        # Get list of all songs in playlist
        cursor = self.db.cursor()
        cursor.execute("SELECT * FROM playlist_songs WHERE playlist_id=?", (str(playlist_id),))
        results = cursor.fetchall()
        return [self._result_to_playlist_song(result) for result in results]

    def add(self: Self, playlist_song: PlaylistSong) -> None:
        """
        Add a playlist song to the database.

        Args:
            playlist_song (PlaylistSong): The playlist song object to be added.
        """
        cursor = self.db.cursor()
        values = (
            str(playlist_song.id),
            str(playlist_song.playlist_id),
            playlist_song.requester_id,
            playlist_song.title,
            playlist_song.artist,
            playlist_song.duration,
            playlist_song.url,
            str(playlist_song.previous_id),
        )
        cursor.execute("INSERT INTO playlist_songs VALUES (?, ?, ?, ?, ?, ?, ?, ?)", values)
        self.db.commit()

    def update(self: Self, playlist_song: PlaylistSong) -> None:
        """
        Update a playlist song in the database.

        Args:
            playlist_song (PlaylistSong): The playlist song object to be
                updated.
        """
        cursor = self.db.cursor()
        values = (
            str(playlist_song.playlist_id),
            playlist_song.requester_id,
            playlist_song.title,
            playlist_song.artist,
            playlist_song.duration,
            playlist_song.url,
            str(playlist_song.previous_id),
            str(playlist_song.id),
        )
        cursor.execute(
            "UPDATE playlist_songs SET playlist_id=?, requester_id=?, title=?, "
            "artist=?, duration=?, url=?, previous_id=? WHERE id=?",
            values,
        )
        self.db.commit()

    def remove(self: Self, id_: uuid.UUID) -> None:
        """
        Removes a playlist song from the database by its ID.

        Parameters:
            id_ (uuid.UUID): The ID of the playlist song to be removed.
        """
        cursor = self.db.cursor()
        cursor.execute("DELETE FROM playlist_songs WHERE id=?", (str(id_),))
        self.db.commit()

    @staticmethod
    def _result_to_playlist_song(result: tuple) -> PlaylistSong | None:
        """
        Convert a database result tuple to a PlaylistSong object.

        Args:
            result (tuple): The resulting tuple from the database query.

        Returns:
            PlaylistSong | None: The converted PlaylistSong object, or
                None if the result is empty.
        """
        return (
            PlaylistSong(
                uuid.UUID(result[0]),
                uuid.UUID(result[1]),
                result[2],
                result[3],
                result[4],
                result[5],
                result[6],
                uuid.UUID(result[7]),
            )
            if result
            else None
        )
