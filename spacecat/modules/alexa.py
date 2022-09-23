from abc import ABC, abstractmethod
import asyncio
import random
import sqlite3
from collections import deque
from itertools import islice
from time import gmtime, strftime, time
from typing import Optional, Any, Generic, TypeVar

from bs4 import BeautifulSoup as bs

import discord
from discord import app_commands
from discord.ext import commands, tasks

from enum import Enum

import requests

import toml

import uuid

import wavelink

import yt_dlp

from spacecat.helpers import constants
from spacecat.helpers import perms
from spacecat.helpers import reaction_buttons

yt_dlp.utils.bug_reports_message = lambda: ''


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

ytdl = yt_dlp.YoutubeDL(ytdl_format_options)


class PlayerResult(Enum):
    PLAYING = 0
    QUEUEING = 1


class AudioSource(ABC):
    @abstractmethod
    def get_stream(self) -> Any:
        pass

    @abstractmethod
    def get_title(self) -> str:
        pass

    @abstractmethod
    def get_duration(self) -> int:
        pass

    @abstractmethod
    def get_playlist(self) -> str:
        pass

    @abstractmethod
    async def get_url(self) -> str:
        pass


class WavelinkAudioSource(AudioSource):
    def __init__(self, track, playlist=None):
        self.track: wavelink.Track = track
        self.playlist: str = playlist

    def get_stream(self) -> wavelink.Track:
        return self.track

    def get_title(self) -> str:
        return self.track.title

    def get_duration(self) -> int:
        return int(self.track.duration)

    def get_playlist(self) -> Optional[str]:
        return self.playlist

    def get_url(self) -> str:
        return self.track.uri

    @classmethod
    async def from_query(cls, query) -> list['WavelinkAudioSource']:
        try:
            found_tracks = await wavelink.YouTubeTrack.search(query=query)
        except IndexError:
            raise VideoUnavailableError

        # The wavelink search method returns an unlisted type of "YouTubePlaylist". Bad practice, but we can use this
        # to our advantage to check if a track is a playlist
        if isinstance(found_tracks, wavelink.YouTubePlaylist):
            return [cls(track, found_tracks.name) for track in found_tracks.tracks]
        return [cls(found_tracks[0])]


class YTDLStream:
    def __init__(self, title, duration, webpage_url, playlist=None):
        self.title = title
        self.duration = duration
        self.webpage_url = webpage_url
        self.playlist = playlist

    async def create_stream(self):
        before_args = "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5"
        loop = asyncio.get_event_loop()
        metadata = await loop.run_in_executor(None, lambda: ytdl.extract_info(self.webpage_url, download=False))
        return discord.PCMVolumeTransformer(
            discord.FFmpegPCMAudio(metadata['url'], **ffmpeg_options, before_options=before_args), 0.5)

    @classmethod
    async def from_metadata(cls, metadata):
        return cls(metadata.get('title'), metadata.get('duration'),
                   metadata.get('webpage_url'), metadata.get('playlist'))

    @classmethod
    async def from_url(cls, webpage_url):
        loop = asyncio.get_event_loop()
        metadata = await loop.run_in_executor(None, lambda: ytdl.extract_info(webpage_url, download=False))
        songs = []
        try:
            if 'entries' in metadata:
                for entry in metadata['entries']:
                    try:
                        songs.append(await YTDLStream.from_metadata(entry))
                    except AttributeError:
                        continue
            else:
                songs.append(await YTDLStream.from_metadata(metadata))
        except TypeError:
            return

        return songs


T_AudioSource = TypeVar("T_AudioSource", bound=AudioSource)


class MusicPlayer(ABC, Generic[T_AudioSource]):
    @abstractmethod
    async def is_looping(self) -> bool:
        pass

    @abstractmethod
    async def get_playing(self) -> T_AudioSource:
        pass

    @abstractmethod
    async def get_seek_position(self) -> int:
        pass

    @abstractmethod
    async def get_next_queue(self) -> list[T_AudioSource]:
        pass

    @abstractmethod
    async def get_previous_queue(self) -> list[T_AudioSource]:
        pass

    @abstractmethod
    async def connect(self, channel):
        pass

    @abstractmethod
    async def disconnect(self):
        pass

    @abstractmethod
    async def play(self, song: T_AudioSource):
        pass

    @abstractmethod
    async def play_multiple(self, songs: list[T_AudioSource]):
        pass

    @abstractmethod
    async def add(self, song: T_AudioSource, index=0):
        pass

    @abstractmethod
    async def add_multiple(self, songs: list[T_AudioSource], index=0):
        pass

    @abstractmethod
    async def next(self):
        pass

    @abstractmethod
    async def previous(self):
        pass

    @abstractmethod
    async def remove(self, index=0):
        pass

    @abstractmethod
    async def clear(self):
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
    async def shuffle(self):
        pass

    @abstractmethod
    async def stop(self):
        pass

    @abstractmethod
    async def process_song_end(self):
        pass


class BuiltinMusicPlayer:
    def __init__(self, voice_client):
        self.voice_client = voice_client
        self.song_queue = []
        self.song_start_time = 0
        self.song_pause_time = 0
        self.loop_toggle = False
        self.skip_toggle = False

        config = toml.load(constants.DATA_DIR + 'config.toml')
        self.disconnect_time = time() + config['music']['disconnect_time']
        self._disconnect_timer.start()

    async def play(self, song):
        self.song_queue.insert(0, song)
        self.song_start_time = time()
        stream = await song.create_stream()
        loop = asyncio.get_event_loop()
        self.voice_client.play(stream, after=lambda e: loop.create_task(self.play_next()))

    async def add(self, song):
        self.song_queue.append(song)
        if len(self.song_queue) <= 1:
            stream = await song.create_stream()
            loop = asyncio.get_event_loop()
            self.voice_client.play(stream, after=lambda e: loop.create_task(self.play_next()))
            self.song_start_time = time()
            return PlayerResult.PLAYING
        return PlayerResult.QUEUEING

    async def add_multiple(self, songs):
        self.song_queue.extend(songs)

        if len(self.song_queue) <= len(songs):
            stream = await songs[0].create_stream()
            loop = asyncio.get_event_loop()
            self.voice_client.play(stream, after=lambda e: loop.create_task(self.play_next()))
            self.song_start_time = time()
            return PlayerResult.PLAYING
        return PlayerResult.QUEUEING

    async def play_next(self):
        config = toml.load(constants.DATA_DIR + 'config.toml')
        self.disconnect_time = time() + config['music']['disconnect_time']
        loop = asyncio.get_event_loop()
        # If looping, grab source from url again
        if self.loop_toggle and not self.skip_toggle:
            loop = asyncio.get_event_loop()
            audio_stream = await loop.run_in_executor(None, lambda: self.song_queue[0].create_stream())
            self.song_start_time = time()
            self.voice_client.play(audio_stream, after=lambda e: loop.create_task(self.play_next()))
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
            audio_stream = await self.song_queue[0].create_stream()
            self.voice_client.play(audio_stream, after=lambda e: loop.create_task(self.play_next()))
            return

    async def stop(self):
        self.song_queue.clear()
        self.voice_client.stop()

    @tasks.loop(seconds=30)
    async def _disconnect_timer(self):
        config = toml.load(constants.DATA_DIR + 'config.toml')
        if time() > self.disconnect_time and not self.voice_client.is_playing() and config['music']['auto_disconnect']:
            await self.voice_client.disconnect()


class WavelinkMusicPlayer(MusicPlayer[WavelinkAudioSource]):
    def __init__(self):
        self.player: Optional[wavelink.Player] = None
        self.current: Optional[WavelinkAudioSource] = None
        self.next_queue: deque[WavelinkAudioSource] = deque()
        self.previous_queue: deque[WavelinkAudioSource] = deque()
        self.looping = False
        self.disconnect_time = time() + self._get_disconnect_time_limit()
        self._disconnect_timer.start()

    async def is_looping(self) -> bool:
        return self.looping

    async def get_playing(self) -> WavelinkAudioSource:
        return self.current

    async def get_seek_position(self) -> int:
        return int(self.player.position)

    async def get_next_queue(self) -> list[WavelinkAudioSource]:
        return list(self.next_queue)

    async def get_previous_queue(self) -> list[WavelinkAudioSource]:
        return list(self.previous_queue)

    async def connect(self, channel: discord.VoiceChannel):
        self.player = await channel.connect(cls=wavelink.Player)

    async def disconnect(self):
        await self.player.disconnect()

    async def play(self, audio_source: WavelinkAudioSource) -> None:
        await self.player.play(audio_source.get_stream())

    async def play_multiple(self, songs: list[WavelinkAudioSource]):
        await self.player.play(songs[0].get_stream())
        for song in songs[1:]:
            self.next_queue.appendleft(song)

    async def add(self, audio_source: WavelinkAudioSource, index=0) -> PlayerResult:
        if not self.current:
            await self.player.play(audio_source.get_stream())
            self.current = audio_source
            return PlayerResult.PLAYING
        self.next_queue.append(audio_source)
        return PlayerResult.QUEUEING

    async def add_multiple(self, audio_sources: list[WavelinkAudioSource], index=0):
        if not self.current:
            await self.player.play(audio_sources[0].get_stream())
            self.current = audio_sources[0]
            for audio_source in audio_sources[1:]:
                self.next_queue.append(audio_source)
            return PlayerResult.PLAYING

        for audio_source in audio_sources:
            self.next_queue.append(audio_source)
        return PlayerResult.QUEUEING

    async def remove(self, index=0):
        self.next_queue.pop()

    async def clear(self):
        self.next_queue.clear()
        self.previous_queue.clear()

    async def pause(self):
        await self.player.pause()

    async def resume(self):
        await self.player.resume()

    async def loop(self):
        pass

    async def unloop(self):
        pass

    async def shuffle(self):
        random.shuffle(self.next_queue)

    async def stop(self):
        await self.player.stop()

    async def next(self):
        next_song = None
        try:
            next_song = self.next_queue.popleft()
            await self.player.play(next_song.get_stream())
            self._refresh_disconnect_timer()
        except IndexError:
            pass
        self.previous_queue.append(self.current)
        self.current = next_song

    async def previous(self):
        previous_song = self.previous_queue.pop()
        await self.player.play(previous_song.get_stream())
        self.next_queue.appendleft(self.current)
        self.current = previous_song

    async def process_song_end(self):
        if self.looping:
            await self.play(await self.get_playing())
            return
        await self.next()

    @tasks.loop(seconds=30)
    async def _disconnect_timer(self):
        if self._is_auto_disconnect() and time() > self.disconnect_time and not self.player.is_playing():
            await self.disconnect()

    def _refresh_disconnect_timer(self):
        self.disconnect_time = time() + self._get_disconnect_time_limit()

    @staticmethod
    def _get_disconnect_time_limit():
        config = toml.load(constants.DATA_DIR + 'config.toml')
        return config['music']['disconnect_time']

    @staticmethod
    def _is_auto_disconnect():
        config = toml.load(constants.DATA_DIR + 'config.toml')
        return config['music']['auto_disconnect']


class Playlist:
    def __init__(self, id_, name, guild_id, description):
        self.id = id_
        self.name = name
        self.guild_id = guild_id
        self.description = description

    @classmethod
    def create_new(cls, name, guild):
        return cls(uuid.uuid4(), name, guild.id, "")


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
    def __init__(self, id_, title, playlist_id, previous_song_id, webpage_url, duration):
        self.id = id_
        self.title = title
        self.playlist_id = playlist_id
        self.previous_song_id = previous_song_id
        self.webpage_url = webpage_url
        self.duration = duration

    @classmethod
    def create_new(cls, title, playlist_id, previous_song_id, webpage_url, duration):
        return cls(uuid.uuid4(), title, playlist_id, previous_song_id, webpage_url, duration)


class PlaylistSongRepository:
    def __init__(self, database):
        self.db = database
        cursor = self.db.cursor()
        cursor.execute('PRAGMA foreign_keys = ON')
        cursor.execute('CREATE TABLE IF NOT EXISTS playlist_songs (id TEXT PRIMARY KEY, title TEXT, '
                       'playlist_id TEXT, previous_song_id INTEGER, webpage_url TEXT, duration INTEGER, '
                       'FOREIGN KEY(playlist_id) REFERENCES playlist(id))')
        self.db.commit()

    def get_all(self):
        """Get list of all playlists"""
        results = self.db.cursor().execute('SELECT * FROM playlist_songs').fetchall()
        playlists = []
        for result in results:
            playlists.append(Playlist(result[0], result[1], result[2], result[3]))
        return playlists

    def get_by_id(self, id_):
        result = self.db.cursor().execute('SELECT * FROM playlist_songs WHERE id=?', (id_,)).fetchone()
        return PlaylistSong(result[0], result[1], result[2], result[3], result[4], result[5])

    def get_by_playlist(self, playlist):
        # Get list of all songs in playlist
        cursor = self.db.cursor()
        values = (playlist.id,)
        cursor.execute('SELECT * FROM playlist_songs WHERE playlist_id=?', values)
        results = cursor.fetchall()

        songs = []
        for result in results:
            songs.append(PlaylistSong(result[0], result[1], result[2], result[3], result[4], result[5]))
        return songs

    def add(self, playlist_song: PlaylistSong):
        cursor = self.db.cursor()
        values = (str(playlist_song.id), playlist_song.title, playlist_song.playlist_id,
                  playlist_song.previous_song_id, playlist_song.webpage_url, playlist_song.duration)
        cursor.execute('INSERT INTO playlist_songs VALUES (?, ?, ?, ?, ?, ?)', values)
        self.db.commit()

    def update(self, playlist_song: PlaylistSong):
        cursor = self.db.cursor()
        values = (playlist_song.title, playlist_song.playlist_id, playlist_song.previous_song_id,
                  playlist_song.webpage_url, playlist_song.duration, playlist_song.id)
        cursor.execute('UPDATE playlist_songs SET title=?, playlist_id=?, '
                       'previous_song_id=?, webpage_url=?, duration=? WHERE id=?', values)
        self.db.commit()

    def remove(self, playlist):
        cursor = self.db.cursor()
        values = (playlist.id,)
        cursor.execute('DELETE FROM playlist_songs WHERE id=?', values)
        self.db.commit()


class Alexa(commands.Cog):
    """Play some funky music in a voice chat"""
    NOT_CONNECTED_EMBED = discord.Embed(
        colour=constants.EmbedStatus.FAIL.value,
        description="I need to be in a voice channel to execute music "
                    "commands. \nUse **/join** or **/play** to connect me to a channel")

    def __init__(self, bot):
        self.bot = bot
        self.music_players = {}
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
        with open(constants.DATA_DIR + 'config.toml', 'w') as config_file:
            toml.dump(config, config_file)

    async def init_wavelink(self):
        config = toml.load(constants.DATA_DIR + 'config.toml')
        await wavelink.NodePool.create_node(
            bot=self.bot, host=config['lavalink']['address'],
            port=config['lavalink']['port'], password=config['lavalink']['password'])

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
    async def play(self, interaction: discord.Interaction, url: str):
        """Plays from a url (almost anything youtube_dl supports)"""
        # Join channel and create music player instance if it doesn't exist
        music_player = await self._get_music_player(interaction.user.voice.channel)

        # Alert due to song errors
        await interaction.response.defer()

        try:
            songs = await self._get_songs(url)
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

        # Add playlist
        if len(songs) > 1:
            result = await music_player.add_multiple(songs, )
            if result == PlayerResult.PLAYING:
                embed = discord.Embed(
                    colour=constants.EmbedStatus.YES.value,
                    description=f"Now playing playlist {songs[0].playlist}")
                await interaction.followup.send(embed=embed)
                return
            elif result == PlayerResult.QUEUEING:
                embed = discord.Embed(
                    colour=constants.EmbedStatus.YES.value,
                    description=f"Added `{len(songs)}` songs from playlist {songs} to "
                                f"#{len(music_player.song_queue) - 1} in queue")
                await interaction.followup.send(embed=embed)
                return

        # Add song
        song = songs[0]
        result = await music_player.add(song)
        duration = await self._format_duration(song.get_duration())
        song_name = f"[{song.get_title()}]({song.get_url()}) `{duration}`"
        if result == PlayerResult.PLAYING:
            embed = discord.Embed(
                colour=constants.EmbedStatus.YES.value,
                description=f"Now playing {song_name}")
            await interaction.followup.send(embed=embed)
            return
        elif result == PlayerResult.QUEUEING:
            embed = discord.Embed(
                colour=constants.EmbedStatus.YES.value,
                description=f"Song {song_name} added to #{len(await music_player.get_next_queue()) - 1} in queue")
            await interaction.followup.send(embed=embed)
            return

    @app_commands.command()
    @perms.check()
    async def playsearch(self, interaction, search: str):
        # Join channel and create music player instance if it doesn't exist
        if not interaction.guild.voice_client:
            await interaction.user.voice.channel.connect()
        music_player = await self._get_music_player(interaction.guild)

        # Set urls to be used by the searcher
        base_url = "https://www.youtube.com"
        search_url = f"https://www.youtube.com/results?search_query={search}"

        # Query YouTube with a search term and grab the title, duration and url
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
            await interaction.response.send_message(embed=embed)
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
        msg = await interaction.response.send_message(embed=embed)

        # Add reaction button for every result
        reactions = []
        for index in range(len(results_format)):
            emoji = reaction_buttons.number_to_emoji(index + 1)
            await msg.add_reaction(emoji)
            reactions.append(emoji)

        # Check if the requester selects a valid reaction
        def reaction_check(reaction, user):
            return user == interaction.user and str(reaction) in reactions

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
        await music_player.add(selected_song)

    @app_commands.command()
    @perms.check()
    async def stop(self, interaction: discord.Interaction):
        """Stops and clears the queue"""
        if not interaction.guild.voice_client:
            interaction.response.send_message(embed=self.NOT_CONNECTED_EMBED)
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
            interaction.response.send_message(embed=self.NOT_CONNECTED_EMBED)
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
            interaction.response.send_message(embed=self.NOT_CONNECTED_EMBED)
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
    async def skip(self, interaction: discord.Interaction):
        """Skip the current song and play the next song"""
        # Get music player
        if not interaction.guild.voice_client:
            interaction.response.send_message(embed=self.NOT_CONNECTED_EMBED)
            return
        music_player = await self._get_music_player(interaction.user.voice.channel)

        # Check if there's queue is empty
        if len(await music_player.get_next_queue()) < 1:
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
            interaction.response.send_message(embed=self.NOT_CONNECTED_EMBED)
            return
        music_player = await self._get_music_player(interaction.user.voice.channel)

        # Alert if not enough songs in queue
        if len(await music_player.get_next_queue()) < 2:
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
        """Loop the currently playing song"""
        # Get music player
        if not interaction.guild.voice_client:
            interaction.response.send_message(embed=self.NOT_CONNECTED_EMBED)
            return
        music_player = await self._get_music_player(interaction.user.voice.channel)

        # Disable loop if enabled
        if music_player.loop_toggle:
            await music_player.unloop()
            embed = discord.Embed(
                colour=constants.EmbedStatus.NO.value,
                description="Loop disabled")
            await interaction.response.send_message(embed=embed)
            return

        # Enable loop if disabled
        await music_player.loop()
        embed = discord.Embed(
            colour=constants.EmbedStatus.YES.value,
            description="Loop enabled")
        await interaction.response.send_message(embed=embed)
        return

    @queue_group.command(name="list")
    @perms.check()
    async def queue_list(self, interaction: discord.Interaction, page: int = 1):
        """List the current song queue"""
        if not interaction.guild.voice_client:
            interaction.response.send_message(embed=self.NOT_CONNECTED_EMBED)
            return
        music_player = await self._get_music_player(interaction.user.voice.channel)

        # Notify user if nothing is in the queue
        queue = await music_player.get_next_queue()
        if not queue:
            embed = discord.Embed(
                colour=constants.EmbedStatus.FAIL.value,
                description="There's nothing in the queue right now")
            await interaction.response.send_message(embed=embed)
            return

        # Output first in queue as currently playing
        embed = discord.Embed(
            colour=constants.EmbedStatus.INFO.value,
            title=f"{constants.EmbedIcon.MUSIC} Music Queue")
        playing = await music_player.get_playing()
        duration = await self._format_duration(playing.get_duration())
        current_time = await self._format_duration(await music_player.get_seek_position())

        # Set header depending on if looping or not, and whether to add a spacer
        queue_status = False
        if music_player.is_looping():
            header = "Currently Playing (Looping)"
        else:
            header = "Currently Playing"
        if len(queue) > 1:
            queue_status = True
            spacer = "\u200B"
        else:
            spacer = ""
        embed.add_field(
            name=header,
            value=f"{playing.get_title()} "
                  f"`{current_time}/{duration}` \n{spacer}")

        # List remaining songs in queue plus total duration
        if queue_status:
            queue_info = []

            # Modify page variable to get every ten results
            page -= 1
            if page > 0:
                page = page * 10

            total_duration = -queue[0].get_duration()
            for song in queue:
                total_duration += song.get_duration()

            for index, song in enumerate(
                    islice(queue, page, page + 10)):
                duration = await self._format_duration(song.get_duration())
                queue_info.append(f"{page + index + 1}. {song.get_title()} `{duration}`")

            # Alert if no songs are on the specified page
            if page > 0 and not queue_info:
                embed = discord.Embed(
                    colour=constants.EmbedStatus.FAIL.value,
                    description="There are no songs on that page")
                await interaction.response.send_message(embed=embed)
                return

            # Omit songs past 10 and just display amount instead
            if len(queue) > page + 11:
                queue_info.append(
                    f"`+{len(queue) - 11 - page} more in queue`")

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
            interaction.response.send_message(embed=self.NOT_CONNECTED_EMBED)
            return
        music_player = await self._get_music_player(interaction.user.voice.channel)

        # Try to remove song from queue using the specified index
        try:
            if original_pos < 1:
                raise IndexError("Position can\'t be be less than 1")
            song = music_player.song_queue[original_pos]
        except IndexError:
            embed = discord.Embed(
                colour=constants.EmbedStatus.FAIL.value,
                description="There's no song at that position")
            await interaction.response.send_message(embed=embed)
            return

        # Move song into new position in queue
        if not 1 <= new_pos < len(music_player.song_queue):
            embed = discord.Embed(
                colour=constants.EmbedStatus.FAIL.value,
                description="You can't move the song into that position")
            await interaction.response.send_message(embed=embed)
            return
        music_player.song_queue.pop(original_pos)
        music_player.song_queue.insert(new_pos, song)

        # Output result to chat
        duration = await self._format_duration(song.duration)
        embed = discord.Embed(
            colour=constants.EmbedStatus.YES.value,
            description=f"[{song.title}]({song.webpage_url}) "
                        f"`{duration}` has been moved from position #{original_pos} "
                        f"to position #{new_pos}")
        await interaction.response.send_message(embed=embed)

    @queue_group.command(name="add")
    @perms.check()
    async def queue_add(self, interaction, position: int, url: str):
        """Adds a song to the queue"""
        # Get music player
        if not interaction.guild.voice_client:
            interaction.response.send_message(embed=self.NOT_CONNECTED_EMBED)
            return
        music_player = await self._get_music_player(interaction.user.voice.channel)

        # Alert if too many songs in queue
        if len(music_player.song_queue) > 100:
            embed = discord.Embed(
                colour=constants.EmbedStatus.FAIL.value,
                description="Too many songs in queue. Calm down.")
            await interaction.response.send_message(embed=embed)
            return

        # Add the song to the queue and output result
        try:
            songs = await self._get_songs(url)
        except VideoTooLongError:
            embed = discord.Embed(
                colour=constants.EmbedStatus.FAIL.value,
                description="Woops, that video is too long")
            await interaction.response.send_message(embed=embed)
            return
        except VideoUnavailableError:
            embed = discord.Embed(
                colour=constants.EmbedStatus.FAIL.value,
                description="Woops, that video is unavailable")
            await interaction.response.send_message(embed=embed)
            return

        await music_player.add(songs[0], position)
        #music_player.song_queue.insert(position, songs[0])
        #if position > len(music_player.song_queue):
        #    position = len(music_player.song_queue) - 1

        embed = discord.Embed(
            colour=constants.EmbedStatus.YES.value,
            description=f"Added {songs[0].get_title()} to #{position} in queue")
        await interaction.response.send_message(embed=embed)
        return

    @queue_group.command(name="remove")
    @perms.check()
    async def queue_remove(self, interaction, position: int):
        """Remove a song from the queue"""
        # Get music player
        if not interaction.guild.voice_client:
            interaction.response.send_message(embed=self.NOT_CONNECTED_EMBED)
            return
        music_player = await self._get_music_player(interaction.user.voice.channel)

        # Try to remove song from queue using the specified index
        try:
            if position < 1:
                raise IndexError('Position can\'t be less than 1')
            song = music_player.song_queue[position]
            await music_player.remove(position)
        except IndexError:
            embed = discord.Embed(
                colour=constants.EmbedStatus.FAIL.value,
                description="That's an invalid queue position")
            await interaction.response.send_message(embed=embed)
            return

        # Output result to chat
        duration = await self._format_duration(song.duration)
        embed = discord.Embed(
            colour=constants.EmbedStatus.NO.value,
            description=f"[{song.title}]({song.webpage_url}) `{duration}` "
                        f"has been removed from position #{position} of the queue")
        await interaction.response.send_message(embed=embed)

    @queue_group.command(name="clear")
    @perms.check()
    async def queue_clear(self, interaction):
        """Clears the entire queue"""
        if not interaction.guild.voice_client:
            interaction.response.send_message(embed=self.NOT_CONNECTED_EMBED)
            return
        music_player = await self._get_music_player(interaction.user.voice.channel)

        # Try to remove all but the currently playing song from the queue
        if len(await music_player.get_next_queue()) < 1:
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
            songs = await self._fetch_songs(url)
        except VideoTooLongError:
            embed = discord.Embed(
                colour=constants.EmbedStatus.FAIL.value,
                description="Woops, that video is too long")
            await interaction.response.send_message(embed=embed)
            return
        except VideoUnavailableError:
            embed = discord.Embed(
                colour=constants.EmbedStatus.FAIL.value,
                description="Woops, that video is unavailable")
            await interaction.response.send_message(embed=embed)
            return

        # Set previous song as the last song in the playlist
        if not playlist_songs:
            previous_song = None
        else:
            song_ids = []
            previous_ids = []
            for playlist_song in playlist_songs:
                song_ids.append(playlist_song.id)
                previous_ids.append(playlist_song.previous_song_id)
            previous_song = list(set(song_ids) - set(previous_ids))[0]

        # Add song to playlist
        self.playlist_songs.add(PlaylistSong.create_new(
            songs[0].title, playlist.id, previous_song, songs[0].webpage_url, songs[0].duration))
        duration = await self._format_duration(songs[0].duration)
        embed = discord.Embed(
            colour=constants.EmbedStatus.YES.value,
            description=f"Added [{songs[0].title}]({songs[0].webpage_url}) "
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
            next_song.previous_song_id = selected_song.previous_song_id
            self.playlist_songs.update(next_song)
        except IndexError:
            pass

        # Remove selected song from playlist
        self.playlist_songs.remove(selected_song)
        duration = await self._format_duration(selected_song.duration)
        embed = discord.Embed(
            colour=constants.EmbedStatus.NO.value,
            description=f"[{selected_song.title}]({selected_song.webpage_url}) "
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
                (other_song.previous_song_id, selected_song.id),
                (selected_song.id, other_song.id)]

        # Connect the two songs beside the original song position
        try:
            after_selected_song = songs[int(original_pos)]
            values.append((selected_song.previous_song_id, after_selected_song.id))
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
            description=f"[{selected_song.title}]({selected_song.webpage_url}) "
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
            formatted_songs.append(f"{page + index + 1}. [{song_name}]({song.webpage_url}) `{duration}`")

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
    async def playlist_play(self, interaction, playlist_name: str):
        """Play from a locally saved playlist"""
        # Get music player
        if not interaction.guild.voice_client:
            await interaction.user.voice.channel.connect()
        music_player = await self._get_music_player(interaction.guild)

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

        stream = await YTDLStream.from_url(songs[0].webpage_url)
        result = await music_player.add(stream[0])
        if result.PLAYING:
            embed = discord.Embed(
                colour=constants.EmbedStatus.YES.value,
                description=f"Now playing playlist `{playlist.name}`")
            await interaction.response.send_message(embed=embed)
        else:
            embed = discord.Embed(
                colour=constants.EmbedStatus.YES.value,
                description=f"Added playlist `{playlist.name}` to queue")
            await interaction.response.send_message(embed=embed)

        # Add remaining songs to queue
        for i in range(1, len(songs)):
            stream = await YTDLStream.from_url(songs[i].webpage_url)
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
            await channel.guild.change_voice_state(channel=channel, self_deaf=True)
            self.music_players[channel.guild.id] = music_player
        return music_player

    async def _get_songs(self, query: str):
        return await WavelinkAudioSource.from_query(query)

    # Format duration based on what values there are
    @staticmethod
    async def _format_duration(seconds):
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

    @staticmethod
    async def _order_playlist_songs(playlist_songs):
        """Gets playlist songs from name"""
        # Use dictionary to pair songs with the next song
        song_links = {}
        for song in playlist_songs:
            song_links[song.previous_song_id] = song

        # Order playlist songs into list
        ordered_songs = []
        next_song = song_links.get(None)
        while next_song is not None:
            ordered_songs.append(next_song)
            next_song = song_links.get(next_song.id)

        return ordered_songs

    @staticmethod
    async def _fetch_songs(query):
        """Grab audio source from YouTube and check if longer than 3 hours"""
        if "youtube" in query or "youtu.be" in query:
            songs = await YTDLStream.from_url(query)
        else:
            songs = await YTDLStream.from_url(query)

        if not songs:
            raise VideoUnavailableError("Specified song is unavailable")

        # if songs.duration >= 10800:
        #     raise VideoTooLongError("Specified song is longer than 3 hours")

        return songs


async def setup(bot):
    await bot.add_cog(Alexa(bot))
