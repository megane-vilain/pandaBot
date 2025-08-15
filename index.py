from utils.logging_config import init_logging
from dateutil import parser as dateparser
from datetime import UTC, datetime, timedelta
from tinydb import TinyDB, Query
from dotenv import load_dotenv
from dateutil.tz import gettz
from discord.ext import tasks

import discord
import os
import random

IMGFLIP_URL='https://api.imgflip.com'
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


def main():
    load_dotenv()
    init_logging()
    db = TinyDB('reminders.json')
    reminders_table = db.table("reminders")
    reminder_query = Query()
    bot = discord.Bot(intents=discord.Intents.default())
    bot.load_extension('cogs.greetings')
    bot.load_extension('cogs.api_call')

    @bot.slash_command(name="remindme", description="Set a reminder")
    async def remindme(
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
            local_dt = dateparser.parse(time)
            aware_dt = local_dt.replace(tzinfo=timezone)

            utc_dt = aware_dt.astimezone(gettz("UTC"))

            reminders_table.insert({
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
    async def check_reminders(query=reminder_query):
        now_date = datetime.now(UTC)
        now = now_date.isoformat()
        due_reminders = reminders_table.search(query.remind_at <= now)

        for reminder in due_reminders:
            channel = bot.get_channel(reminder["channel_id"])
            if channel:
                try:
                    user = await bot.fetch_user(reminder["user_id"])
                    await channel.send(f"{user.mention} ⏰ Reminder: {reminder['message']}")
                except Exception as e:
                    print(f"Failed to send reminder: {e}")

            if reminder.get("repeat"):
                future_date = now_date + timedelta(days=1)
                reminders_table.update({"remind_at": future_date.isoformat()}, doc_ids=[reminder.doc_id])
            else:
                # Remove sent reminder
                reminders_table.remove(doc_ids=[reminder.doc_id])

    @bot.slash_command(name="list_reminder", description="List active reminders")
    async def list_reminders(ctx: discord.ApplicationContext):
        reminders = reminders_table.search(reminder_query.user_id == ctx.author.id)

        if not reminders:
            await ctx.respond("No reminders found", ephemeral=True)
            return

        view = ReminderView(reminders)
        await ctx.respond("Select a reminder to delete:", view=view, ephemeral=True)
        await view.wait()
        if view.selected_doc_id:
            reminders_table.remove(doc_ids=[view.selected_doc_id])
            await ctx.followup.send("✅ Reminder deleted.", ephemeral=True)


    @bot.slash_command(name="roll", description="Roll between 1 and 100")
    async def roll(ctx: discord.ApplicationContext):
        await ctx.respond(random.randint(1, 100))


    @bot.event
    async def on_ready():
        print(f"{bot.user} is online!")
        check_reminders.start()
        await bot.sync_commands()  # Automatically sync all slash commands

    # Initialize globally
    bot.run(os.getenv('TOKEN'))

if __name__ == "__main__":
    main()