from asyncio import tasks
from collections import deque
import random
import time
from typing import Optional

import discord
import toml
import wavelink

from spacecat.helpers import constants
from spacecat.modules.musicbox import OriginalSource, PlayerResult, SongUnavailableError
from spacecat.modules.musicbox.music_player import MusicPlayer, Song
from spacecat.modules.musicbox.playlist import Playlist, PlaylistSong

class WavelinkSong(Song):
    def __init__(self, track, original_source, url, group=None, group_url=None,
                 title=None, artist=None, duration=None, requester_id=None):
        self._track: wavelink.Playable = track
        self._original_source: OriginalSource = original_source
        self._url: str = url
        self._playlist: str = group
        self._playlist_url: str = group_url
        self._title = title
        self._artist = artist
        self._duration = duration
        self._requester_id = requester_id

    @property
    def stream(self) -> wavelink.Playable:
        return self._track

    @property
    def title(self) -> str:
        return self._title if self._title else self._track.title

    @property
    def artist(self) -> Optional[str]:
        return self._artist if self._artist else self._track.author

    @property
    def duration(self) -> int:
        return self._duration if self._duration else int(self._track.length)

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

    @property
    def requester_id(self) -> int:
        return self._requester_id

    @classmethod
    async def from_local(cls, requester: discord.User, playlist_song: PlaylistSong,
                         playlist: Playlist = None) -> list['WavelinkSong']:
        """
        Process a local playlist song to obtain a track and create a list of WavelinkSong objects based on the song details and the requester.

        Parameters:
            requester (discord.User): The user requesting the song.
            playlist_song (PlaylistSong): The playlist song object containing the song details.
            playlist (Playlist, optional): The playlist to which the song belongs. Defaults to None.

        Returns:
            list['WavelinkSong']: A list containing WavelinkSong objects created from the local playlist song.
        """
        track = await wavelink.Playable.search(playlist_song.url)
        return [cls(track, OriginalSource.LOCAL, playlist_song.url, title=playlist_song.title,
                     artist=playlist_song.artist, duration=playlist_song.duration,
                     group=playlist.name, requester_id=requester.id)]

    @classmethod
    async def from_query(cls, query: str, requester: discord.User) -> list['WavelinkSong']:
        """
        Process a query to obtain a track and create a list of WavelinkSong objects based on the query and the requester.

        Parameters:
            query (str): The query used to search for the track.
            requester (discord.User): The user requesting the track.

        Returns:
            list['WavelinkSong']: A list containing WavelinkSong objects created from the query.
        """
        track = await wavelink.Playable.search(query)
        if not track:
            raise SongUnavailableError

        if track[0].playlist is None:
            return await cls._process_single(query, track[0], requester)
        else:
            return await cls._process_multiple(query, track, requester)

    @classmethod
    async def _process_single(cls, query: str, track: wavelink.Playable, requester: discord.User):
        """
        Process a single track to determine its source and create a WavelinkSong object.

        Parameters:
            query (str): The query that was used to obtain the track.
            track (wavelink.Playable): The track to create the WavelinkSong from.
            requester (discord.User): The user requesting the track.

        Returns:
            list['WavelinkSong']: A list containing a single WavelinkSong object created from the query.
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

        return [cls(track, source, track.uri, "", "", track.title, track.author, track.length, requester.id)]

    @classmethod
    async def _process_multiple(cls, query: str, tracks: wavelink.Playlist, requester: discord.User):
        """
        Process multiple tracks to determine their sources and create WavelinkSong objects.

        Parameters:
            query (str): The query used to obtain the tracks.
            tracks (wavelink.Playlist): The playlist containing tracks to process.
            requester (discord.User): The user requesting the tracks.

        Returns:
            list['WavelinkSong']: A list containing multiple WavelinkSong objects created from the tracks.
        """
        source = OriginalSource.UNKNOWN
        url = query
        playlist_name = ""
        
        if "youtube.com" in tracks[0].uri or "youtu.be" in query:
            if "Album - " in tracks[0].playlist.name:
                source, playlist_name = OriginalSource.YOUTUBE_ALBUM, tracks[0].playlist.name[8:]
            elif "playlist" in query:
                source, playlist_name = OriginalSource.YOUTUBE_PLAYLIST, tracks[0].playlist.name
        elif "open.spotify.com" in query:
            if "playlist" in query:
                source, url, playlist_name = OriginalSource.SPOTIFY_PLAYLIST, tracks[0].playlist.url, tracks[0].playlist.name
            elif "album" in query:
                source, url, playlist_name = OriginalSource.SPOTIFY_ALBUM, tracks[0].playlist.url, tracks[0].playlist.name
            else:
                source = OriginalSource.SPOTIFY_SONG

        return [cls(track, source, track.uri, playlist_name, url, track.title, track.author, track.length, requester.id)
                for track in tracks.tracks]

class WavelinkMusicPlayer(MusicPlayer[WavelinkSong]):
    def __init__(self):
        self._player: Optional[wavelink.Player] = None
        self._current: Optional[WavelinkSong] = None
        self._next_queue: deque[WavelinkSong] = deque()
        self._previous_queue: deque[WavelinkSong] = deque()
        self._is_looping = False
        self._is_skipping = False
        self._queue_reverse = False
        self._disconnect_time = time() + self._get_disconnect_time_limit()
        self._disconnect_job.start()

    @property
    def is_paused(self) -> bool:
        return self._player.paused

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
        await self._player.pause(True)

    async def resume(self):
        await self._player.pause(False)

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
        await self._player.stop()

    async def next(self):
        if not self._player.playing:
            return False
        self._queue_reverse = False
        self._is_skipping = True
        await self._player.stop()
        return True

    async def previous(self):
        self._queue_reverse = True
        self._is_skipping = True
        await self._player.stop()

    async def process_song_end(self):
        self._refresh_disconnect_timer()

        # Play current song again if set to loop.
        if self._is_looping and not self._is_skipping:
            await self.play(self._current)
            return
        self._is_skipping = False

        # Play next or previous based on direction toggle
        if self._queue_reverse:
            await self._play_previous_song()
            return
        await self._play_next_song()
        self._queue_reverse = False

    async def _play_next_song(self):
        next_song = None
        try:
            next_song = self._next_queue.popleft()
            await self._player.play(next_song.stream)
        except IndexError:
            pass
        self._previous_queue.appendleft(self._current)
        self._current = next_song

    async def _play_previous_song(self):
        previous_song = None
        try:
            previous_song = self._previous_queue.popleft()
            await self._player.play(previous_song.stream)
        except IndexError:
            pass
        self._next_queue.appendleft(self._current)
        self._current = previous_song

    async def enable_auto_disconnect(self):
        self._disconnect_job.start()

    async def disable_auto_disconnect(self):
        self._disconnect_job.cancel()

    @tasks.loop(seconds=30)
    async def _disconnect_job(self):
        if self._is_auto_disconnect() and time() > self._disconnect_time and not self._player.playing:
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