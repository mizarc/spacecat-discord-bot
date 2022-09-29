# SpaceCat Discord Bot

The official source code of the Magic Space Cat Discord bot. Everything here is readily available if you want to host your own instance, with full commands and permission customisation.

Official bot invite: https://discord.com/api/oauth2/authorize?client_id=503580226035384340&permissions=8&scope=bot

## Requirements
-   [Python 3.7+](https://www.python.org/)
-   [Opus](https://www.opus-codec.org/)
-   [FFmpeg](https://www.ffmpeg.org/)

## Installation
1. Open a terminal to the root directory of this project.
2. Run `python -m pip install .` (Yes the dot is part of the command)
3. That's it.

## Running
1. Navigate to any directory on your filesystem to store bot data in.
2. Run `python -m spacecat`.
3. Follow the instructions.

## Setup
You'll go through this stuff when you run the program, don't worry.

### [Bot API Key](https://discordapp.com/developers/applications/)
1. Create a new application and set a name.
2. Open the 'Bot' tab on the left.
3. Select 'Create a Bot' and confirm.
4. Click on 'Copy' under Token.
(Don't ever reveal this token to anyone you don't trust)

### Your Discord User ID
1. Open Discord.
2. Open your user settings.
3. Open the appearance tab.
4. Enable 'Developer Mode' under Advanced.
5. Exit user settings.
6. Right click on your user and click "Copy ID".

## Music
To make use of the Musicbox module in order to stream songs from sources such as YouTube or Spotify, you must set up a
Lavalink server. This is an efficient audio playback server that the module is designed to interface with. A reworked 
built-in solution may be implemented at a later date, but will likely still not be as performant as Lavalink.

Here are some steps to set it all up:
1. Install a minimum of [Java 13](https://www.azul.com/downloads/?package=jdk#download-openjdk).
2. Download [Lavalink](https://github.com/freyacodes/Lavalink/releases) from GitHub and save it to a known location.
3. Create a file called `application.yml` with the contents of [this example]
(https://github.com/freyacodes/Lavalink/blob/master/LavalinkServer/application.yml.example)
4. Find the line labelled "password" and set it to your own secure password.
5. Run Lavalink using Java with the command `java -jar Lavalink.jar`.
6. Ensure that SpaceCat Discord Bot has been run at least once, and an instance has been created.
7. Navigate to data/\<instance name> in the SpaceCat files.
8. Open the config and edit the IP address, port, and password of the Lavalink server. 
(Default IP of 0.0.0.0 works if the Lavalink server is on the same computer as SpaceCat)
9. Restart the bot and have fun!

## Inviting Bot to Server
The bot can be invited to servers you have admistrator permissions in.

### [Official Method](https://discordapp.com/developers/applications/)
1. Select your bot.
2. Open the 'OAuth2' tab on the left.
3. Select 'bot' in the scopes category.
4. Select the permissions that you want your bot to have.
5. Copy the link.

### Alternate Method
Simply insert this link into your web browser and replace the placeholder with the **Client ID** from your discord application page. This link allows the bot to have full control over the server, which may have certain security and trust issues.

https://discord.com/api/oauth2/authorize?client_id=PLACEHOLDER&permissions=8&scope=bot
