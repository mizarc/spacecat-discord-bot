#!/usr/bin/env python
import discord
from discord.ext import commands
import logging
import os
import glob
import configparser
import deps.perms as perms
from argparse import ArgumentParser

# Arguments for inputting API Key
parser = ArgumentParser()
parser.add_argument('-apikey', '-a', help='apikey help', type=str)
args = parser.parse_args()

# Set command prefix
bot = commands.Bot(command_prefix='!')

config = configparser.ConfigParser()


def main():
    os.system('cls' if os.name == 'nt' else 'clear')

    # Logging
    logger = logging.getLogger('discord')
    logger.setLevel(logging.DEBUG)
    handler = logging.FileHandler(filename='spacecat.log',
                                  encoding='utf-8', mode='w')
    handler.setFormatter(logging.Formatter(
        '%(asctime)s:%(levelname)s:%(name)s: %(message)s'))
    logger.addHandler(handler)

    # Load Modules
    modulelist = getmodules()
    loadedmodules = []
    for x in modulelist:
        module = 'modules.' + x
        try:
            bot.load_extension(module)
            loadedmodules.append(x)
        except Exception as e:
            exc = '{}: {}'.format(type(e).__name__, e)
            print("Failed to load extension {}\n{}\n".format(x, exc))

    print("Successfully loaded module(s): " + ', '.join(loadedmodules))

    # Run Config Check
    if not os.path.exists('config.ini'):
        noconfig()
    else:
        config.read('config.ini')

    # Append New APIKey to config
    if args.apikey is not None:
        config['Base']['APIKey'] = args.apikey
        with open('config.ini', 'w') as file:
            config.write(file)

    # Run Bot with API Key
    try:
        apikey = config['Base']['APIKey']
        print("Active API Key: " + apikey + "\n")
        bot.run(apikey)
    except discord.LoginFailure:
        print("""
        Invalid API key.
        Specify new key through argument or config file.
        Bot shutting down.
        """)


def noconfig():
    print("First Run Initiated")
    # Generate Config
    keyinput = input("Input your bot's API Key: ")
    config['Base'] = {}
    config['Base']['APIKey'] = keyinput
    with open('configasdf.ini', 'w') as file:
        config.write(file)


def getmodules():
    modulelist = []
    os.chdir('modules')
    for files in glob.glob('*.py'):
        modulelist.append(files[:-3])
    os.chdir('../')
    return modulelist


@bot.event
async def on_ready():
    print(bot.user.name + " has successfully launched")
    print(bot.user.id)
    print('--------------------')
    game = discord.Streaming(name="The Elder Scrolls VI",
                             url="https://www.twitch.tv/monstercat",
                             type=1)
    await bot.change_presence(activity=game)


@bot.command()
async def ping(ctx):
    """A simple command to check if the bot is working."""
    await ctx.send(bot.user.name + "is responding")


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
        await ctx.send("Reloaded all modules")
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


if __name__ == "__main__":
    main()
