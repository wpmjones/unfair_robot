import asyncio
import coc
import discord
import git
import os
import sys
import traceback

from discord.ext import commands
from cogs.utils import context
from cogs.utils.db import Table
from datetime import datetime
from loguru import logger
from config import settings

enviro = "home"

initial_extensions = ["cogs.general",
                      "cogs.admin",
                      "cogs.push",
                      ]

if enviro == "LIVE":
    token = settings['discord']['token']
    prefix = "+"
    log_level = "INFO"
    coc_names = "uw"
elif enviro == "home":
    token = settings['discord']['token']
    prefix = "+"
    log_level = "INFO"
    coc_names = "ubuntu"
else:
    token = settings['discord']['testing']
    prefix = ">"
    log_level = "DEBUG"
    coc_names = "dev"

description = ("Unfair Robot welcomes you to his laboratory.\n"
               "All commands must begin with a plus.\n"
               "Proudly maintained by TubaKid.\n\n")


class CustomClient(coc.EventsClient):
    def _create_status_tasks(self, cached_war, war):
        if cached_war.state != war.state:
            self.dispatch("on_war_state_change", war.state, war)

        super()._create_status_tasks(cached_war, war)


coc_client = coc.login(settings['cocpy']['user'],
                       settings['cocpy']['pass'],
                       client=CustomClient,
                       key_names=coc_names,
                       key_count=4,
                       throttle_limit=35,
                       correct_tags=True)


class Robot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix=prefix,
                         description=description,
                         case_insensitive=True)
        self.coc = coc_client
        self.logger = logger
        self.color = discord.Color.dark_red()
        self.loop.create_task(self.after_ready())

        for extension in initial_extensions:
            try:
                self.load_extension(extension)
                self.logger.debug(f"{extension} loaded successfully")
            except Exception as extension:
                self.logger.error(f"Failed to load extenstion {extension}.", file=sys.stderr)
                traceback.print_exc()

    @property
    def log_channel(self):
        return self.get_channel(settings['channels']['log'])

    async def send_message(self,  message):
        if len(message) > 1999:
            message = message[:1975]
        await self.log_channel.send(f"`{message}`")

    def send_log(self, message):
        asyncio.ensure_future(self.send_message(message))

    async def on_message(self, message):
        if message.author.bot:
            return
        await self.process_commands(message)

    async def process_commands(self, message):
        ctx = await self.get_context(message, cls=context.Context)
        if ctx.command is None:
            return
        async with ctx.acquire():
            await self.invoke(ctx)

    async def on_command_error(self, ctx, error):
        if isinstance(error, commands.NoPrivateMessage):
            await ctx.author.send("This command cannot be used in private messages.")
        elif isinstance(error, commands.DisabledCommand):
            await ctx.author.send("Oops. This command is disabled and cannot be used.")
        elif isinstance(error, commands.CommandInvokeError):
            original = error.original
            if not isinstance(original, discord.HTTPException):
                self.logger.error(f"In {ctx.command.qualified_name}:", file=sys.stderr)
                traceback.print_tb(original.__traceback__)
                self.logger.error(f"{original.__class__.__name__}: {original}", file=sys.stderr)
        elif isinstance(error, commands.ArgumentParsingError):
            await ctx.send(error)

    async def on_error(self, event_method, *args, **kwargs):
        e = discord.Embed(title="Discord Event Error", color=0xa32952)
        e.add_field(name="Event", value=event_method)
        e.description = f"```py\n{traceback.format_exc()}\n```"
        e.timestamp = datetime.utcnow()

        args_str = ["```py"]
        for index, arg in enumerate(args):
            args_str.append(f"[{index}]: {arg!r}")
        args_str.append("```")
        e.add_field(name="Args", value="\n".join(args_str), inline=False)
        try:
            await self.log_channel.send(embed=e)
        except:
            pass

    async def on_ready(self):
        activity = discord.Game(" with your mind")
        await bot.change_presence(activity=activity)

    async def after_ready(self):
        await self.wait_until_ready()
        logger.add(self.send_log, level=log_level)

    async def close(self):
        await super().close()
        await self.coc.close()


if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    try:
        pool = loop.run_until_complete(Table.create_pool(settings['pg']['uri_home'], max_size=15))
        bot = Robot()
        bot.pool = pool
        bot.repo = git.Repo(os.getcwd())
        bot.loop = loop
        bot.run(token, reconnect=True)
    except:
        traceback.print_exc()
