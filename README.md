# SpaceCat Discord Bot

A magical, open source, self hostable, easy to use, general purpose, fully extensible discord bot running on Python.

## Requirements
-   [Python 3.6+](https://www.python.org/)
-   [discord.py](https://github.com/Rapptz/discord.py)
-   [youtube_dl](https://ytdl-org.github.io/youtube-dl/index.html)
-   [Pillow](https://pillow.readthedocs.io/en/stable/)
-   [toml](https://pypi.org/project/toml/)

How to install all other requirements after installing python:

`py -3 -m pip install -U discord.py[voice] youtube_dl pillow toml requests bs4`

Note: For MacOS/Linux, substitute `py -3` with `sudo python3`


## Running

### Windows
Open the terminal to the software root folder and type `spacecat.py`.

Alternatively, python can be called directly using `py -3 spacecat.py` or any other alternative alias

### MacOS & Linux
Open the terminal to the software root folder and run the software as a script `./spacecat.py`.

Alternatively, python can be called directly using `python3 spacecat.py` or any other alternative alias

## Installation
You'll go through this stuff when you run the program, don't worry.
### [Discord Bot Application API Key](https://discordapp.com/developers/applications/)
1. Create a new application and set a name.
2. Open the 'Bot' tab on the left.
3. Select 'Create a Bot' and confirm.
4. Click on 'Copy' under Token.
(Don't ever reveal this token to anyone you don't trust)

### Your Discord user ID
1. Open Discord.
2. Open your user settings.
3. Open the appearance tab.
4. Enable 'Developer Mode' under Advanced.
5. Exit user settings
6. Right click on your user and click "Copy ID"


## Inviting Bot to Server
Simply insert this link into your web browser and replace the placeholder with the **Client ID** from your discord application page.

https://discordapp.com/oauth2/authorize?client_id=PLACEHOLDER&scope=bot

The bot can be invited to servers you have admistrator permissions in.

