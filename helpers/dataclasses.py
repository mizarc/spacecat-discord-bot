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