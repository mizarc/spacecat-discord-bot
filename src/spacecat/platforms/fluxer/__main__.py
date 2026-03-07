import fluxer

bot = fluxer.Bot(command_prefix="!", intents=fluxer.Intents.default())


@bot.event
async def on_ready():
    print(f"Bot is ready! Logged in as {bot.user.username}")


@bot.command()
async def ping(ctx):
    await ctx.reply("Pong!")


if __name__ == "__main__":
    TOKEN = "1478053375523042194.VZG2ZWZNo7XlQEKRF6j0Ff0LHnMrxFZZ_Lx9THQGJt4"
    bot.run(TOKEN)