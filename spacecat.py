#!/usr/bin/env python
import discord
import logging
import os
import glob
import configparser
import shutil
import time
import helpers.perms as perms
import helpers.perms
from discord.ext import commands
from argparse import ArgumentParser
from helpers.appearance import activity_type_class, status_class, embed_type, embed_icons

# Arguments for API key input
parser = ArgumentParser()
parser.add_argument('--apikey', '-a', help='apikey help', type=str)
parser.add_argument('--user', '-u', help='user help', type=str)
args = parser.parse_args()

# Set command prefix
bot = commands.Bot(command_prefix='!')

config = configparser.ConfigParser()
loadedmodules = []
firstrun = False

def main():
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
    for x in modulelist:
        module = 'modules.' + x
        try:
            bot.load_extension(module)
            loadedmodules.append(x)
        except Exception as e:
            exc = '{}: {}'.format(type(e).__name__, e)
            print("Failed to load extension {}\n{}\n".format(x, exc))

    # Run Config Check
    if not os.path.exists('config.ini'):
        createconfig()
    else:
        config.read('config.ini')
        run()

    # Append New APIKey to config
    if args.apikey is not None:
        config['Base']['APIKey'] = args.apikey
        with open('config.ini', 'w') as file:
            config.write(file)


def createconfig():
    # Just some info
    print("Hey there,")
    print("It appears that you don't have a configuration file.")
    print("Don't worry, I'll help you set one up in only 3 steps.")

    input("Press Enter to continue...")
    print('--------------------\n')
    time.sleep(1)

    # Generate Config
    print("[Step 1]")
    print("I'll need to get an API Key from your bot.")
    print("https://discordapp.com/developers/applications/\n")
    print("Open that link and follow these instructions:")
    print("""    1. Create a new application and set a name.
    2. Open the 'Bot' tab on the left.
    3. Select 'Create a Bot' and confirm.
    4. Click on 'Copy' under Token.
    (Don't ever reveal this token to anyone you don't trust)\n""")
    
    keyinput = input("Paste your token right here: ")
    print('--------------------\n')

    config['Base'] = {}
    config['Base']['APIKey'] = keyinput
    run(keyinput)


def run(key = None):
    # Run with key input on first run
    if key:
        apikey = key
        try:
            bot.run(apikey)
        except discord.LoginFailure:
            print("""Looks like that API key didn't work.
        Run the program again and use the correct key.""")
    # Run with key in the config
    else:
        try:
            apikey = config['Base']['APIKey']
            print("Active API Key: " + apikey + "\n")
            bot.run(apikey)
        except discord.LoginFailure:
            print("""   [Error]
        The API key doesn't work.
        Set a new key by running the bot again with the --apikey argument.
        Eg. ./spacecat --apikey <insert_key>""")

def getmodules():
    modulelist = []
    os.chdir('modules')
    for module in glob.glob('*.py'):
        if module == "__init__.py":
            continue
        modulelist.append(module[:-3])
    os.chdir('../')
    return modulelist


@bot.event
async def on_ready():
    if os.path.exists('config.ini'):
        print(bot.user.name + " has successfully launched")
        print(bot.user.id)
        print("Successfully loaded module(s): " + ', '.join(loadedmodules))
        print('--------------------')

        if not os.path.exists("spacecat.db"):
            perms.setup()

        statusname = config['Base']['status']
        status = status_class(statusname)

        try:
            acttypename = config['Base']['activity_type']
            activitytype = activity_type_class(acttypename)

            activity = discord.Activity(type=activitytype,
                                        name=config['Base']['activity_name'],
                                        url="https://www.twitch.tv/monstercat")
            await bot.change_presence(status=status, activity=activity)
        except (KeyError, TypeError):
            await bot.change_presence(status=status)
    else:
        while True:
            # Set a bot admin
            botname = bot.user.name
            print("[Step 2]")
            print(f"Alright, {botname} is now operational.")
            print("Now I'll need to get your discord user ID.")
            print("This will give you admin access to the bot through discord.")
            print("You can set more users later.\n")

            print("Here's what you need to do:")
            print("""    1. Open Discord.
    2. Open your user settings.
    3. Open the appearance tab.
    4. Enable 'Developer Mode' under Advanced.
    5. Exit user settings
    6. Right click on your user and click "Copy ID"\n""")

            idinput = input("Paste your ID right here: ")
            print('--------------------\n')
            
            try:
                user = bot.get_user(int(idinput))
                await user.send("Hello there!")
            except (ValueError, AttributeError):
                print("It looks like that is not a valid ID.")
                print("Lets try this again.")
                input("Press Enter to continue...")
                print('--------------------\n')
                time.sleep(1)
                continue

            time.sleep(1)
            
            print("You should've recieved a message from me through Discord.")
            confirminput = input("Type 'yes' if you have, or 'no' to set a new ID: ")
            print('--------------------\n')
            if confirminput == "yes":
                config['Base']['AdminUser'] = idinput
                break
            continue

        config['Base']['status'] = 'online'
        config['Base']['activity_type'] = ''
        config['Base']['activity_name'] = ''
        with open('config.ini', 'w') as file:
                config.write(file)
        time.sleep(1)

        # Join a server
        print("[Step 3]")
        
        print("Finally, I need to join your Discord server.")
        print("This is the easiest step.")
        print("Click the link below or copy it into your web browser.")

        botid = bot.user.id
        print(f"https://discordapp.com/oauth2/authorize?client_id={botid}&scope=bot&permissions=8")
        print('--------------------\n')


@bot.event
async def on_guild_join(guild):
    if os.path.exists('config.ini'):
        perms.new(guild)
    else:
        print("Congrats! I have now had my core functions set up")
        print("You may now use me, or continue to configure me through Discord.")
        print("Type !help for more info")
        print('--------------------\n')

        with open('config.ini', 'w') as file:
            config.write(file)


# Commands
@bot.command()
@perms.check()
async def ping(ctx):
    """A simple command to check if the bot is working."""
    embed = discord.Embed(colour=embed_type('accept'), description=f"{bot.user.name} is operational at {int(bot.latency * 1000)}ms")
    await ctx.send(embed=embed)


@bot.command()
@perms.exclusive()
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
                embed = discord.Embed(colour=embed_type('warn'), description=f"Failed to reload module {module}. Reloading has stopped.")
                await ctx.send(embed=embed)
                return
        embed = discord.Embed(colour=embed_type('accept'), description=f"Reloaded all modules successfully")
        await ctx.send(embed=embed)
        return
    try:
        z = 'modules.' + module
        bot.unload_extension(z)
        bot.load_extension(z)
        embed = discord.Embed(colour=embed_type('accept'), description=f"Reloaded module {module} successfully")
    except ModuleNotFoundError:
        embed = discord.Embed(colour=embed_type('warn'), description=f"{module} is not a valid module")
    except Exception:
        embed = discord.Embed(colour=embed_type('warn'), description=f"Failed to load module {module}")
    await ctx.send(embed=embed)


@bot.command()
@perms.exclusive()
async def exit(ctx):
    """Shuts down the bot."""
    try:
        shutil.rmtree('cache')
    except:
        pass
    
    await bot.logout()


if __name__ == "__main__":
    main()
