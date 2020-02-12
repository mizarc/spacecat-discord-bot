import configparser
from itertools import islice
import os
import sqlite3

import discord
from discord.ext import commands
import toml

from spacecat.helpers import perms
from spacecat.helpers import settings

class Configuration(commands.Cog):
    """Modify Discord wide bot settings"""
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        # Auto generate the permissions config category with
        # default (@everyone) role
        config = toml.load(settings.data + 'config.toml')
        try:
            config['permissions']
        except KeyError:
            config['permissions'] = {}
        try:
            config['permissions']['default']
        except KeyError:
            config['permissions']['default'] = []

        with open(settings.data + "config.toml", "w") as config_file:
            toml.dump(config, config_file)

    @commands.Cog.listener()
    async def on_command_error(self, ctx, error):
        if isinstance(error, commands.CommandNotFound):
            prefix = ctx.prefix
            cmd = ctx.message
            cmd_name = cmd.content.split()[0][len(prefix):]
            cmd_args = cmd.content.split()[1:]

            # Query if command exists as an alias in database
            db = sqlite3.connect(settings.data + 'spacecat.db')
            cursor = db.cursor()
            query = (ctx.guild.id, cmd_name)
            cursor.execute(f"SELECT command FROM command_alias WHERE server_id=? AND alias=?", query)
            result = cursor.fetchall()
            db.close()

            # Use command linked to alias to replace command process
            if result:
                cmd.content = f"{prefix}{result[0][0]} {' '.join(cmd_args)}"
                await self.bot.process_commands(cmd)

    @commands.command()
    @perms.exclusive()
    async def status(self, ctx, statusname):
        config = toml.load(settings.data + 'config.toml')
        status = settings.status_class(statusname)
        try:
            activity = discord.Activity(type=settings.activity_type_class(config['base']['activity_type']), name=config['base']['activity_name'])
        except KeyError:
            activity = None
        

        # Check if valid status name was used
        if status == None:
            embed = discord.Embed(colour=settings.embed_type('warn'), description=f"That's not a valid status")
            await ctx.send(embed=embed)
            return

        if activity:
            await self.bot.change_presence(status=status, activity=activity)
        else:
            await self.bot.change_presence(status=status)

        config['base']['status'] = statusname
        with open(settings.data + "config.toml", "w") as config_file:
            toml.dump(config, config_file)

    @commands.command()
    @perms.exclusive()
    async def activity(self, ctx, acttype, *, name):
        config = toml.load(settings.data + 'config.toml')
        activitytype = settings.activity_type_class(acttype)
        activity = discord.Activity(type=activitytype, name=name, url="https://www.twitch.tv/yeet")
        try:
            status = config['base']['status']
        except KeyError:
            status = None

        if activitytype == None:
            embed = discord.Embed(colour=settings.embed_type('warn'), description=f"That's not a valid activity type")
            await ctx.send(embed=embed)
            return

        if status:
            await self.bot.change_presence(activity=activity, status=status)
        else:
            await self.bot.change_presence(activity=activity)


        config['base']['activity_type'] = acttype
        config['base']['activity_name'] = name
        with open(settings.data + "config.toml", "w") as config_file:
            toml.dump(config, config_file)

    @commands.group(invoke_without_command=True)
    @perms.exclusive()
    async def permpreset(self, ctx):
        print('nah')

    @permpreset.command(name='create')
    @perms.exclusive()
    async def permpreset_create(self, ctx):
        print('nah')

    @permpreset.command(name='destroy')
    @perms.exclusive()
    async def permpreset_destroy(self, ctx):
        print('nah')

    @permpreset.command(name='add')
    @perms.exclusive()
    async def permpreset_add(self, ctx):
        print('nah')

    @permpreset.command(name='remove')
    @perms.exclusive()
    async def permpreset_remove(self, ctx):
        print('nah')

    @permpreset.command(name='list')
    @perms.exclusive()
    async def permpreset_list(self, ctx):
        config = toml.load(settings.data + 'config.toml')
        perm_presets = config['permissions']

        # Output first in queue as currently playing
        embed = discord.Embed(colour=settings.embed_type('info'))
        image = discord.File(
            settings.embed_icons('information'),
            filename="image.png")
        embed.set_author(name="Permission Presets",
            icon_url="attachment://image.png")

        # Format playlist songs into pretty list
        perm_presets_output = []
        for index, preset_name in enumerate(islice(perm_presets, 0, 10)):
            perm_presets_output.append(f"{index + 1}. {preset_name}")

        embed.add_field(
            name=f"{len(perm_presets)} available",
            value='\n'.join(perm_presets_output), inline=False)
        await ctx.send(file=image, embed=embed)


def setup(bot):
    bot.add_cog(Configuration(bot))