import uuid
import discord
import datetime

from typing import Optional

class Playlist:
    def __init__(self, id_, name, guild_id, creator_id, creation_date, modified_date, description):
        self._id: uuid.UUID = id_
        self._name = name
        self._guild_id = guild_id
        self._creator_id = creator_id
        self._creation_date: datetime.datetime = creation_date
        self._modified_date: datetime.datetime = modified_date
        self._description = description

    @classmethod
    def create_new(cls, name, guild, creator: discord.User):
        return cls(uuid.uuid4(), name, guild.id, creator.id, datetime.datetime.now(tz=datetime.timezone.utc),
                   datetime.datetime.now(tz=datetime.timezone.utc), "")

    @property
    def id(self) -> uuid.UUID:
        return self._id

    @property
    def name(self) -> str:
        return self._name

    @name.setter
    def name(self, value):
        self._name = value

    @property
    def guild_id(self) -> int:
        return self._guild_id

    @property
    def creator_id(self) -> int:
        return self._creator_id

    @property
    def creation_date(self) -> datetime.datetime:
        return self._creation_date

    @property
    def modified_date(self) -> datetime.datetime:
        return self._creation_date

    @modified_date.setter
    def modified_date(self, value: datetime.datetime):
        self._creation_date = value

    @property
    def description(self) -> str:
        return self._description

    @description.setter
    def description(self, value):
        self._description = value

class PlaylistRepository:
    def __init__(self, database):
        self.db = database
        cursor = self.db.cursor()
        cursor.execute('PRAGMA foreign_keys = ON')
        cursor.execute('CREATE TABLE IF NOT EXISTS playlist '
                       '(id TEXT PRIMARY KEY, name TEXT, guild_id INTEGER, creator_id INTEGER, creation_date INTEGER,'
                       ' modified_date INTEGER, description TEXT)')
        self.db.commit()

    def get_all(self):
        """Get list of all playlists"""
        results = self.db.cursor().execute('SELECT * FROM playlist').fetchall()
        playlists = []
        for result in results:
            playlists.append(self._result_to_playlist(result))
        return playlists

    def get_by_id(self, id_):
        result = self.db.cursor().execute('SELECT * FROM playlist WHERE id=?', (id_,)).fetchone()
        return self._result_to_playlist(result)

    def get_by_guild(self, guild):
        # Get list of all playlists in a guild
        cursor = self.db.cursor()
        values = (guild.id,)
        cursor.execute('SELECT * FROM playlist WHERE guild_id=?', values)
        results = cursor.fetchall()

        playlists = []
        for result in results:
            playlists.append(self._result_to_playlist(result))
        return playlists

    def get_by_name_in_guild(self, name, guild):
        # Get playlist by guild and playlist name
        cursor = self.db.cursor()
        values = (guild.id, name)
        result = cursor.execute('SELECT * FROM playlist WHERE guild_id=? AND name=?', values).fetchone()
        return self._result_to_playlist(result)

    def add(self, playlist):
        cursor = self.db.cursor()
        values = (str(playlist.id), playlist.name, playlist.guild_id, playlist.creator_id,
                  int(playlist.creation_date.timestamp()), int(playlist.modified_date.timestamp()),
                  playlist.description)
        cursor.execute('INSERT INTO playlist VALUES (?, ?, ?, ?, ?, ?, ?)', values)
        self.db.commit()

    def update(self, playlist):
        cursor = self.db.cursor()
        values = (playlist.name, playlist.guild_id, playlist.creator_id, int(playlist.creation_date.timestamp()),
                  int(playlist.modified_date.timestamp()), playlist.description, playlist.id)
        cursor.execute('UPDATE playlist SET name=?, guild_id=?, creator_id=?, creation_date=?, modified_date=?, '
                       'description=? WHERE id=?', values)
        self.db.commit()

    def remove(self, id_: uuid.UUID):
        cursor = self.db.cursor()
        cursor.execute('DELETE FROM playlist WHERE id=?', (str(id_),))
        self.db.commit()

    @staticmethod
    def _result_to_playlist(result):
        return Playlist(result[0], result[1], result[2], result[3],
                        datetime.datetime.fromtimestamp(result[4], tz=datetime.timezone.utc),
                        datetime.datetime.fromtimestamp(result[5], tz=datetime.timezone.utc),
                        result[6]) if result else None


class PlaylistSong:
    def __init__(self, id_, playlist_id, requester_id, title, artist, duration, url, previous_id):
        self._id: uuid.UUID = id_
        self._playlist_id = playlist_id
        self._requester_id = requester_id
        self._title = title
        self._artist = artist
        self._url = url
        self._duration = duration
        self._previous_id = previous_id

    @classmethod
    def create_new(cls, playlist_id, requester_id, title, artist, duration, url, previous_id):
        return cls(uuid.uuid4(), playlist_id, requester_id, title, artist, duration, url, previous_id)

    @property
    def id(self) -> uuid.UUID:
        return self._id

    @property
    def playlist_id(self) -> uuid.UUID:
        return self._playlist_id

    @property
    def requester_id(self) -> int:
        return self._requester_id

    @property
    def title(self) -> str:
        return self._title

    @property
    def artist(self) -> Optional[str]:
        return self._artist

    @property
    def duration(self) -> int:
        return self._duration

    @property
    def url(self) -> str:
        return self._url

    @property
    def previous_id(self) -> uuid.UUID:
        return self._previous_id

    @previous_id.setter
    def previous_id(self, value: uuid.UUID):
        self._previous_id = value

class PlaylistSongRepository:
    def __init__(self, database):
        self.db = database
        cursor = self.db.cursor()
        cursor.execute('PRAGMA foreign_keys = ON')
        cursor.execute('CREATE TABLE IF NOT EXISTS playlist_songs (id TEXT PRIMARY KEY, playlist_id TEXT, '
                       'requester_id INTEGER, title TEXT, artist TEXT, duration INTEGER, url TEXT, '
                       'previous_id INTEGER, FOREIGN KEY(playlist_id) REFERENCES playlist(id))')
        self.db.commit()

    def get_by_id(self, id_):
        result = self.db.cursor().execute('SELECT * FROM playlist_songs WHERE id=?', (id_,)).fetchone()
        return self._result_to_playlist_song(result)

    def get_by_playlist(self, playlist_id: uuid.UUID):
        # Get list of all songs in playlist
        cursor = self.db.cursor()
        cursor.execute('SELECT * FROM playlist_songs WHERE playlist_id=?', (str(playlist_id),))
        results = cursor.fetchall()

        songs = []
        for result in results:
            songs.append(self._result_to_playlist_song(result))
        return songs

    def add(self, playlist_song: PlaylistSong):
        cursor = self.db.cursor()
        values = (str(playlist_song.id), str(playlist_song.playlist_id), playlist_song.requester_id,
                  playlist_song.title, playlist_song.artist, playlist_song.duration, playlist_song.url,
                  str(playlist_song.previous_id))
        cursor.execute('INSERT INTO playlist_songs VALUES (?, ?, ?, ?, ?, ?, ?, ?)', values)
        self.db.commit()

    def update(self, playlist_song: PlaylistSong):
        cursor = self.db.cursor()
        values = (str(playlist_song.playlist_id), playlist_song.requester_id, playlist_song.title,
                  playlist_song.artist, playlist_song.duration, playlist_song.url, str(playlist_song.previous_id),
                  str(playlist_song.id))
        cursor.execute('UPDATE playlist_songs SET playlist_id=?, requester_id=?, title=?, '
                       'artist=?, duration=?, url=?, previous_id=? WHERE id=?', values)
        self.db.commit()

    def remove(self, id_):
        cursor = self.db.cursor()
        cursor.execute('DELETE FROM playlist_songs WHERE id=?', (str(id_),))
        self.db.commit()

    @staticmethod
    def _result_to_playlist_song(result):
        return PlaylistSong(uuid.UUID(result[0]), uuid.UUID(result[1]), result[2], result[3],
                            result[4], result[5], result[6], uuid.UUID(result[7])) if result else None