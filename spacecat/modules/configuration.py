import sqlite3
from itertools import islice

import discord
from discord import app_commands
from discord.ext import commands

import toml

from spacecat.helpers import constants
from spacecat.helpers import perms


class Configuration(commands.Cog):
    """Modify Discord wide bot settings"""
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        # Auto generate the permissions config category with
        # default (@everyone) role
        config = toml.load(constants.DATA_DIR + 'config.toml')
        try:
            config['permissions']
        except KeyError:
            config['permissions'] = {}
        try:
            config['permissions']['default']
        except KeyError:
            config['permissions']['default'] = []

        with open(constants.DATA_DIR + 'config.toml', 'w') as config_file:
            toml.dump(config, config_file)

    @commands.Cog.listener()
    async def on_command_error(self, ctx, error):
        if isinstance(error, commands.CommandNotFound):
            prefix = ctx.prefix
            cmd = ctx.message
            cmd_name = cmd.content.split()[0][len(prefix):]
            cmd_args = cmd.content.split()[1:]

            # Query if command exists as an alias in database
            db = sqlite3.connect(constants.DATA_DIR + 'spacecat.db')
            cursor = db.cursor()
            query = (ctx.guild.id, cmd_name)
            cursor.execute(
                'SELECT command FROM command_alias '
                'WHERE server_id=? AND alias=?', query)
            result = cursor.fetchall()
            db.close()

            # Use command linked to alias to replace command process
            if result:
                cmd.content = f"{prefix}{result[0][0]} {' '.join(cmd_args)}"
                await self.bot.process_commands(cmd)

    @app_commands.command()
    @perms.exclusive()
    async def status(self, interaction, status_name: str):
        config = toml.load(constants.DATA_DIR + 'config.toml')
        status = discord.Status[status_name]
        activity_name = config['base']['activity_type']
        try:
            activity = discord.Activity(
                type=discord.ActivityType[activity_name],
                name=config['base']['activity_name'])
        except KeyError:
            activity = None

        # Check if valid status name was used
        if status is None:
            embed = discord.Embed(
                colour=constants.EmbedStatus.FAIL.value,
                description="That's not a valid status")
            await interaction.response.send_message(embed=embed)
            return

        if activity:
            await self.bot.change_presence(status=status, activity=activity)
        else:
            await self.bot.change_presence(status=status)

        config['base']['status'] = status_name
        with open(constants.DATA_DIR + 'config.toml', 'w') as config_file:
            toml.dump(config, config_file)

    @app_commands.command()
    @perms.exclusive()
    async def activity(self, interaction, activity_name: str, *, name: str):
        config = toml.load(constants.DATA_DIR + 'config.toml')
        activity_type = discord.ActivityType[activity_name]
        activity = discord.Activity(
            type=activity_type,
            name=name,
            url='https://www.twitch.tv/yeet')
        try:
            status = config['base']['status']
        except KeyError:
            status = None

        if activity_type is None:
            embed = discord.Embed(
                colour=constants.EmbedStatus.FAIL.value,
                description="That's not a valid activity type")
            await interaction.response.send_message(embed=embed)
            return

        if status:
            await self.bot.change_presence(activity=activity, status=status)
        else:
            await self.bot.change_presence(activity=activity)

        config['base']['activity_type'] = activity_type
        config['base']['activity_name'] = name
        with open(constants.DATA_DIR + 'config.toml', 'w') as config_file:
            toml.dump(config, config_file)


async def setup(bot):
    await bot.add_cog(Configuration(bot))
