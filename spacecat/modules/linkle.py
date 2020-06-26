import itertools
import math
import sqlite3

import discord
from discord.ext import commands

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

        try:
            # Show linked text channel if joining a linked voice channel
            query = (member.guild.id, after.channel.id)
            cursor.execute(
                'SELECT text_channel FROM linked_channel '
                'WHERE server_id=? AND voice_channel=?', query)
            text_channel_id = cursor.fetchall()
            if text_channel_id:
                text_channel = await self.bot.fetch_channel(text_channel_id[0])
                await text_channel.set_permissions(member, read_messages=True)
        except AttributeError:
            pass

        try:
            # Hide linked text channel if leaving a linked voice channel
            query = (member.guild.id, before.channel.id)
            cursor.execute(
                'SELECT text_channel FROM linked_channel '
                'WHERE server_id=? AND voice_channel=?', query)
            text_channel_id = cursor.fetchall()
            if text_channel_id:
                text_channel = await self.bot.fetch_channel(text_channel_id[0])
                await text_channel.set_permissions(member, read_messages=None)
                text_channel = await self.bot.fetch_channel(text_channel_id[0])

                # Remove user from the perm overwrites list entirely if they
                # do not have any other permission overwrites
                if text_channel.overwrites_for(member).is_empty():
                    await text_channel.set_permissions(member, overwrite=None)
        except AttributeError:
            pass

    @commands.command()
    @perms.check()
    async def linkchannels(
            self, ctx, voice_channel: discord.VoiceChannel, text_channel: discord.TextChannel):
        """
        Reveal a text channel when a user joins a voice channel.
        On a user joining a linked voice channel, the associated text
        channel will be revealed to them, and will subsequently hide
        itself when the user leaves. Ensure that the linked text channel
        is hidden to users by default.
        """
        exists = await self._query_channel_links(voice_channel.id, text_channel.id)
        if exists:
            embed = discord.Embed(
                colour=constants.EmbedStatus.FAIL.value,
                description="Those channels are already linked")
            await ctx.send(embed=embed)
            return

        # Add linked values to database
        db = sqlite3.connect(constants.DATA_DIR + 'spacecat.db')
        cursor = db.cursor()
        value = (ctx.guild.id, voice_channel.id, text_channel.id)
        cursor.execute("INSERT INTO linked_channel VALUES (?,?,?)", value)
        db.commit()
        db.close()

        embed = discord.Embed(
            colour=constants.EmbedStatus.YES.value,
            description=f"Voice channel `{voice_channel.name}` has been "
            f"linked to text channel `{text_channel.name}`")
        await ctx.send(embed=embed)

    @commands.command()
    @perms.check()
    async def unlinkchannels(
            self, ctx, voice_channel: discord.VoiceChannel, text_channel: discord.TextChannel):
        """
        Remove the connection between a text and voice channel.
        If a text and voice channel were linked together with the linkchannels
        command, this command can be used to unlink the channels stopping it
        from being dynamically shown and hidden on voice connects.
        """
        exists = await self._query_channel_links(voice_channel.id, text_channel.id)
        if not exists:
            embed = discord.Embed(
                colour=constants.EmbedStatus.FAIL.value,
                description="Those channels aren't linked")
            await ctx.send(embed=embed)
            return

        # Remove linked value from database
        db = sqlite3.connect(constants.DATA_DIR + 'spacecat.db')
        cursor = db.cursor()
        value = (voice_channel.id, text_channel.id)
        cursor.execute(
            'DELETE FROM linked_channel '
            'WHERE voice_channel=? AND text_channel=?', value)
        db.commit()
        db.close()

        embed = discord.Embed(
            colour=constants.EmbedStatus.NO.value,
            description=f"Voice channel `{voice_channel.name}` has been "
            f"unlinked to text channel `{text_channel.name}`")
        await ctx.send(embed=embed)

    @commands.command()
    @perms.check()
    async def listlinkchannels(self, ctx, page=1):
        """
        List currently linked voice to text channels
        Channels that have been linked together by the linkchannels command
        can be viewed here.
        """
        db = sqlite3.connect(constants.DATA_DIR + 'spacecat.db')
        cursor = db.cursor()
        value = (ctx.guild.id,)
        cursor.execute(
            'SELECT * FROM linked_channel WHERE server_id=?', value)
        links = cursor.fetchall()
        db.close()

        if not links:
            embed = discord.Embed(
                colour=constants.EmbedStatus.FAIL.value,
                description="There are no linked channels")
            return

        # Modify page variable to get every ten results
        page -= 1
        if page > 0:
            page = page * 10

        links_display_list = []
        for index, link in enumerate(itertools.islice(links, page, page + 10)):
            voice_channel = self.bot.get_channel(link[1])
            text_channel = self.bot.get_channel(link[2])
            links_display_list.append(
                f"**{page + index + 1}.** {voice_channel.mention} = {text_channel.mention}")

        if page + 10 < len(links):
            prefix = await self.bot.get_prefix(ctx.message)
            links_display_list.append(
                "`For more results, type "
                f"{prefix[2]}{ctx.command.name} {math.floor((page + 20) / 10)}`")
        links_display = '\n'.join(links_display_list)

        embed = discord.Embed(
            colour=constants.EmbedStatus.INFO.value,
            title=f"{constants.EmbedIcon.DATABASE} Linked Channels")
        embed.add_field(
            name=f"There are `{len(links)}` links",
            value=links_display, inline=False)
        await ctx.send(embed=embed)

    async def _query_channel_links(self, voice_channel, text_channel):
        """Check database to see if link already exists"""
        db = sqlite3.connect(constants.DATA_DIR + 'spacecat.db')
        cursor = db.cursor()
        query = (voice_channel, text_channel)
        cursor.execute(
            'SELECT * FROM linked_channel WHERE voice_channel=? AND text_channel=?', query)
        link = cursor.fetchall()
        db.close()

        return link


def setup(bot):
    bot.add_cog(Linkle(bot))
