import discord

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
    if name == "warning":
        colour = discord.Color.from_rgb(211, 47, 47)
    elif name == "accepted":
        colour = discord.Color.from_rgb(67, 160, 71)  
    elif name == "information":
        colour = discord.Color.from_rgb(3, 169, 244)
    elif name == "special":
        colour = discord.Color.from_rgb(103, 58, 183)

    return colour