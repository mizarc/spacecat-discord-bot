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
    @perms.exclusive()
    async def permpreset(self, ctx)
        print('nah')

    @permpreset.command()
    @perms.exclusive()
    async def create(self, ctx)
        print('nah')

    @permpreset.command()
    @perms.exclusive()
    async def remove(self, ctx)
        print('nah')

    @permpreset.command()
    @perms.exclusive()
    async def append(self, ctx)
        print('nah')

    @permpreset.command()
    @perms.exclusive()
    async def truncate(self, ctx)
        print('nah')



def setup(bot):
    bot.add_cog(Configuration(bot))
