import configparser
import sqlite3

import discord
from discord.ext import commands

from helpers.dataclasses import activity_type_class, status_class
import helpers.perms as perms

class Configuration(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.config = configparser.ConfigParser()

    @commands.command()
    @perms.exclusive()
    async def status(self, ctx, statusname):
        self.config.read('config.ini')
        activity = discord.Activity(type=activity_type_class(self.config['Base']['activity_type']), name=self.config['Base']['activity_name'])
        status = status_class(statusname)

        if status == None:
            await ctx.send("That's not a valid status")
            return

        print(status)
        await self.bot.change_presence(status=status, activity=activity)

        self.config['Base']['status'] = statusname
        with open('config.ini', 'w') as file:
            self.config.write(file)

    @commands.command()
    @perms.exclusive()
    async def activity(self, ctx, acttype, *, name):
        self.config.read('config.ini')
        activitytype = activity_type_class(acttype)
        activity = discord.Activity(type=activitytype, name=name, url="https://www.twitch.tv/yeet")

        if activitytype == None:
            await ctx.send("That's not a valid activity type")
            return

        await self.bot.change_presence(activity=activity, status=self.config['Base']['status'])

        self.config['Base']['activity_type'] = acttype
        self.config['Base']['activity_name'] = name
        with open('config.ini', 'w') as file:
            self.config.write(file)

    @commands.group()
    @perms.check()
    async def perm(self, ctx):
        """Configure server permissions"""
        if ctx.invoked_subcommand is None:
            await ctx.send("Please specify a subcommand. Group/User")
    
    @perm.group()
    @perms.check()
    async def group(self, ctx):
        """Configure server permissions"""
        if ctx.invoked_subcommand is None:
            await ctx.send("Please specify a subcommand. Add/Remove/Parent/Unparent")

    @group.command(name='add')
    @perms.check()
    async def addgroup(self, ctx, group: discord.Role, command):
        # Loop through command list and check if command exists
        command_exists = False
        for bot_command in ctx.bot.commands:
            if command == bot_command.name:
                command_exists = True
                break

        # Notify user if command does not exist
        if not command_exists:
            await ctx.send("That command does not exist")
            return

        # Query database for 
        db = sqlite3.connect('spacecat.db')
        cursor = db.cursor()
        group_perms = cursor.execute(
            'SELECT perm FROM group_permissions WHERE groupid=' + str(group.id))

        # Add permission to group if they don't already have the perm
        if command in group_perms:
            await ctx.send("That group already has that permission")
            return
        cursor.execute("INSERT INTO group_permissions VALUES (" + str(ctx.guild.id) + ',' + str(group.id) + ", '" + command + "')")
        
        # Write to file and notify user of change
        await ctx.send(f"Command `{command}` added to group `{group.name}`")
        db.commit()
        db.close()

    @group.command(name='remove')
    @perms.check()
    async def removegroup(self, ctx, group: discord.Role, command):
        # Check if command exists
        command_exists = False
        for bot_command in ctx.bot.commands:
            if command == bot_command.name:
                command_exists = True
                break

        # Notify user if command doesn't exist
        if not command_exists:
            await ctx.send("That command does not exist")
            return

        # Query database for group permissions
        db = sqlite3.connect('spacecat.db')
        cursor = db.cursor()
        cursor.execute(
            "SELECT perm FROM group_permissions WHERE groupid=" + str(group.id) + " AND perm='" + command + "'")
        group_perms = cursor.fetchall()
        
        # Notify user if group doesn't have the permission
        if not group_perms:
            await ctx.send("That group doesn't have that permission")
            return
        
        # Remove permission from database and notify user
        cursor.execute("DELETE FROM group_permissions WHERE groupid=" + str(group.id) + " AND perm='" + command + "'")
        await ctx.send(f"Command `{command}` added to group `{group.name}`")
        db.commit()
        db.close()

    @group.command()
    @perms.check()
    async def parent(self, ctx, child_group: discord.Role, parent_group: discord.Role):
        # Open server's config file
        config = configparser.ConfigParser()
        config.read('servers/' + str(ctx.guild.id) + '.ini')

    @perm.group()
    @perms.check()
    async def user(self, ctx):
        """Configure server permissions"""
        if ctx.invoked_subcommand is None:
            await ctx.send("Please specify a subcommand. Add/Remove/Parent/Unparent")

    @user.command(name='add')
    @perms.check()
    async def adduser(self, ctx, user: discord.User, command):
        # Loop through command list and check if command exists
        command_exists = False
        for bot_command in ctx.bot.commands:
            if command == bot_command.name:
                command_exists = True
                break

        # Send message if command does not exist
        if not command_exists:
            await ctx.send("That command does not exist")
            return

        # Open server's database file
        db = sqlite3.connect('spacecat.db')
        cursor = db.cursor()

        # Query 
        user_perms = cursor.execute(
            'SELECT perm FROM user_permissions WHERE userid=' + str(user.id))

        # Add permission to group if they don't already have the perm
        if command in user_perms:
            await ctx.send("That user already has that permission")
            return
        cursor.execute("INSERT INTO user_permissions VALUES (" + str(ctx.guild.id) + ',' + str(user.id) + ", '" + command + "')")
        
        # Write to file and notify user of change
        await ctx.send(f"Command `{command}` added to group `{user.name}`")
        db.commit()
        db.close()

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
