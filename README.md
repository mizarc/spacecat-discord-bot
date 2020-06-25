# SpaceCat Discord Bot

The official source code of the Magic Space Cat Discord bot. Everything here is readily available if you want to host your own instance, with full commands and permission customsation.

Official bot invite: https://discord.com/api/oauth2/authorize?client_id=503580226035384340&permissions=8&scope=bot

## Requirements
-   [Python 3.7+](https://www.python.org/)
-   [Opus](https://www.opus-codec.org/)
-   [FFmpeg](https://www.ffmpeg.org/)

## Installation
1. Open a terminal to the root directory of this project
2. Run `python -m pip install .`. That's it.

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