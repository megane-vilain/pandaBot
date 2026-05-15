from tinydb import TinyDB

from cogs.reminders import ReminderCog
from cogs.timezone import TimezoneCog
from services.reminder_service import ReminderService
from services.timezone_service import TimezoneService
from utils.logging_config import init_logging
from discord.ext import commands
import discord
import asyncio
import os


async def main():
    init_logging()

    intents = discord.Intents.default()
    bot = commands.Bot(command_prefix="/", intents=intents)

    db = TinyDB('panda_bot.json')
    timezones_table = db.table('timezones')
    timezone_service = TimezoneService(timezones_table)

    reminders_table = db.table('reminders')
    reminder_service = ReminderService(reminders_table)

    @bot.event
    async def on_ready():
        print(f"{bot.user} is online!")
        await bot.tree.sync()


    async with bot:
        await bot.load_extension('cogs.misc')
        await bot.add_cog(ReminderCog(bot, timezone_service, reminder_service))
        await bot.add_cog(TimezoneCog(bot, timezone_service))
        await bot.load_extension('cogs.garland')

        await bot.start(os.getenv('TOKEN'))

if __name__ == "__main__":
    asyncio.run(main())