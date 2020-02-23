import discord


# Data folder location
package = __package__.split('.')[0]
assets = 'assets/'
cache = 'cache/'
data = 'data/'


def activity_type_class(acttype):
    if acttype == "playing":
        activity = discord.ActivityType.playing
    elif acttype == "streaming":
        activity = discord.ActivityType.streaming
    elif acttype == "listening":
        activity = discord.ActivityType.listening
    elif acttype == "watching":
        activity = discord.ActivityType.watching
    else:
        return
    return activity


def status_class(statusname):
    if statusname == "online":
        status = discord.Status.online
    elif statusname == "idle":
        status = discord.Status.idle
    elif statusname == "dnd":
        status = discord.Status.dnd
    elif statusname == "invisible" or input == "offline":
        status = discord.Status.invisible
    else:
        return
    return status


def embed_type(name):
    if name == "warn":
        colour = discord.Color.from_rgb(211, 47, 47)
    elif name == "accept":
        colour = discord.Color.from_rgb(67, 160, 71)  
    elif name == "info":
        colour = discord.Color.from_rgb(3, 169, 244)
    elif name == "special":
        colour = discord.Color.from_rgb(103, 58, 183)
    return colour


def embed_icons(name):
    if name == "music":
        icon = assets + "music_disc.jpg"
    elif name == "database":
        icon = assets + "database.png"
    elif name == "information":
        icon = assets + "information.png"
    return icon


def number_to_emoji(number):
    emojis = {
        1: "1\u20e3",
        2: "2\u20e3",
        3: "3\u20e3",
        4: "4\u20e3",
        5: "5\u20e3"
    }
    return emojis.get(number)


def emoji_to_number(emoji):
    numbers = {
        "1\u20e3": 1,
        "2\u20e3": 2,
        "3\u20e3": 3,
        "4\u20e3": 4,
        "5\u20e3": 5
    }
    return numbers.get(emoji)