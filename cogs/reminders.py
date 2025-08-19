from tinydb import TinyDB, Query
from dateutil.parser import ParserError
from discord.ext import commands, tasks
from dateutil import parser as date_parser
from dateutil.tz import gettz
from datetime import UTC, datetime, timedelta, tzinfo
from models import Reminder, Timezone
from utils.db_utils import document_to_dataclass, dataclass_to_document
import discord
import logging

M_D_Y_M_H_FORMAT = "%m/%d/%y %H:%M"

TIMEZONES = {  # British Summer Time
    "GMT": gettz("Europe/London"),
    "CET": gettz("Europe/Paris")
}
DEFAULT_TIMEZONE = "UTC"

# Create a list of discord.OptionChoice
timezone_choices = [
    discord.OptionChoice(name=f"{abbr} ({name})", value=abbr)
    for abbr, name in TIMEZONES.items()
]


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
        await interaction.response.edit_message(content="✅ Reminder deleted.", view=self.view)

        doc_id = int(self.values[0])
        self.view.selected_doc_id = doc_id
        self.view.stop()


class ReminderView(discord.ui.View):
    def __init__(self, reminders):
        super().__init__(timeout=120)
        self.add_item(ReminderDropdown(reminders))
        self.selected_doc_id = None


class ReminderCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = TinyDB("reminders.json")
        self.reminders_table = self.db.table("reminders")
        self.timezones_table = self.db.table("timezones")
        self.query = Query()
        self.check_reminders.start()

    def get_user_timezone(self, user_id: int):
        """
        Return the pytz timezone object for a given user, or None if not set.
        :param user_id: ID of the discord user.
        :return: The timezone string abbreviation
        """
        record = self.timezones_table.get(self.query.user_id == user_id)
        timezone = document_to_dataclass(record, Timezone)
        if timezone:
            return TIMEZONES.get(timezone.timezone, None)
        return None

    @staticmethod
    def parse_datetime_to_utc(time_str: str, tz: tzinfo):
        """
        Parse a string into a UTC datetime given a timezone.
        :param time_str: The string to parse.
        :param tz: The pytz timezone
        :return: The UTC datetime parsed.
        """
        try:
            local_dt = date_parser.parse(time_str)
            aware_dt = local_dt.replace(tzinfo=tz)
            return aware_dt.astimezone(gettz(DEFAULT_TIMEZONE))
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
            local_dt = date_parser.parse(time_str)
            local_dt = local_dt.replace(tzinfo=gettz(DEFAULT_TIMEZONE))
            converted_dt = local_dt.astimezone(tz)
            return converted_dt.strftime(M_D_Y_M_H_FORMAT)
        except (TypeError, ValueError, ParserError) as e:
            logging.error(f"Error parsing datetime {time_str}: {e}")
            return None

    @commands.slash_command(name="remindme", description="Set a reminder")
    async def remindme(
            self,
            ctx: discord.ApplicationContext,
            time: discord.Option(str, "When to remind you (Format: mm/dd/yy hh:mm)"),
            message: discord.Option(str, "The reminder message"),
            repeat: discord.Option(bool, "Repeat the reminder", required=False)):
        await ctx.defer(ephemeral=True)

        timezone_tz = self.get_user_timezone(ctx.author.id)
        if not timezone_tz:
            await ctx.respond("You need to set you timezone, by using the timezone command", ephemeral=True)
            return

        utc_dt = self.parse_datetime_to_utc(time, timezone_tz)
        if not utc_dt:
            await ctx.followup.send(f"Could not parse date/time {time} . Use format: `MM/DD/YY HH:MM TZ`")
            return

        reminder = Reminder(
            user_id= ctx.author.id,
            channel_id= ctx.channel.id,
            remind_at= utc_dt.isoformat(),
            message= message,
            repeat= repeat
        )

        self.reminders_table.insert(dataclass_to_document(reminder))
        await ctx.followup.send(f"✅ Reminder set for {time}.")


    @commands.slash_command(name="list_reminder", description="List active reminders")
    async def list_reminders(self,
                             ctx: discord.ApplicationContext):
        reminders = self.reminders_table.search(self.query.user_id == ctx.author.id)
        reminders = [document_to_dataclass(reminder, Reminder) for reminder in reminders]
        timezone_tz = self.get_user_timezone(ctx.author.id)
        for reminder in reminders:
            reminder.remind_at = self.parse_datetime_to_tz(reminder.remind_at, timezone_tz)
        if not reminders:
            await ctx.respond("No reminders found", ephemeral=True)
            return

        view = ReminderView(reminders)
        await ctx.respond("Select a reminder to delete:", view=view, ephemeral=True)
        await view.wait()
        if view.selected_doc_id:
            self.reminders_table.remove(doc_ids=[view.selected_doc_id])
            await ctx.followup.send("✅ Reminder deleted.", ephemeral=True)


    @commands.slash_command(name="timezone", description="Set a timezone")
    async def set_timezone(self,
                           ctx: discord.ApplicationContext,
                           timezone: discord.Option(str, "Select your timezone", choices=timezone_choices)):
        await ctx.defer(ephemeral=True)

        timezone = timezone.upper()
        user_id = ctx.author.id
        timezone = Timezone(
            user_id= user_id,
            timezone=timezone
        )

        existing = self.timezones_table.search(self.query.user_id == user_id)
        if existing:
            self.timezones_table.update(dataclass_to_document(timezone), self.query.user_id == user_id)
        else:
            self.timezones_table.insert(dataclass_to_document(timezone))

        await ctx.followup.send(f"🌍 Timezone set to {timezone.timezone}.", ephemeral=True)

    @tasks.loop(seconds=10)
    async def check_reminders(self):
        now_date = datetime.now(UTC)
        now = now_date.isoformat()
        due_reminders = self.reminders_table.search(self.query.remind_at <= now)

        reminders = [document_to_dataclass(reminder, Reminder) for reminder in due_reminders]
        for reminder in reminders:
            channel = self.bot.get_channel(reminder.channel_id)
            if channel:
                try:
                    user = await self.bot.fetch_user(reminder.user_id)
                    await channel.send(f"{user.mention} ⏰ Reminder: {reminder.message}")
                except Exception as e:
                    logging.error(f"Failed to send reminder {reminder.message} for user {reminder.user_id}: {e}")

            if reminder.repeat:
                future_date = now_date + timedelta(days=1)
                self.reminders_table.update({"remind_at": future_date.isoformat()}, doc_ids=[reminder.doc_id])
            else:
                # Remove sent reminder
                self.reminders_table.remove(doc_ids=[reminder.doc_id])


    def cog_unload(self) -> None:
        self.check_reminders.cancel()


def setup(bot):
    bot.add_cog(ReminderCog(bot))