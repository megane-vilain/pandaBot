import datetime
from xmlrpc.client import DateTime

import discord
from discord.ext import commands, tasks
from dotenv import load_dotenv
from tinydb import TinyDB, Query
from datetime import datetime, UTC
from dateutil import parser as dateparser
from dateutil.tz import gettz
import requests
import os
import time
import random

IMGFLIP_URL='https://api.imgflip.com'
TIMEZONES = {
    "BST": gettz("Europe/London"),  # British Summer Time
    "GMT": gettz("Europe/London"),
    "CET": gettz("Europe/Paris"),   # Central European Time
    "CEST": gettz("Europe/Paris"),
}

load_dotenv()

db = TinyDB('reminders.json')
reminders_table = db.table("reminders")
Reminder = Query()


class CaptionModal(discord.ui.Modal):
    def __init__(self, template_id:str):
        super().__init__(title="Enter Meme Caption")
        self.template_id = template_id

        self.add_item(discord.ui.InputText(label="First Caption", placeholder="Enter top text"))
        self.add_item(discord.ui.InputText(label="Second Caption", placeholder="Enter bottom text", required=False))

    async def callback(self, interaction: discord.Interaction):
        top_text = self.children[0].value
        bottom_text = self.children[1].value

        # Generate meme using Imgflip
        response = requests.post(f"{IMGFLIP_URL}/caption_image", data={
            "template_id": self.template_id,
            "username": os.getenv("API_USERNAME"),
            "password": os.getenv("API_PASSWORD"),
            "text0": top_text,
            "text1": bottom_text
        })

        data = response.json()
        if data["success"]:
            await interaction.response.send_message(data["data"]["url"])
        else:
            await interaction.response.send_message(
                f"Error: {data.get('error_message', 'Unknown error')}", ephemeral=True
            )

class MemeTemplateCache:
    def __init__(self, refresh_interval=3600):
        self.templates = []
        self.last_updated = 0
        self.refresh_interval = refresh_interval

    def fetch_templates(self):
        if time.time() - self.last_updated < self.refresh_interval and self.templates:
            return self.templates
        response = requests.get(f"{IMGFLIP_URL}/get_memes")
        data = response.json()

        if data["success"]:
            self.templates = data["data"]["memes"]
            self.last_updated = time.time()
        else:
            print("Failed to fetch memes templates")
        return self.templates

    def get_template_by_id(self, template_id: str):
        return next((m for m in self.templates if m["id"] == template_id), None)


class MemeGallery(discord.ui.View):
    def __init__(self, user_id: int, templates: list):
        super().__init__(timeout=300)
        self.index = 0
        self.user_id = user_id
        self.templates = templates
        self.index = 0


    def create_embed(self):
        template = self.templates[self.index]
        embed = discord.Embed(
            title=template["name"],
            description=f"ID: `{template['id']}` | Boxes: {template['box_count']}",
            color=discord.Color.blurple())
        embed.set_image(url=template["url"])
        embed.set_footer(text=f"Template {self.index + 1} of {len(self.templates)}")
        return embed

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id == self.user_id

    @discord.ui.button(label="Previous", style=discord.ButtonStyle.secondary)
    async def previous_button(self, button:discord.ui.Button, interaction: discord.Interaction):
        if self.index > 0:
            self.index -= 1
        else:
            self.index = len(self.templates) - 1
        await interaction.response.edit_message(embed=self.create_embed(), view=self)

    @discord.ui.button(label="Next", style=discord.ButtonStyle.secondary)
    async def next_button(self, button:discord.ui.Button, interaction: discord.Interaction):
        if self.index < len(self.templates) - 1:
            self.index += 1
        else:
            self.index = 0
        await interaction.response.edit_message(embed=self.create_embed(), view=self)

    @discord.ui.button(label="Select This", style=discord.ButtonStyle.success)
    async def select_button(self, button:discord.ui.Button, interaction: discord.Interaction):
        selected_template = self.templates[self.index]

        # Disable buttons
        for child in self.children:
            child.disabled = True

        await interaction.response.send_modal(CaptionModal(selected_template["id"]))

        self.stop()

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
        doc_id = int(self.values[0])
        reminders_table.remove(doc_ids=[doc_id])
        await interaction.response.send_message("✅ Reminder deleted.", ephemeral=True)

class ReminderView(discord.ui.View):
    def __init__(self, reminders):
        super().__init__(timeout=120)
        self.add_item(ReminderDropdown(reminders))

bot = discord.Bot(intents=discord.Intents.default())

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
async def check_reminders():
    now_date = datetime.now(UTC)
    now = now_date.isoformat()
    due_reminders = reminders_table.search(Reminder.remind_at <= now)

    for reminder in due_reminders:
        channel = bot.get_channel(reminder["channel_id"])
        if channel:
            try:
                user = await bot.fetch_user(reminder["user_id"])
                await channel.send(f"{user.mention} ⏰ Reminder: {reminder['message']}")
            except Exception as e:
                print(f"Failed to send reminder: {e}")

        if reminder.get("repeat"):
            future_date = now_date + datetime.timedelta(days=1)
            reminders_table.update({reminder["remind_at"]: future_date},doc_ids=[reminder.doc_id])
        else:
            # Remove sent reminder
            reminders_table.remove(doc_ids=[reminder.doc_id])


@bot.slash_command(name="list_reminder", description="List active reminders")
async def list_reminders(ctx: discord.ApplicationContext):
    reminders = reminders_table.search(Reminder.user_id == ctx.author.id)

    if not reminders:
        await ctx.respond("No reminders found", ephemeral=True)
        return

    await ctx.respond("Select a reminder to delete:", view=ReminderView(reminders), ephemeral=True)



@bot.slash_command(name="meme", description="Browse meme templates and select one")
async def meme(ctx):
    templates = meme_cache.fetch_templates()
    if not templates:
        await ctx.respond("Could not load meme templates. Please try again later.", ephemeral=True)
        return

    view = MemeGallery(user_id=ctx.author.id, templates=templates)
    embed = view.create_embed()
    response = await ctx.respond(embed=embed, view=view, ephemeral=True)

    view.message = await response.original_response()

@bot.slash_command(name="hello", description="Say hello to the bot")
async def hello(ctx: discord.ApplicationContext):
    await ctx.respond(f"Hello {ctx.author.mention}!")

@bot.slash_command(name="roll", description="Roll between 1 and 100")
async def roll(ctx: discord.ApplicationContext):
    await ctx.respond(random.randint(1, 100))

@bot.slash_command(name="duck", description="Random duck image")
async def duck_fact(ctx: discord.ApplicationContext):
    response = requests.get('https://random-d.uk/api/v2/quack')

    data = response.json()
    if data["url"]:
        await ctx.respond(data["url"])
    else:
        await ctx.respond("Something went wrong. No duck for you")

@bot.event
async def on_ready():
    print(f"{bot.user} is online!")
    check_reminders.start()
    await bot.sync_commands()  # Automatically sync all slash commands

# Initialize globally
meme_cache = MemeTemplateCache()

bot.run(os.getenv('TOKEN'))