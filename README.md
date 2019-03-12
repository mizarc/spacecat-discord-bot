# SpaceCat Discord Bot

An open source self hostable discord bot.

## Requirements

-   Python 3.5.3+
-   [discord.py Rewrite](https://github.com/Rapptz/discord.py/tree/rewrite)
    -   `python3 -m pip install -U https://github.com/Rapptz/discord.py/archive/rewrite.zip#egg=discord.py[voice]`
-   [Discord Bot Application API Key](https://discordapp.com/developers/applications/)
    1. Create an application
    2. Open 'Bot' tab
    3. Create a bot
    4. Reveal token


## Inviting Bot to Server
Simply insert this link into your web browser and replace the placeholder with the **Client ID** from your discord application page.

https://discordapp.com/oauth2/authorize?client_id=PLACEHOLDER&scope=bot

The bot can be invited to servers you have admistrator permissions in.

## Running

### Windows
Open the terminal to the software root folder and type `spacecat.py`.

### MacOS & Linux
Open the terminal to the software root folder and run the software as a script `./spacecat.py`.

Alternatively, python can be called directly using `python3 spacecat.py` or any other alternative alias
