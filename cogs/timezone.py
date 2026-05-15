from discord.ext import commands
from discord import app_commands

from services.timezone_service import TimezoneService, TIMEZONES
import discord

timezone_choices = [
    app_commands.Choice(name=timezone, value=timezone)
    for timezone in TIMEZONES
]

class TimezoneCog(commands.Cog):
    def __init__(self, bot, timezone_service: TimezoneService):
        self.bot = bot
        self.timezone_service = timezone_service

    @app_commands.command(name="timezone", description="Set a timezone")
    @app_commands.choices(timezone=timezone_choices)
    async def set_user_timezone(
            self,
            interaction: discord.Interaction,
            timezone: app_commands.Choice[str]
    ):
        await interaction.response.defer(ephemeral=True)# noqa

        self.timezone_service.set_user_timezone( interaction.user.id,timezone.value)

        await interaction.followup.send(f"Timezone set to {timezone.value}.",ephemeral=True)