import enum

import discord


MAIN_DIR = __package__.split('.')[0]
ASSETS_DIR = 'assets/'
CACHE_DIR = 'cache/'
GLOBAL_DATA_DIR = 'data/'
DATA_DIR = ''


def instance_location(instance):
    global DATA_DIR
    DATA_DIR = f'{GLOBAL_DATA_DIR}/{instance}/'


class EmbedStatus(enum.Enum):
    YES = discord.Color.from_rgb(67, 160, 71)
    NO = discord.Color.from_rgb(218, 120, 16)
    INFO = discord.Color.from_rgb(3, 169, 244)
    GAME = discord.Color.from_rgb(229, 226, 41)
    FAIL = discord.Color.from_rgb(211, 47, 47)
    SPECIAL = discord.Color.from_rgb(103, 58, 183)


class EmbedIcon(enum.Enum):
    DEFAULT = ':bulb: '
    HELP = ':question: '
    MUSIC = ':musical_note: '
    DATABASE = ':cd: '

    def __str__(self):
        return self.value
