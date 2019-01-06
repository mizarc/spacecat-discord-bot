import discord
from discord.ext import commands
import logging
import os
import glob
import configparser
import deps.perms as perms


# Logging
logger = logging.getLogger('discord')
logger.setLevel(logging.DEBUG)
handler = logging.FileHandler(filename="spacecat.log",
                              encoding="utf-8", mode="w")
handler.setFormatter(logging.Formatter(
    '%(asctime)s:%(levelname)s:%(name)s: %(message)s'))
logger.addHandler(handler)


# Generate Config
if os.path.isfile('./config.ini'):
    config = configparser.ConfigParser()
    config['Base'] = {'APIKey': ''}
    with open('config.ini', 'w') as file:
        config.write(file)


bot = commands.Bot(command_prefix="!")


@bot.event
async def on_ready():
    print(bot.user.name + ' has successfully launched')
    print(bot.user.id)
    print('--------------------')
    game = discord.Streaming(name='The Elder Scrolls VI',
                             url='https://www.twitch.tv/monstercat',
                             type=1)
    await bot.change_presence(activity=game)


@bot.command()
async def ping(ctx):
    """A simple command to check if the bot is working."""
    await ctx.send('Magic Space Cat is responding')


@bot.command()
@perms.admin()
async def reload(ctx, module=None):
    """Reloads all or specified module"""
    if module is None:
        modulelist = getmodules()
        for y in modulelist:
            try:
                z = 'modules.' + y
                bot.unload_extension(z)
                bot.load_extension(z)
            except Exception:
                await ctx.send("Failed to load module '" + y
                               + "'. Reloading has stopped.")
                return
        await ctx.send('Reloaded all modules')
        return
    try:
        z = 'modules.' + module
        bot.unload_extension(z)
        bot.load_extension(z)
        await ctx.send("Reloaded module '" + module + "'")
    except ModuleNotFoundError:
        await ctx.send("'" + module + "' is not a valid module")
    except Exception:
        await ctx.send("Failed to load module '" + module + "'")


@bot.command()
@perms.admin()
async def exit():
    """Shuts down the bot."""
    await bot.logout()


def getmodules():
    modulelist = []
    os.chdir("modules")
    for files in glob.glob("*.py"):
        modulelist.append(files[:-3])
    os.chdir("../")
    return modulelist


if __name__ == "__main__":
    modulelist = getmodules()
    for x in modulelist:
        module = 'modules.' + x
        try:
            bot.load_extension(module)
            print('Successfully loaded ' + module)
        except Exception as e:
            exc = '{}: {}'.format(type(e).__name__, e)
            print('Failed to load extension {}\n{}'.format(x, exc))

    config = configparser.ConfigParser()
    config.read('config.ini')
    apikey = config['Base']['APIKey']
    bot.run(apikey)
