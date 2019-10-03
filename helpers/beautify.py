import discord

from helpers.dataclasses import embed_type

def simple(ctx, header, text, type):
    colour = embed_type(type)
    embed = discord.Embed(title=header, description=text, colour=colour)
    return embed