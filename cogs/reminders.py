from discord import app_commands
from dateutil.parser import ParserError
from discord.ext import commands, tasks
from dateutil import parser as dateutil_parser
from dateutil.tz import gettz
from datetime import UTC, tzinfo
from models import Reminder
from services.reminder_service import ReminderService
from services.timezone_service import TimezoneService
import discord
import logging
import dateparser

D_M_Y_M_H_FORMAT = "%d/%m/%y %H:%M"

class ReminderDropdown(discord.ui.Select):
    def __init__(self, reminders: list[Reminder]):
        options = []
        for reminder in reminders:
            label = reminder.message[:50]
            if reminder.repeat:
                prefix = "🔁"
            else:
                prefix = "📅"
            options.append(
                discord.SelectOption(
                    label=f"{prefix} {reminder.remind_at} - {label}",
                    value=str(reminder.doc_id)
                )
            )
            super().__init__(
                placeholder="Select a reminder to delete",
                min_values=1,
                max_values=1,
                options=options
            )


    async def callback(self,
                       interaction: discord.Interaction):
        for child in self.view.children:
            child.disabled = True
        # Edit the original message to reflect the disabled view
        await interaction.response.edit_message(content="✅ Reminder deleted.", view=self.view)# noqa

        doc_id = int(self.values[0])
        self.view.selected_doc_id = doc_id
        self.view.stop()


class ReminderView(discord.ui.View):
    def __init__(self, reminders):
        super().__init__(timeout=120)
        self.add_item(ReminderDropdown(reminders))
        self.selected_doc_id = None


class ReminderCog(commands.Cog):
    def __init__(self, bot, timezone_service: TimezoneService, reminder_service: ReminderService):
        self.bot = bot
        self.timezone_service = timezone_service
        self.reminder_service = reminder_service
        self.check_reminders.start()

    @staticmethod
    def parse_datetime_to_utc(time_str: str, user_timezone_str: str):
        """
        Parse a string into a UTC datetime given a timezone.
        :param time_str: The string to parse.
        :param user_timezone_str: The pytz timezone
        :return: The UTC datetime parsed.
        """
        try:
            date = dateparser.parse(time_str, settings={# noqa
                'TIMEZONE': user_timezone_str,
                'RETURN_AS_TIMEZONE_AWARE': True}
            )
            return date.astimezone(UTC)
        except (TypeError, ValueError, ParserError) as e:
            logging.error(f"Error parsing datetime {time_str}: {e}")
            return None

    @staticmethod
    def parse_datetime_to_tz(time_str: str, tz: tzinfo):
        """
        Convert to the timezone and returns the date formatted.
        :param time_str: The string to parse.
        :param tz: The pytz timezone
        :return: The date formatted.
        """
        try:
            local_dt = dateutil_parser.parse(time_str)
            local_dt = local_dt.replace(tzinfo=UTC)
            converted_dt = local_dt.astimezone(tz)
            return converted_dt.strftime(D_M_Y_M_H_FORMAT)
        except (TypeError, ValueError, ParserError) as e:
            logging.error(f"Error parsing datetime {time_str}: {e}")
            return None

    @app_commands.describe(time="When to remind you (Format: mm/dd/yy hh:mm)")
    @app_commands.describe(message="The reminder message")
    @app_commands.describe(repeat="The reminder message")
    @app_commands.command(name="remindme", description="Set a reminder")
    async def remindme(self, interaction: discord.Interaction,time: str, message: str,repeat: bool = False):
        await interaction.response.defer(ephemeral=True)# noqa

        user_timezone_str = self.timezone_service.get_user_timezone(interaction.user.id)
        if not user_timezone_str:
            await interaction.followup.send("You need to set you timezone, by using the timezone command", ephemeral=True)
            return

        utc_dt = self.parse_datetime_to_utc(time, user_timezone_str)
        if not utc_dt:
            await interaction.followup.send(f"Could not parse date/time {time} . Use format: `MM/DD/YY HH:MM TZ`")
            return

        reminder = Reminder(
            user_id= interaction.user.id,
            channel_id= interaction.channel_id,
            remind_at= utc_dt.isoformat(),
            message= message,
            repeat= repeat
        )

        self.reminder_service.create_reminder(reminder)
        time_str = utc_dt.strftime(D_M_Y_M_H_FORMAT)
        await interaction.followup.send(f"Reminder set for {time_str}.")


    @app_commands.command(name="list_reminder", description="List active reminders")
    async def list_reminders(self, interaction: discord.Interaction):
        timezone_str = self.timezone_service.get_user_timezone(interaction.user.id)
        reminders = self.reminder_service.get_user_reminders(interaction.user.id)

        if not reminders:
            await interaction.response.send_message("No reminders found", ephemeral=True)# noqa
            return

        for reminder in reminders:
            reminder.remind_at = self.parse_datetime_to_tz(reminder.remind_at, gettz(timezone_str))


        view = ReminderView(reminders)
        await interaction.response.send_message("Select a reminder to delete:", view=view, ephemeral=True)# noqa
        await view.wait()

        if view.selected_doc_id:
            self.reminder_service.delete_reminder(view.selected_doc_id)
            await interaction.followup.send("Reminder deleted.", ephemeral=True)# noqa

    @tasks.loop(seconds=10)
    async def check_reminders(self):
        reminders = self.reminder_service.get_due_reminders()
        for reminder in reminders:
            channel = self.bot.get_channel(reminder.channel_id)
            if channel:
                try:
                    user = await self.bot.fetch_user(reminder.user_id)
                    await channel.send(f"{user.mention} ⏰ Reminder: {reminder.message}")
                except Exception as e:
                    logging.error(f"Failed to send reminder {reminder.message} for user {reminder.user_id}: {e}")

            if reminder.repeat:
                self.reminder_service.repeat_reminder(reminder.doc_id)
            else:
                # Remove sent reminder
                self.reminder_service.delete_reminder(reminder.doc_id)


    def cog_unload(self) -> None:
        self.check_reminders.cancel()