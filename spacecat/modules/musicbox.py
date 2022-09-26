from abc import ABC, abstractmethod
import random
import sqlite3
from collections import deque
from itertools import islice
from time import time
from typing import Optional, Any, Generic, TypeVar

import discord
from discord import app_commands
from discord.ext import commands, tasks

from enum import Enum

import toml

import uuid

import wavelink
from wavelink import YouTubeMusicTrack

from wavelink.ext import spotify

from spacecat.helpers import constants
from spacecat.helpers import perms
from spacecat.helpers.spotify_extended_support import SpotifyPlaylist, SpotifyTrack, SpotifyAlbum


class SongUnavailableError(ValueError):
    pass


class PlayerResult(Enum):
    PLAYING = 0
    QUEUEING = 1


class OriginalSource(Enum):
    LOCAL = "Playlist"
    YOUTUBE_VIDEO = "YouTube Video"
    YOUTUBE_SONG = "YouTube Song"
    YOUTUBE_PLAYLIST = "YouTube Playlist"
    YOUTUBE_ALBUM = "YouTube Album"
    SPOTIFY_SONG = "Spotify Song"
    SPOTIFY_PLAYLIST = "Spotify Playlist"
    SPOTIFY_ALBUM = "Spotify Album"


class Playlist:
    def __init__(self, id_, name, guild_id, description):
        self._id: uuid.UUID = id_
        self._name = name
        self._guild_id = guild_id
        self._description = description

    @classmethod
    def create_new(cls, name, guild):
        return cls(uuid.uuid4(), name, guild.id, "")

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
                       '(id TEXT PRIMARY KEY, name TEXT, guild_id INTEGER, description TEXT)')
        self.db.commit()

    def get_all(self):
        """Get list of all playlists"""
        results = self.db.cursor().execute('SELECT * FROM playlist').fetchall()
        playlists = []
        for result in results:
            playlists.append(Playlist(result[0], result[1], result[2], result[3]))
        return playlists

    def get_by_id(self, id_):
        result = self.db.cursor().execute('SELECT * FROM playlist WHERE id=?', (id_,)).fetchone()
        return Playlist(result[0], result[1], result[2], result[3])

    def get_by_guild(self, guild):
        # Get list of all playlists in a guild
        cursor = self.db.cursor()
        values = (guild.id,)
        cursor.execute('SELECT * FROM playlist WHERE guild_id=?', values)
        results = cursor.fetchall()

        playlists = []
        for result in results:
            playlists.append(Playlist(result[0], result[1], result[2], result[3]))
        return playlists

    def get_by_guild_and_name(self, guild, name):
        # Get playlist by guild and playlist name
        cursor = self.db.cursor()
        values = (guild.id, name)
        cursor.execute('SELECT * FROM playlist WHERE guild_id=? AND name=?', values)
        results = cursor.fetchall()

        playlists = []
        for result in results:
            playlists.append(Playlist(result[0], result[1], result[2], result[3]))
        return playlists

    def add(self, playlist):
        cursor = self.db.cursor()
        values = (str(playlist.id), playlist.name, playlist.guild_id, playlist.description)
        cursor.execute('INSERT INTO playlist VALUES (?, ?, ?, ?)', values)
        self.db.commit()

    def update(self, playlist):
        cursor = self.db.cursor()
        values = (playlist.guild_id, playlist.name, playlist.description, playlist.id)
        cursor.execute('UPDATE playlist SET guild_id=?, name=?, description=? WHERE id=?', values)
        self.db.commit()

    def remove(self, playlist):
        cursor = self.db.cursor()
        values = (playlist.id,)
        cursor.execute('DELETE FROM playlist WHERE id=?', values)
        self.db.commit()


class PlaylistSong:
    def __init__(self, id_, playlist_id, title, artist, duration, url, previous_id):
        self._id: uuid.UUID = id_
        self._playlist_id = playlist_id
        self._title = title
        self._artist = artist
        self._url = url
        self._duration = duration
        self._previous_id = previous_id

    @classmethod
    def create_new(cls, playlist_id, title, artist, duration, url, previous_id):
        return cls(uuid.uuid4(), playlist_id, title, artist, duration, url, previous_id)

    @property
    def id(self) -> uuid.UUID:
        return self._id

    @property
    def playlist_id(self) -> uuid.UUID:
        return self._playlist_id

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
        cursor.execute('CREATE TABLE IF NOT EXISTS playlist_songs (id TEXT PRIMARY KEY, playlist_id TEXT, title TEXT, '
                       'artist TEXT, duration INTEGER, url TEXT, previous_id INTEGER, '
                       'FOREIGN KEY(playlist_id) REFERENCES playlist(id))')
        self.db.commit()

    def get_by_id(self, id_):
        result = self.db.cursor().execute('SELECT * FROM playlist_songs WHERE id=?', (id_,)).fetchone()
        return self._result_to_playlist_song(result)

    def get_by_playlist(self, playlist):
        # Get list of all songs in playlist
        cursor = self.db.cursor()
        cursor.execute('SELECT * FROM playlist_songs WHERE playlist_id=?', (playlist.id,))
        results = cursor.fetchall()

        songs = []
        for result in results:
            songs.append(self._result_to_playlist_song(result))
        return songs

    def add(self, playlist_song: PlaylistSong):
        cursor = self.db.cursor()
        values = (str(playlist_song.id), str(playlist_song.playlist_id), playlist_song.title, playlist_song.artist,
                  playlist_song.duration, playlist_song.url, str(playlist_song.previous_id))
        cursor.execute('INSERT INTO playlist_songs VALUES (?, ?, ?, ?, ?, ?, ?)', values)
        self.db.commit()

    def update(self, playlist_song: PlaylistSong):
        cursor = self.db.cursor()
        values = (str(playlist_song.playlist_id), playlist_song.title, playlist_song.artist, playlist_song.duration,
                  playlist_song.url, str(playlist_song.previous_id), str(playlist_song.id))
        cursor.execute('UPDATE playlist_songs SET playlist_id=?, title=?, '
                       'artist=?, duration=?, url=?, previous_id=? WHERE id=?', values)
        self.db.commit()

    def remove(self, playlist):
        cursor = self.db.cursor()
        values = (playlist.id,)
        cursor.execute('DELETE FROM playlist_songs WHERE id=?', values)
        self.db.commit()

    @staticmethod
    def _result_to_playlist_song(result):
        return PlaylistSong(uuid.UUID(result[0]), uuid.UUID(result[1]), result[2], result[3],
                            result[4], result[5], uuid.UUID(result[6])) if result else None


class Song(ABC):
    @property
    @abstractmethod
    def stream(self) -> Any:
        pass

    @property
    @abstractmethod
    def title(self) -> str:
        pass

    @property
    @abstractmethod
    def artist(self) -> Optional[str]:
        pass

    @property
    @abstractmethod
    def duration(self) -> int:
        pass

    @property
    @abstractmethod
    def url(self) -> str:
        pass

    @property
    @abstractmethod
    def group(self) -> str:
        pass

    @property
    @abstractmethod
    def group_url(self) -> str:
        pass

    @property
    @abstractmethod
    def original_source(self) -> str:
        pass


class WavelinkSong(Song):
    def __init__(self, track, original_source, url, group=None, group_url=None,
                 title=None, artist=None, duration=None):
        self._track: wavelink.Track = track
        self._original_source: OriginalSource = original_source
        self._url: str = url
        self._playlist: str = group
        self._playlist_url: str = group_url
        self._title = title
        self._artist = artist
        self._duration = duration

    @property
    def stream(self) -> wavelink.Track:
        return self._track

    @property
    def title(self) -> str:
        return self._title if self._title else self._track.title

    @property
    def artist(self) -> Optional[str]:
        return self._artist if self._artist else self._track.author

    @property
    def duration(self) -> int:
        return self._duration if self._duration else int(self._track.duration)

    @property
    def url(self) -> str:
        return self._url

    @property
    def group(self) -> Optional[str]:
        return self._playlist

    @property
    def group_url(self):
        return self._playlist_url

    @property
    def original_source(self) -> OriginalSource:
        return self._original_source

    @classmethod
    async def from_local(cls, playlist_song: PlaylistSong) -> list['WavelinkSong']:
        # noinspection PyTypeChecker
        track = wavelink.PartialTrack(query=f'{playlist_song.title} - {playlist_song.artist}', cls=YouTubeMusicTrack)
        return [cls(track, OriginalSource.LOCAL, playlist_song.url, title=playlist_song.title,
                    artist=playlist_song.artist, duration=playlist_song.duration)]

    @classmethod
    async def from_query(cls, query) -> list['WavelinkSong']:
        found_tracks = await wavelink.YouTubeMusicTrack.search(query=query)
        return [cls(track, OriginalSource.YOUTUBE_SONG, track.uri) for track in found_tracks]

    @classmethod
    async def from_youtube(cls, url) -> ['WavelinkSong']:
        found_tracks = await wavelink.YouTubeTrack.search(query=url)
        return [cls(track, OriginalSource.YOUTUBE_VIDEO, track.uri) for track in found_tracks]

    @classmethod
    async def from_youtube_playlist(cls, url) -> list['WavelinkSong']:
        found_playlist = await wavelink.YouTubePlaylist.search(query=url)
        original_source = OriginalSource.YOUTUBE_PLAYLIST
        name = found_playlist.name
        if "Album -" in found_playlist.name:
            original_source = OriginalSource.YOUTUBE_ALBUM
            name = name[8:]
        return [cls(track, original_source, track.uri, name, url)
                for track in found_playlist.tracks]

    @classmethod
    async def from_spotify(cls, url) -> list['WavelinkSong']:
        found_tracks = await SpotifyTrack.search(query=url)
        return [cls(track, OriginalSource.SPOTIFY_SONG, track.url) for track in found_tracks]

    @classmethod
    async def from_spotify_playlist(cls, url) -> list['WavelinkSong']:
        found_playlist = await SpotifyPlaylist.search(query=url)
        return [cls(track, OriginalSource.SPOTIFY_PLAYLIST, track.url, found_playlist.name, found_playlist.url)
                for track in found_playlist.tracks]

    @classmethod
    async def from_spotify_album(cls, url) -> list['WavelinkSong']:
        found_album = await SpotifyAlbum.search(query=url)
        return [cls(track, OriginalSource.SPOTIFY_ALBUM, track.url, found_album.name, found_album.url)
                for track in found_album.tracks]


T_Song = TypeVar("T_Song", bound=Song)


class MusicPlayer(ABC, Generic[T_Song]):
    @property
    @abstractmethod
    def is_looping(self) -> bool:
        pass

    @is_looping.setter
    @abstractmethod
    def is_looping(self, value):
        pass

    @property
    @abstractmethod
    def playing(self) -> T_Song:
        pass

    @property
    @abstractmethod
    def seek_position(self) -> int:
        pass

    @property
    @abstractmethod
    def next_queue(self) -> list[T_Song]:
        pass

    @property
    @abstractmethod
    def previous_queue(self) -> list[T_Song]:
        pass

    @abstractmethod
    async def connect(self, channel):
        pass

    @abstractmethod
    async def disconnect(self):
        pass

    @abstractmethod
    async def play(self, song: T_Song):
        pass

    @abstractmethod
    async def play_multiple(self, songs: list[T_Song]):
        pass

    @abstractmethod
    async def add(self, song: T_Song, index=0):
        pass

    @abstractmethod
    async def add_multiple(self, songs: list[T_Song], index=0):
        pass

    @abstractmethod
    async def remove(self, index=0):
        pass

    @abstractmethod
    async def clear(self):
        pass

    @abstractmethod
    async def seek(self, position):
        pass

    @abstractmethod
    async def next(self):
        pass

    @abstractmethod
    async def previous(self):
        pass

    @abstractmethod
    async def pause(self):
        pass

    @abstractmethod
    async def resume(self):
        pass

    @abstractmethod
    async def loop(self):
        pass

    @abstractmethod
    async def unloop(self):
        pass

    @abstractmethod
    async def move(self, first_index, second_index):
        pass

    @abstractmethod
    async def shuffle(self):
        pass

    @abstractmethod
    async def stop(self):
        pass

    @abstractmethod
    async def process_song_end(self):
        pass

    @abstractmethod
    async def enable_auto_disconnect(self):
        pass

    @abstractmethod
    async def disable_auto_disconnect(self):
        pass


class WavelinkMusicPlayer(MusicPlayer[WavelinkSong]):
    def __init__(self):
        self._player: Optional[wavelink.Player] = None
        self._current: Optional[WavelinkSong] = None
        self._next_queue: deque[WavelinkSong] = deque()
        self._previous_queue: deque[WavelinkSong] = deque()
        self._is_looping = False
        self._skip_toggle = False
        self._disconnect_time = time() + self._get_disconnect_time_limit()
        self._disconnect_timer.start()

    @property
    def is_looping(self) -> bool:
        return self._is_looping

    @is_looping.setter
    def is_looping(self, value):
        self._is_looping = value

    @property
    def playing(self) -> WavelinkSong:
        return self._current

    @property
    def seek_position(self) -> int:
        return int(self._player.position)

    @property
    def next_queue(self) -> list[WavelinkSong]:
        return list(self._next_queue)

    @property
    def previous_queue(self) -> list[WavelinkSong]:
        return list(self._previous_queue)

    async def connect(self, channel: discord.VoiceChannel):
        # noinspection PyTypeChecker
        # Incorrectly warns this line
        self._player = await channel.connect(cls=wavelink.Player, self_deaf=True)

    async def disconnect(self):
        await self._player.disconnect()

    async def play(self, audio_source: WavelinkSong) -> None:
        self._refresh_disconnect_timer()
        await self._player.play(audio_source.stream)

    async def play_multiple(self, songs: list[WavelinkSong]):
        self._refresh_disconnect_timer()
        await self._player.play(songs[0].stream)
        for song in songs[1:]:
            self._next_queue.appendleft(song)

    async def add(self, audio_source: WavelinkSong, index=-1) -> PlayerResult:
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

    async def add_multiple(self, audio_sources: list[WavelinkSong], index=-1):
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

    async def remove(self, index=-1):
        if index >= 0:
            del self._next_queue[index]
            return
        self._next_queue.pop()

    async def clear(self):
        self._next_queue.clear()
        self._previous_queue.clear()

    async def seek(self, position):
        await self._player.seek(position)

    async def pause(self):
        await self._player.pause()

    async def resume(self):
        await self._player.resume()

    async def loop(self):
        self._is_looping = True

    async def unloop(self):
        self._is_looping = False

    async def move(self, first_index, second_index):
        song = self._next_queue[first_index]
        await self.remove(first_index)
        await self.add(song, second_index)

    async def shuffle(self):
        random.shuffle(self._next_queue)

    async def stop(self):
        self._skip_toggle = True
        await self._player.stop()

    async def next(self):
        self._refresh_disconnect_timer()
        next_song = None
        try:
            next_song = self._next_queue.popleft()
            await self._player.play(next_song.stream)
        except IndexError:
            pass
        self._previous_queue.append(self._current)
        self._current = next_song

    async def previous(self):
        previous_song = self._previous_queue.pop()
        await self._player.play(previous_song.stream)
        self._next_queue.appendleft(self._current)
        self._current = previous_song

    async def process_song_end(self):
        self._refresh_disconnect_timer()
        if self._is_looping and not self._skip_toggle:
            await self.play(self._current)
            return
        self._skip_toggle = False
        await self.next()

    async def enable_auto_disconnect(self):
        self._disconnect_timer.start()

    async def disable_auto_disconnect(self):
        self._disconnect_timer.stop()

    @tasks.loop(seconds=30)
    async def _disconnect_timer(self):
        if self._is_auto_disconnect() and time() > self._disconnect_time and not self._player.is_playing():
            await self.disconnect()

    def _refresh_disconnect_timer(self):
        self._disconnect_time = time() + self._get_disconnect_time_limit()

    @staticmethod
    def _get_disconnect_time_limit():
        config = toml.load(constants.DATA_DIR + 'config.toml')
        return config['music']['disconnect_time']

    @staticmethod
    def _is_auto_disconnect():
        config = toml.load(constants.DATA_DIR + 'config.toml')
        return config['music']['auto_disconnect']


class Musicbox(commands.Cog):
    """Stream your favourite beats right to your local VC"""
    NOT_CONNECTED_EMBED = discord.Embed(
        colour=constants.EmbedStatus.FAIL.value,
        description="I need to be in a voice channel to execute music "
                    "commands. \nUse **/join** or **/play** to connect me to a channel")

    def __init__(self, bot):
        self.bot = bot
        self.music_players: dict[int, MusicPlayer] = {}
        self.database = sqlite3.connect(constants.DATA_DIR + "spacecat.db")
        self.playlists = PlaylistRepository(self.database)
        self.playlist_songs = PlaylistSongRepository(self.database)

    async def cog_load(self):
        await self.init_config()
        await self.init_wavelink()

    @staticmethod
    async def init_config():
        config = toml.load(constants.DATA_DIR + 'config.toml')
        if 'lavalink' not in config:
            config['lavalink'] = {}
        if 'address' not in config['lavalink']:
            config['lavalink']['address'] = "0.0.0.0"
        if 'port' not in config['lavalink']:
            config['lavalink']['port'] = "2333"
        if 'password' not in config['lavalink']:
            config['lavalink']['password'] = "password1"

        if 'spotify' not in config:
            config['spotify'] = {}
        if 'client_id' not in config['spotify']:
            config['spotify']['client_id'] = ""
        if 'client_secret' not in config['spotify']:
            config['spotify']['client_secret'] = ""
        with open(constants.DATA_DIR + 'config.toml', 'w') as config_file:
            toml.dump(config, config_file)

    async def init_wavelink(self):
        config = toml.load(constants.DATA_DIR + 'config.toml')
        await wavelink.NodePool.create_node(
            bot=self.bot, host=config['lavalink']['address'],
            port=config['lavalink']['port'], password=config['lavalink']['password'],
            spotify_client=spotify.SpotifyClient(client_id=config['spotify']['client_id'],
                                                 client_secret=config['spotify']['client_secret']))

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

    @commands.Cog.listener()
    async def on_wavelink_track_end(self, player: wavelink.Player, track, reason):
        _ = track, reason  # Disable warning for unused arguments
        music_player = await self._get_music_player(player.channel)
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
        """Plays from a url (almost anything youtube_dl supports)"""
        # Join channel and create music player instance if it doesn't exist
        music_player = await self._get_music_player(interaction.user.voice.channel)

        if position > len(music_player.next_queue) or position < 1:
            position = len(music_player.next_queue) + 1

        # Defer response due to long processing times when provided a large playlist
        await interaction.response.defer()

        try:
            songs = await self._get_songs(url)
        except SongUnavailableError:
            embed = discord.Embed(
                colour=constants.EmbedStatus.FAIL.value,
                description="That song is unavailable. Maybe the link is invalid?")
            await interaction.followup.send(embed=embed)
            return

        # Add YouTube playlist
        if songs[0].original_source == OriginalSource.YOUTUBE_PLAYLIST \
                or songs[0].original_source == OriginalSource.SPOTIFY_PLAYLIST:
            result = await music_player.add_multiple(songs, position-1)
            if result == PlayerResult.PLAYING:
                embed = discord.Embed(
                    colour=constants.EmbedStatus.YES.value,
                    description=f"Now playing playlist {songs[0].group}")
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

        # Add YouTube album
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
        songs = await self._get_songs(search)
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
        if not interaction.guild.voice_client.is_paused():
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
        if interaction.guild.voice_client.is_paused():
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
                description="There's nothing in the queue after this"))
            return

        # Stop current song and flag that it has been skipped
        await music_player.stop()
        await interaction.response.send_message(embed=discord.Embed(
            colour=constants.EmbedStatus.YES.value,
            description="Song has been skipped."))

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
                colour=constants.EmbedStatus.NO.value,
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
                colour=constants.EmbedStatus.NO.value,
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

        # Output first in queue as currently playing
        embed = discord.Embed(
            colour=constants.EmbedStatus.INFO.value,
            title=f"{constants.EmbedIcon.MUSIC} Music Queue")
        duration = await self._format_duration(playing.duration)
        current_time = await self._format_duration(music_player.seek_position)

        # Set header depending on if looping or not, and whether to add a spacer
        if music_player.is_looping:
            header = "Currently Playing (Looping)"
        else:
            header = "Currently Playing"
        if len(queue) >= 1:
            spacer = "\u200B"
        else:
            spacer = ""
        artist = ""
        if playing.artist:
            artist = f"{playing.artist} - "
        embed.add_field(
            name=header,
            value=f"[{artist}{playing.title}]({playing.url}) "
                  f"`{current_time}/{duration}` \n{spacer}")

        # List remaining songs in queue plus total duration
        if len(queue) >= 1:
            queue_info = []

            # Modify page variable to get every ten results
            page -= 1
            if page > 0:
                page = page * 5

            total_duration = 0
            for song in queue:
                total_duration += song.duration

            for index, song in enumerate(
                    islice(queue, page, page + 5)):
                duration = await self._format_duration(song.duration)
                artist = ""
                if song.artist:
                    artist = f"{song.artist} - "
                queue_info.append(f"{page + index + 1}. [{artist}{song.title}]({song.url}) `{duration}`")

            # Alert if no songs are on the specified page
            if page > 0 and not queue_info:
                embed = discord.Embed(
                    colour=constants.EmbedStatus.FAIL.value,
                    description="There are no songs on that page")
                await interaction.response.send_message(embed=embed)
                return

            # Omit songs past 10 and just display amount instead
            if len(queue) > page + 6:
                queue_info.append(
                    f"`+{len(queue) - 6 - page} more in queue`")

            # Output results to chat
            duration = await self._format_duration(total_duration)
            queue_output = '\n'.join(queue_info)
            embed.add_field(
                name=f"Queue  `{duration}`",
                value=queue_output, inline=False)
        await interaction.response.send_message(embed=embed)

    @queue_group.command(name="move")
    @perms.check()
    async def queue_move(self, interaction, original_pos: int, new_pos: int):
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
            colour=constants.EmbedStatus.NO.value,
            description="All songs have been removed from the queue")
        await interaction.response.send_message(embed=embed)

    @playlist_group.command(name='create')
    @perms.check()
    async def playlist_create(self, interaction, playlist_name: str):
        """Create a new playlist"""
        # Limit playlist name to 30 chars
        if len(playlist_name) > 30:
            embed = discord.Embed(
                colour=constants.EmbedStatus.FAIL.value,
                description="Playlist name is too long")
            await interaction.response.send_message(embed=embed)
            return

        # Alert if playlist with specified name already exists
        if self.playlists.get_by_guild_and_name(interaction.guild, playlist_name):
            embed = discord.Embed(
                colour=constants.EmbedStatus.FAIL.value,
                description=f"Playlist `{playlist_name}` already exists")
            await interaction.response.send_message(embed=embed)
            return

        # Add playlist to database
        self.playlists.add(Playlist.create_new(playlist_name, interaction.guild))
        embed = discord.Embed(
            colour=constants.EmbedStatus.NO.value,
            description=f"Playlist `{playlist_name}` has been created")
        await interaction.response.send_message(embed=embed)

    @playlist_group.command(name='destroy')
    @perms.check()
    async def playlist_destroy(self, interaction, playlist_name: str):
        """Deletes an existing playlist"""
        # Alert if playlist doesn't exist in db
        playlist = self.playlists.get_by_guild_and_name(interaction.guild, playlist_name)[0]
        if not playlist:
            embed = discord.Embed(
                colour=constants.EmbedStatus.FAIL.value,
                description=f"Playlist `{playlist_name}` doesn't exist")
            await interaction.response.send_message(embed=embed)
            return

        # Remove playlist from database and all songs linked to it
        self.playlists.remove(playlist)
        playlist_songs = self.playlist_songs.get_by_playlist(playlist)
        for song in playlist_songs:
            self.playlist_songs.remove(song)
        embed = discord.Embed(
            colour=constants.EmbedStatus.NO.value,
            description=f"Playlist `{playlist_name}` has been destroyed")
        await interaction.response.send_message(embed=embed)

    @playlist_group.command(name='description')
    @perms.check()
    async def playlist_description(self, interaction, playlist_name: str, description: str):
        """Sets the description for the playlist"""
        # Alert if playlist doesn't exist
        playlist = self.playlists.get_by_guild_and_name(interaction.guild, playlist_name)[0]
        if playlist:
            embed = discord.Embed(
                colour=constants.EmbedStatus.FAIL.value,
                description=f"Playlist `{playlist_name}` doesn't exist")
            await interaction.response.send_message(embed=embed)
            return

        # Limit playlist description to 300 chars
        if len(description) > 300:
            embed = discord.Embed(
                colour=constants.EmbedStatus.FAIL.value,
                description="Description is too long")
            await interaction.response.send_message(embed=embed)
            return

        # Update playlist description
        playlist.description = description
        self.playlists.update(playlist)
        embed = discord.Embed(
            colour=constants.EmbedStatus.YES.value,
            description=f"Description set for playlist `{playlist_name}`")
        await interaction.response.send_message(embed=embed)

    @playlist_group.command(name='rename')
    @perms.check()
    async def playlist_rename(self, interaction, playlist_name: str, new_name: str):
        """Rename an existing playlist"""
        # Get the playlist
        playlist = self.playlists.get_by_guild_and_name(interaction.guild, playlist_name)[0]
        if playlist:
            embed = discord.Embed(
                colour=constants.EmbedStatus.FAIL.value,
                description=f"Playlist `{playlist_name}` doesn't exist")
            await interaction.response.send_message(embed=embed)
            return

        # Update playlist name
        playlist.name = new_name
        self.playlists.update(playlist)
        embed = discord.Embed(
            colour=constants.EmbedStatus.YES.value,
            description=f"Playlist `{playlist}` has been renamed to `{new_name}`")
        await interaction.response.send_message(embed=embed)

    @playlist_group.command(name='list')
    @perms.check()
    async def playlist_list(self, interaction):
        """List all available playlists"""
        # Get playlist from repo
        playlists = self.playlists.get_by_guild(interaction.guild)
        if not playlists:
            embed = discord.Embed(
                colour=constants.EmbedStatus.FAIL.value,
                description="There are no playlists available")
            await interaction.response.send_message(embed=embed)
            return

        # Get all playlist names and duration
        playlist_names = []
        for playlist in playlists:
            songs = self.playlist_songs.get_by_playlist(playlist)
            song_duration = 0
            for song in songs:
                song_duration += song.duration
            playlist_names.append([playlist.name, song_duration])

        # Format playlist songs into pretty list
        playlist_info = []
        for index, playlist_name in enumerate(islice(playlist_names, 0, 10)):
            duration = await self._format_duration(playlist_name[1])
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
        await interaction.response.send_message(embed=embed)

    @playlist_group.command(name='add')
    @perms.check()
    async def playlist_add(self, interaction, playlist_name: str, url: str):
        """Adds a song to a playlist"""
        # Get playlist from repo
        playlist = self.playlists.get_by_guild_and_name(interaction.guild, playlist_name)[0]
        if not playlist:
            embed = discord.Embed(
                colour=constants.EmbedStatus.FAIL.value,
                description="There are no playlists available")
            await interaction.response.send_message(embed=embed)
            return

        playlist_songs = self.playlist_songs.get_by_playlist(playlist)
        if len(playlist_songs) > 100:
            embed = discord.Embed(
                colour=constants.EmbedStatus.FAIL.value,
                description="There's too many songs in the playlist. Remove"
                            "some songs to be able to add more")
            await interaction.response.send_message(embed=embed)
            return

        # Get song source to add to song list
        try:
            songs = await self._get_songs(url)
        except SongUnavailableError:
            embed = discord.Embed(
                colour=constants.EmbedStatus.FAIL.value,
                description="That song is unavailable. Maybe the link is invalid?")
            await interaction.response.send_message(embed=embed)
            return

        # Set previous song as the last song in the playlist
        if not playlist_songs:
            previous_song = uuid.UUID(int=0)
        else:
            song_ids = []
            previous_ids = []
            for playlist_song in playlist_songs:
                song_ids.append(playlist_song.id)
                previous_ids.append(playlist_song.previous_id)
            previous_song = list(set(song_ids) - set(previous_ids))[0]

        # Add song to playlist
        self.playlist_songs.add(PlaylistSong.create_new(
            playlist.id, songs[0].title, songs[0].artist, songs[0].duration, songs[0].url, previous_song))
        duration = await self._format_duration(songs[0].duration)
        embed = discord.Embed(
            colour=constants.EmbedStatus.YES.value,
            description=f"Added [{songs[0].title}]({songs[0].url}) "
                        f"`{duration}` to position #{len(songs) + 1} "
                        f"in playlist `{playlist_name}`")
        await interaction.response.send_message(embed=embed)

    @playlist_group.command(name='remove')
    @perms.check()
    async def playlist_remove(self, interaction, playlist_name: str, index: int):
        """Removes a song from a playlist"""
        # Get playlist from repo
        playlist = self.playlists.get_by_guild_and_name(interaction.guild, playlist_name)[0]
        if not playlist:
            embed = discord.Embed(
                colour=constants.EmbedStatus.FAIL.value,
                description=f"Playlist `{playlist_name}` doesn't exist")
            await interaction.response.send_message(embed=embed)
            return

        # Fetch selected song and the song after
        songs: list[PlaylistSong] = await self._order_playlist_songs(self.playlist_songs.get_by_playlist(playlist))
        selected_song = songs[int(index) - 1]

        # Edit next song's previous song id if it exists
        try:
            next_song = songs[int(index)]
            next_song.previous_id = selected_song.previous_id
            self.playlist_songs.update(next_song)
        except IndexError:
            pass

        # Remove selected song from playlist
        self.playlist_songs.remove(selected_song)
        duration = await self._format_duration(selected_song.duration)
        embed = discord.Embed(
            colour=constants.EmbedStatus.NO.value,
            description=f"[{selected_song.title}]({selected_song.url}) "
                        f"`{duration}` has been removed from `{playlist_name}`")
        await interaction.response.send_message(embed=embed)

    @playlist_group.command(name='move')
    @perms.check()
    async def playlist_move(self, interaction, playlist_name: str, original_pos: int, new_pos: int):
        """Moves a song to a specified position in a playlist"""
        # Get playlist from repo
        playlist = self.playlists.get_by_guild_and_name(interaction.guild, playlist_name)[0]
        if not playlist:
            embed = discord.Embed(
                colour=constants.EmbedStatus.FAIL.value,
                description=f"Playlist `{playlist_name}` doesn't exist")
            await interaction.response.send_message(embed=embed)
            return

        # Edit db to put selected song in other song's position
        songs = self.playlist_songs.get_by_playlist(playlist)
        selected_song = songs[int(original_pos) - 1]
        other_song = songs[int(new_pos) - 1]

        # If moving down, shift other song down the list
        if new_pos > original_pos:
            values = [(other_song.id, selected_song.id)]
            try:
                after_new_song = songs[int(new_pos)]
                values.append((selected_song.id, after_new_song.id))
            except IndexError:
                pass
        # If moving up, shift other song up the list
        else:
            values = [
                (other_song.previous_id, selected_song.id),
                (selected_song.id, other_song.id)]

        # Connect the two songs beside the original song position
        try:
            after_selected_song = songs[int(original_pos)]
            values.append((selected_song.previous_id, after_selected_song.id))
        except IndexError:
            pass

        # Execute all those values
        db = sqlite3.connect(constants.DATA_DIR + 'spacecat.db')
        cursor = db.cursor()
        for value in values:
            cursor.execute('UPDATE playlist_songs SET previous_song=? WHERE id=?', value)
        db.commit()

        # Output result to chat
        duration = await self._format_duration(selected_song.duration)
        embed = discord.Embed(
            colour=constants.EmbedStatus.YES.value,
            description=f"[{selected_song.title}]({selected_song.url}) "
                        f"`{duration}` has been moved to position #{new_pos} "
                        f"in playlist `{playlist_name}`")
        await interaction.response.send_message(embed=embed)

    @playlist_group.command(name='view')
    @perms.check()
    async def playlist_view(self, interaction, playlist_name: str, page: int = 1):
        """List all songs in a playlist"""
        # Fetch songs from playlist if it exists
        playlist = self.playlists.get_by_guild_and_name(interaction.guild, playlist_name)[0]
        if not playlist:
            embed = discord.Embed(
                colour=constants.EmbedStatus.FAIL.value,
                description=f"Playlist `{playlist_name}` does not exist")
            await interaction.response.send_message(embed=embed)
            return

        songs = self.playlist_songs.get_by_playlist(playlist)

        # Modify page variable to get every ten results
        page -= 1
        if page > 0:
            page = page * 10

        # Get total duration
        total_duration = 0
        for song in songs:
            total_duration += song.duration

        # Make a formatted list of 10 songs on the page
        formatted_songs = []
        for index, song in enumerate(islice(songs, page, page + 10)):
            # Cut off song name to 90 chars
            if len(song.title) > 90:
                song_name = f"{song.title[:87]}..."
            else:
                song_name = song.title

            duration = await self._format_duration(song.duration)
            formatted_songs.append(f"{page + index + 1}. [{song_name}]({song.url}) `{duration}`")

        # Alert if no songs are on the specified page
        if not formatted_songs:
            embed = discord.Embed(
                colour=constants.EmbedStatus.FAIL.value,
                description="There are no songs on that page")
            await interaction.response.send_message(embed=embed)
            return

        # Output results to chat
        embed = discord.Embed(
            colour=constants.EmbedStatus.INFO.value,
            title=f"{constants.EmbedIcon.MUSIC} Playlist '{playlist_name}' Songs")
        if playlist.description and page == 0:
            embed.description = playlist.description
        formatted_duration = await self._format_duration(total_duration)
        playlist_songs_output = '\n'.join(formatted_songs)
        embed.add_field(
            name=f"{len(songs)} songs available `{formatted_duration}`",
            value=playlist_songs_output, inline=False)
        await interaction.response.send_message(embed=embed)

    @playlist_group.command(name='play')
    @perms.check()
    async def playlist_play(self, interaction: discord.Interaction, playlist_name: str):
        """Play from a locally saved playlist"""
        # Get music player
        music_player = await self._get_music_player(interaction.user.voice.channel)

        # Fetch songs from playlist if it exists
        playlist = self.playlists.get_by_guild_and_name(interaction.guild, playlist_name)[0]
        if not playlist:
            embed = discord.Embed(
                colour=constants.EmbedStatus.FAIL.value,
                description=f"Playlist `{playlist_name}` does not exist")
            await interaction.response.send_message(embed=embed)
            return

        songs = self.playlist_songs.get_by_playlist(playlist)
        if not songs:
            embed = discord.Embed(
                colour=constants.EmbedStatus.FAIL.value,
                description=f"Playlist `{playlist.name}` does not contain any songs")
            await interaction.response.send_message(embed=embed)
            return

        stream = await self._get_song_from_saved(songs[0])
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
            stream = await self._get_song_from_saved(songs[i])
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

    async def _get_music_player(self, channel: discord.VoiceChannel):
        try:
            music_player = self.music_players[channel.guild.id]
        except KeyError:
            music_player = WavelinkMusicPlayer()
            await music_player.connect(channel)
            self.music_players[channel.guild.id] = music_player
        return music_player

    @staticmethod
    async def _get_songs(query: str):
        if "youtube.com" in query and "list" in query:
            return await WavelinkSong.from_youtube_playlist(query)
        elif "youtube.com" in query:
            return await WavelinkSong.from_youtube(query)
        elif "spotify.com" in query and "playlist" in query:
            return await WavelinkSong.from_spotify_playlist(query)
        elif "spotify.com" in query and "album" in query:
            return await WavelinkSong.from_spotify_album(query)
        elif "spotify.com" in query:
            return await WavelinkSong.from_spotify(query)
        return await WavelinkSong.from_query(query)

    @staticmethod
    async def _get_song_from_saved(playlist_song: PlaylistSong):
        return await WavelinkSong.from_local(playlist_song)

    # Format duration based on what values there are
    @staticmethod
    async def _format_duration(seconds):
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
            formatted += "0:"

        if seconds:
            if seconds < 10:
                formatted += f"0{seconds}"
            else:
                formatted += f"{seconds}"
        return formatted

    @staticmethod
    async def _order_playlist_songs(playlist_songs):
        """Gets playlist songs from name"""
        # Use dictionary to pair songs with the next song
        song_links = {}
        for song in playlist_songs:
            song_links[song.previous_id] = song

        # Order playlist songs into list
        ordered_songs = []
        next_song = song_links.get(None)
        while next_song is not None:
            ordered_songs.append(next_song)
            next_song = song_links.get(next_song.id)

        return ordered_songs

    @staticmethod
    def _parse_time(time_string):
        time_split = time_string.split(':')
        hours, minutes, seconds = 0, 0, 0
        if len(time_split) >= 3:
            hours = time_split[-3]
        if len(time_split) >= 2:
            minutes = time_split[-2]
        if len(time_split) >= 1:
            minutes = time_split[-1]
        return int(hours) * 3600000 + int(minutes) * 60000 + int(seconds) * 1000


async def setup(bot):
    await bot.add_cog(Musicbox(bot))
