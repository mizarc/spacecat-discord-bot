import time
from typing import Optional

from wavelink import Node, SearchableTrack, YouTubeMusicTrack, NodePool
from wavelink.abc import Searchable
from wavelink.ext.spotify import SpotifySearchType, SpotifyClient, URLREGEX, BASEURL, SpotifyRequestError
from wavelink.utils import MISSING
import wavelink.ext


class SpotifyPartialTrack(wavelink.PartialTrack):
    def __init__(self, *, query: str, title: str, artist: str, duration: int, node: Optional[Node] = MISSING,
                 cls: Optional[SearchableTrack] = YouTubeMusicTrack):
        super().__init__(query=query, node=node, cls=cls)
        self.title = title
        self.author = artist
        self.duration = duration

    @classmethod
    async def search(cls):
        pass


class SpotifyPlaylist(Searchable):
    def __init__(self, name, tracks):
        self.name: name = name
        self.tracks: list[SpotifyPartialTrack] = tracks

    @classmethod
    async def search(cls, query: str, *, type: wavelink.ext.spotify.SpotifySearchType = None,
                     node: wavelink.Node = MISSING, return_first: bool = False) -> 'SpotifyPlaylist':
        if node is MISSING:
            node = NodePool.get_node()

        spotify_client = node._spotify
        data = await broad_spotify_search(spotify_client, query)

        tracks = [track['track'] for track in data['tracks']['items']]
        playlist_name = data["name"]
        track_sources = []

        for track in tracks:
            track_sources.append(SpotifyPartialTrack(query=f'{track["name"]} - {track["artists"][0]["name"]}',
                                                     title=track["name"],
                                                     artist=track["artists"][0]["name"],
                                                     duration=track["duration_ms"] / 1000))
        return cls(playlist_name, track_sources)


async def broad_spotify_search(spotify_client: SpotifyClient, query: str):
    if not spotify_client._bearer_token or time.time() >= spotify_client._expiry:
        await spotify_client._get_bearer_token()

    regex_result = URLREGEX.match(query)
    url = BASEURL.format(entity=regex_result['type'], identifier=regex_result['id'])

    async with spotify_client.session.get(url, headers=spotify_client.bearer_headers) as resp:
        if resp.status != 200:
            raise SpotifyRequestError(resp.status, resp.reason)

        data = await resp.json()
    return data
