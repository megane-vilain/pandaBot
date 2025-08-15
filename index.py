from utils.logging_config import init_logging
from dotenv import load_dotenv
import discord
import os


def main():
    load_dotenv()
    init_logging()

    bot = discord.Bot(intents=discord.Intents.default())

    @bot.event
    async def on_ready():
        print(f"{bot.user} is online!")
        await bot.sync_commands()  # Automatically sync all slash commands

    bot.load_extension('cogs.misc')
    bot.load_extension('cogs.api_call')
    bot.load_extension('cogs.reminders')
    bot.run(os.getenv('TOKEN'))

if __name__ == "__main__":
    main()