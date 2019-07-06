from discord.ext import commands


async def on_command_error(ctx, error):
    printerror = ("`" + str(error) + "`")
    if isinstance(error, commands.MissingPermissions):
        await ctx.send(printerror)
