from discord.ext import commands, tasks
from dateutil import parser as date_parser
from dateutil.tz import gettz
from datetime import UTC, datetime, timedelta
import discord
from tinydb import TinyDB, Query

TIMEZONES = {
    "BST": gettz("Europe/London"),  # British Summer Time
    "GMT": gettz("Europe/London"),
    "CET": gettz("Europe/Paris"),   # Central European Time
    "CEST": gettz("Europe/Paris"),
}


class ReminderDropdown(discord.ui.Select):
    def __init__(self, reminders):
        options = []
        for reminder in reminders:
            label = reminder["message"][:50]
            date = reminder.get("remind_at").split("T")
            dt_str = f'{date[0]} {date[1] [:5]}'
            if reminder.get("remind_at"):
                prefix = "🔁"
            else:
                prefix = "📅"
            options.append(
                discord.SelectOption(
                    label=f"{prefix} {dt_str} - {label}",
                    value=str(reminder.doc_id)
                )
            )
            super().__init__(
                placeholder="Select a reminder to delete",
                min_values=1,
                max_values=1,
                options=options
            )


    async def callback(self, interaction: discord.Interaction):
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

class Reminder(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = TinyDB("reminders.json")
        self.reminders_table = self.db.table("reminders")
        self.reminder_query = Query()
        self.check_reminders.start()


    @commands.slash_command(name="remindme", description="Set a reminder")
    async def remindme(
            self,
            ctx: discord.ApplicationContext,
            time: discord.Option(str, "When to remind you (Format: mm/dd/yy hh:mm)"),
            timezone: discord.Option(str, "Timezone abbreviation like BST, GMT, CET, CEST"),
            message: discord.Option(str, "The reminder message"),
            repeat: discord.Option(bool, "Repeat the reminder", required=False)):
        timezone = TIMEZONES.get(timezone.upper())
        await ctx.defer(ephemeral=True)
        if not timezone:
            await ctx.followup.send("Invalid timezone, use BST, GMT, CET or CEST")
            return

        try:
            local_dt = date_parser.parse(time)
            aware_dt = local_dt.replace(tzinfo=timezone)

            utc_dt = aware_dt.astimezone(gettz("UTC"))

            self.reminders_table.insert({
                "user_id": ctx.author.id,
                "channel_id": ctx.channel.id,
                "remind_at": utc_dt.isoformat(),
                "message": message,
                "repeat": repeat
            })
            await ctx.followup.send(f"✅ Reminder set for {aware_dt.strftime('%Y-%m-%d %H:%M %Z')}.")

        except Exception as e:
            await ctx.followup.send("❌ Could not parse date/time. Use format: `MM/DD/YY HH:MM TZ`")
            print("Error:", e)

    @tasks.loop(seconds=10)
    async def check_reminders(self):
        now_date = datetime.now(UTC)
        now = now_date.isoformat()
        due_reminders = self.reminders_table.search(self.reminder_query.remind_at <= now)

        for reminder in due_reminders:
            channel = self.bot.get_channel(reminder["channel_id"])
            if channel:
                try:
                    user = await self.bot.fetch_user(reminder["user_id"])
                    await channel.send(f"{user.mention} ⏰ Reminder: {reminder['message']}")
                except Exception as e:
                    print(f"Failed to send reminder: {e}")

            if reminder.get("repeat"):
                future_date = now_date + timedelta(days=1)
                self.reminders_table.update({"remind_at": future_date.isoformat()}, doc_ids=[reminder.doc_id])
            else:
                # Remove sent reminder
                self.reminders_table.remove(doc_ids=[reminder.doc_id])

    @commands.slash_command(name="list_reminder", description="List active reminders")
    async def list_reminders(self, ctx: discord.ApplicationContext):
        reminders = self.reminders_table.search(self.reminder_query.user_id == ctx.author.id)

        if not reminders:
            await ctx.respond("No reminders found", ephemeral=True)
            return

        view = ReminderView(reminders)
        await ctx.respond("Select a reminder to delete:", view=view, ephemeral=True)
        await view.wait()
        if view.selected_doc_id:
            self.reminders_table.remove(doc_ids=[view.selected_doc_id])
            await ctx.followup.send("✅ Reminder deleted.", ephemeral=True)


    def cog_unload(self) -> None:
        self.check_reminders.cancel()


def setup(bot):
    bot.add_cog(Reminder(bot))