from discord.ext import commands
from discord import app_commands
import discord
import random


class Misc(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="hello", description="Say hello to the bot")
    async def hello(self, interaction: discord.Interaction):
        await interaction.response.send_message(f"Hello {interaction.user.mention}!")

    @app_commands.command(name="roll", description="Roll between 1 and 100")
    async def roll(self, interaction: discord.Interaction):
        await interaction.response.send_message(random.randint(1, 100))

# This is required so the bot can load the cog
async def setup(bot):
    await bot.add_cog(Misc(bot))