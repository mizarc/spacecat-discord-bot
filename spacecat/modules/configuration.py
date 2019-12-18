import configparser
import os
import sqlite3

import discord
from discord.ext import commands
import toml

from helpers import perms
from helpers.appearance import activity_type_class, status_class, embed_type, embed_icons

class Configuration(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_command_error(self, ctx, error):
        if isinstance(error, commands.CommandNotFound):
            prefix = ctx.prefix
            cmd = ctx.message
            cmd_name = cmd.content.split()[0][len(prefix):]
            cmd_args = cmd.content.split()[1:]

            # Query if command exists as an alias in database
            db = sqlite3.connect('spacecat.db')
            cursor = db.cursor()
            query = (ctx.guild.id, cmd_name)
            cursor.execute(f"SELECT command FROM command_aliases WHERE server_id=? AND alias=?", query)
            result = cursor.fetchall()
            db.close()

            # Use command linked to alias to replace command process
            if result:
                cmd.content = f"{prefix}{result[0][0]} {' '.join(cmd_args)}"
                await self.bot.process_commands(cmd)

    @commands.command()
    @perms.exclusive()
    async def status(self, ctx, statusname):
        config = toml.load('config.toml')
        status = status_class(statusname)
        try:
            activity = discord.Activity(type=activity_type_class(config['base']['activity_type']), name=config['base']['activity_name'])
        except KeyError:
            activity = None
        

        # Check if valid status name was used
        if status == None:
            embed = discord.Embed(colour=embed_type('warn'), description=f"That's not a valid status")
            await ctx.send(embed=embed)
            return

        if activity:
            await self.bot.change_presence(status=status, activity=activity)
        else:
            await self.bot.change_presence(status=status)

        config['base']['status'] = statusname
        with open("config.toml", "w") as config_file:
            toml.dump(config, config_file)

    @commands.command()
    @perms.exclusive()
    async def activity(self, ctx, acttype, *, name):
        config = toml.load('config.toml')
        activitytype = activity_type_class(acttype)
        activity = discord.Activity(type=activitytype, name=name, url="https://www.twitch.tv/yeet")
        try:
            status = config['base']['status']
        except KeyError:
            status = None

        if activitytype == None:
            embed = discord.Embed(colour=embed_type('warn'), description=f"That's not a valid activity type")
            await ctx.send(embed=embed)
            return

        if status:
            await self.bot.change_presence(activity=activity, status=status)
        else:
            await self.bot.change_presence(activity=activity)


        config['base']['activity_type'] = acttype
        config['base']['activity_name'] = name
        with open("config.toml", "w") as config_file:
            toml.dump(config, config_file)

    @commands.group()
    @perms.exclusive()
    async def permpreset(self, ctx):
        print('nah')

    @permpreset.command()
    @perms.exclusive()
    async def create(self, ctx):
        print('nah')

    @permpreset.command()
    @perms.exclusive()
    async def removed(self, ctx):
        print('nah')

    @permpreset.command()
    @perms.exclusive()
    async def append(self, ctx):
        print('nah')

    @permpreset.command()
    @perms.exclusive()
    async def truncate(self, ctx):
        print('nah')


def setup(bot):
    bot.add_cog(Configuration(bot))