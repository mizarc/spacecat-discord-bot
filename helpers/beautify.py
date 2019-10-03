import discord

from helpers.dataclasses import embed_type

async def send(ctx, body, header="", type="information"):
    colour = embed_type(type)
    embed = discord.Embed(title=header, description=body, colour=colour)
    await ctx.send(embed=embed)
    return
