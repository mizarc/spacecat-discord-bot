import os
import sqlite3

import discord
from discord.ext import commands
import toml

from spacecat.helpers import constants
from spacecat.helpers import perms

class Linkle(commands.Cog):
    """Have channels (dis)appear under certain conditions"""

    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        db = sqlite3.connect(constants.DATA_DIR + 'spacecat.db')
        cursor = db.cursor()

        # Create database tables if they don't exist
        cursor.execute(
            'CREATE TABLE IF NOT EXISTS linked_channel'
            '(server_id INTEGER, voice_channel INTEGER, text_channel INTEGER)')

        db.commit()
        db.close()

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        """Do things when users join voice channels"""
        # Don't do anything if user doesn't switch channels
        if before.channel == after.channel or member.bot:
            return
        
        db = sqlite3.connect(constants.DATA_DIR + 'spacecat.db')
        db.row_factory = lambda cursor, row: row[0]
        cursor = db.cursor()

        # Hide linked text channel if leaving a linked voice channel
        try:
            query = (member.guild.id, before.channel.id)
            cursor.execute('SELECT text_channel FROM linked_channel '
                'WHERE server_id=? AND voice_channel=?', query)
            text_channel_id = cursor.fetchall()
            if text_channel_id:
                text_channel = await self.bot.fetch_channel(text_channel_id[0])
                await text_channel.set_permissions(member, read_messages=False)
        except AttributeError:
            pass

        # Show linked text channel if joining a linked voice channel
        try:
            query = (member.guild.id, after.channel.id)
            cursor.execute('SELECT text_channel FROM linked_channel '
                'WHERE server_id=? AND voice_channel=?', query)
            text_channel_id = cursor.fetchall()
            if text_channel_id:
                text_channel = await self.bot.fetch_channel(text_channel_id[0])
                await text_channel.set_permissions(member, read_messages=True)
        except AttributeError:
            pass

    @commands.command()
    @perms.check()
    async def linkchannels(self, ctx, voice_channel: discord.VoiceChannel,
            text_channel: discord.TextChannel):
        """
        Reveal a text channel when a user joins a voice channel
        On a user joining a linked voice channel, the associated text
        channel will be revealed to them, and will subsequently hide
        itself when the user leaves. Ensure that the linked text channel
        is hidden to users by default.
        """
        # Add linked values to database
        db = sqlite3.connect(constants.DATA_DIR + 'spacecat.db')
        cursor = db.cursor()
        value = (ctx.guild.id, voice_channel.id, text_channel.id)
        cursor.execute("INSERT INTO linked_channel VALUES (?,?,?)", value)
        db.commit()
        db.close()

        embed = discord.Embed(
            colour=constants.EMBED_TYPE['accept'],
            description=f"Voice channel `{voice_channel.name}` has been "
                f"linked to text channel `{text_channel.name}`")
        await ctx.send(embed=embed)


def setup(bot):
    bot.add_cog(Linkle(bot))