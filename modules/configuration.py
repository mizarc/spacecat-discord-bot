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
        # Query database to check if the group has the permission already
        perm = await self._perm_query(ctx, 'group', group.id, command)
        if perm is None:
            return
        elif perm is True:
            await ctx.send("That group already has that permission")
            return 
        
        # Append permission to database and notify user
        db = sqlite3.connect('spacecat.db')
        cursor = db.cursor()
        values = (ctx.guild.id, group.id, command)
        cursor.execute("INSERT INTO group_permissions VALUES (?,?,?)", values)
        await ctx.send(f"Command `{command}` added to group `{group.name}`")
        db.commit()
        db.close()

    @group.command(name='remove')
    @perms.check()
    async def removegroup(self, ctx, group: discord.Role, command):
        # Query database to check if the group has the permission already
        perm = await self._perm_query(ctx, 'group', group.id, command)
        if perm is None:
            return
        elif perm is False:
            await ctx.send("That group doesn't have that permission")
            return
        
        # Remove permission from database and notify user
        db = sqlite3.connect('spacecat.db')
        cursor = db.cursor()
        query = (ctx.guild.id, group.id, command)
        cursor.execute("DELETE FROM group_permissions WHERE serverid=? AND groupid=? AND perm=?", query)
        await ctx.send(f"Command `{command}` removed from group `{group.name}`")
        db.commit()
        db.close()

    @group.command()
    @perms.check()
    async def parent(self, ctx, child_group: discord.Role, parent_group: discord.Role):
        # Open server's config file
        check = await self._parent_query(ctx, child_group.id, parent_group.id)
        if check:
            await ctx.send("Cannot add parent to group as selected parent is already a parent of group")
            return

        # Query database to check if parent is a child of group
        db = sqlite3.connect('spacecat.db')
        cursor = db.cursor()
        query = (parent_group, child_group)
        cursor.execute("SELECT child_group FROM group_parents WHERE child_group=? AND parent_group=?", query)
        check = cursor.fetchall()
        if check:
            db.close()
            await ctx.send("Cannot add parent to group as selected parent is a child of group")        
            return

        # Remove permission from database and notify user
        values = (ctx.guild.id, child_group.id, parent_group.id)
        cursor.execute("INSERT INTO group_parents VALUES (?,?,?)", values)
        await ctx.send(f"`{child_group.name}` now inherits permissions from `{parent_group.name}`")
        db.commit()
        db.close()

    @group.command()
    @perms.check()
    async def unparent(self, ctx, child_group: discord.Role, parent_group: discord.Role):
        # Open server's config file
        check = await self._parent_query(ctx, child_group.id, parent_group.id)
        if not check:
            await ctx.send("Cannot remove parent from group as selected parent isn't a parent of group")
            return

        # Remove permission from database and notify user
        db = sqlite3.connect('spacecat.db')
        cursor = db.cursor()
        values = (ctx.guild.id, child_group.id, parent_group.id)
        cursor.execute("DELETE FROM group_parents WHERE serverid=? AND child_group=? AND parent_group=?", values)
        await ctx.send(f"`{child_group.name}` is no longer inheriting permissions from `{parent_group.name}`")
        db.commit()
        db.close()

    @perm.group()
    @perms.check()
    async def user(self, ctx):
        """Configure server permissions"""
        if ctx.invoked_subcommand is None:
            await ctx.send("Please specify a subcommand. Add/Remove/Parent/Unparent")

    @user.command(name='add')
    @perms.check()
    async def adduser(self, ctx, user: discord.User, command):
        # Query database to check if the user has the permission already
        perm = await self._perm_query(ctx, 'user', user.id, command)
        if perm is None:
            return
        elif perm is True:
            await ctx.send("That user already has that permission")
            return 

        # Append permission to database and notify user
        db = sqlite3.connect('spacecat.db')
        cursor = db.cursor()
        values = (ctx.guild.id, user.id, command)
        cursor.execute("INSERT INTO user_permissions VALUES (?,?,?)", values)
        await ctx.send(f"Command `{command}` added to group `{user.name}`")
        db.commit()
        db.close()

    @user.command(name='remove')
    @perms.check()
    async def removeuser(self, ctx, user: discord.User, command):
        # Query database to check if the user has the permission already
        perm = await self._perm_query(ctx, 'user', user.id, command)
        if perm is None:
            return
        elif perm is False:
            await ctx.send("That user doesn't have that permission")
            return 

        # Append permission to database and notify user
        db = sqlite3.connect('spacecat.db')
        cursor = db.cursor()
        query = (ctx.guild.id, group.id, command)
        cursor.execute("DELETE FROM user_permissions WHERE serverid=? AND userid=? AND perm=?", query)
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

    async def _perm_query(self, ctx, type_, id_, command):
        # Loop through command list and check if command exists
        command_exists = False
        for bot_command in ctx.bot.commands:
            if command == bot_command.name:
                command_exists = True
                break

        # Send message if command does not exist
        if not command_exists:
            await ctx.send("That command does not exist")
            return None

        # Query database for group permissions
        db = sqlite3.connect('spacecat.db')
        cursor = db.cursor()
        query = (id_, command)
        cursor.execute(f"SELECT perm FROM {type_}_permissions WHERE {type_}id=? AND perm=?", query)
        result = cursor.fetchall()
        db.close()
        if result:
            return True
        return False

    async def _parent_query(self, ctx, child, parent):
        # Query database to check if group already has the parent
        db = sqlite3.connect('spacecat.db')
        cursor = db.cursor()
        query = (child, parent)
        cursor.execute("SELECT parent_group FROM group_parents WHERE child_group=? AND parent_group=?", query)
        result = cursor.fetchall()
        if result:
            db.close()
            return True

        db.close()
        return False



def setup(bot):
    bot.add_cog(Configuration(bot))
