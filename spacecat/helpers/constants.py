import enum
import importlib.resources

import discord

from .. import resources


MAIN_DIR = __package__.split('.')[0]
ASSETS_DIR = 'assets/'
CACHE_DIR = 'cache/'
GLOBAL_DATA_DIR = 'data/'
DATA_DIR = ''

def instance_location(instance):
    global DATA_DIR
    DATA_DIR = f'{GLOBAL_DATA_DIR}/{instance}/'

STATUS = {
    'online': discord.Status.online,
    'idle': discord.Status.idle,
    'dnd': discord.Status.dnd,
    'invisible': discord.Status.invisible
}

EMBED_TYPE = {
    'accept': discord.Color.from_rgb(67, 160, 71),
    'warn': discord.Color.from_rgb(211, 47, 47),
    'info': discord.Color.from_rgb(3, 169, 244),
    'special': discord.Color.from_rgb(103, 58, 183)
}


class EmbedIcon(enum.Enum):
    INFORMATION = ':bulb: '
    HELP = ':question:  '
    MUSIC = ':musical_note: '
    DATABASE = ':cd: '

    def __str__(self):
        return str(self.value)


NUM_TO_EMOJI = {
    1: "1\u20e3",
    2: "2\u20e3",
    3: "3\u20e3",
    4: "4\u20e3",
    5: "5\u20e3"
}

EMOJI_TO_NUM = {
    "1\u20e3": 1,
    "2\u20e3": 2,
    "3\u20e3": 3,
    "4\u20e3": 4,
    "5\u20e3": 5
}