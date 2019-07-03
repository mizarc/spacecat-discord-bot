import discord
from discord.ext import commands


class Configuration(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def status(self, ctx, input):
        if input == "online":
            await self.bot.change_presence(status=discord.Status.online)
        elif input == "idle":
            await self.bot.change_presence(status=discord.Status.idle)
        elif input == "dnd":
            await self.bot.change_presence(status=discord.Status.dnd)
        elif input == "invisible" or input == "offline":
            await self.bot.change_presence(status=discord.Status.invisible)
        else:
            await ctx.send("That's how a valid status")

    @commands.command()
    async def activity(self, ctx, acttype, *, name):
        activity = discord.Activity(name = name, url = "https://www.twitch.tv/yeet")

        if acttype == "playing":
            activity.type = discord.ActivityType.playing
        elif acttype == "streaming":
            activity.type = discord.ActivityType.streaming
        elif acttype == "listening":
            activity.type = discord.ActivityType.listening
        elif acttype == "watching":
            activity.type = discord.ActivityType.watching
        else:
            await ctx.send("Invalid Activity Type")

        await self.bot.change_presence(activity=activity)


def setup(bot):
    bot.add_cog(Configuration(bot))
