import discord
from discord.ext import commands
import configparser
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

    @group.command()
    @perms.check()
    async def add(self, ctx, group: discord.Role, command):
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

        # Open server's config file
        config = configparser.ConfigParser()
        config.read('servers/' + str(ctx.guild.id) + '.ini')

        # Add permission to group if they don't already have the perm
        try:
            # Check group's existing perms
            group_perms = config['GroupPerms'][str(group.id)].split(',')
            if command in group_perms:
                await ctx.send("That group already has that permission")
                return

            # Add command to existing command list
            group_perms.append(command)
            config['GroupPerms'][str(group.id)] = ','.join(group_perms)
        except KeyError:
            # Add first command if group doesn't have existing perms
            config['GroupPerms'][str(group.id)] = command

        # Write to file and notify user of change
        await ctx.send(f"Command `{command}` added to group `{group.name}`")
        with open('servers/' + str(ctx.guild.id) + '.ini', 'w') as file:
                config.write(file)

    @group.command()
    @perms.check()
    async def remove(self, ctx, group: discord.Role, command):
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

        # Open server's config file
        config = configparser.ConfigParser()
        config.read('servers/' + str(ctx.guild.id) + '.ini')

        # Add permission to group if they don't already have the perm
        try:
            # Check group's existing perms
            group_perms = config['GroupPerms'][str(group.id)].split(',')
            if command in group_perms:
                group_perms.remove(command)
                config['GroupPerms'][str(group.id)] = ','.join(group_perms)
            else:
                raise KeyError
        except KeyError:
            # Notify user if group doesn't have permission
            await ctx.send("That group doesn't have that permission")
            return

        # Write to file and notify user of change
        await ctx.send(f"Command `{command}` removed from group `{group.name}`")
        with open('servers/' + str(ctx.guild.id) + '.ini', 'w') as file:
                config.write(file)

    @group.command()
    @perms.check()
    async def parent(self, ctx, group: discord.Role, command):
        await ctx.send("kek")

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
