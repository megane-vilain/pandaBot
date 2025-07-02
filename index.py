import discord
from discord.ext import commands
from dotenv import load_dotenv
import requests
import os
import time

load_dotenv()
bot = commands.Bot(intents=discord.Intents.default())

# User template selection
user_template_selection = {}

class MemeTemplateCache:
    def __init__(self, refresh_interval=3600):
        self.templates = []
        self.last_updated = 0
        self.refresh_interval = refresh_interval

    def fetch_templates(self):
        if time.time() - self.last_updated < self.refresh_interval and self.templates:
            return self.templates
        response = requests.get("https://api.imgflip.com/get_memes")
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
    async def previous_button(self, button, interaction: discord.Interaction):
        if self.index > 0:
            self.index -= 1
        else:
            self.index = len(self.templates) - 1
        await interaction.response.edit_message(embed=self.create_embed(), view=self)

    @discord.ui.button(label="Next", style=discord.ButtonStyle.secondary)
    async def next_button(self, button, interaction: discord.Interaction):
        if self.index < len(self.templates) - 1:
            self.index += 1
        else:
            self.index = 0
        await interaction.response.edit_message(embed=self.create_embed(), view=self)

    @discord.ui.button(label="Select This", style=discord.ButtonStyle.success)
    async def select_button(self, button, interaction: discord.Interaction):
        print("select_button")
        selected_template = self.templates[self.index]
        user_template_selection[self.user_id] = selected_template["id"]

        # Disable buttons
        for child in self.children:
            child.disabled = True

        await interaction.response.edit_message(view=self)

        await interaction.followup.send(
            f"You selected **{selected_template['name']}**.\nUse `/caption` to add text!",
            ephemeral=True
        )

        self.stop()


@bot.slash_command(name="meme", description="Browse meme templates and select one")
async def meme(ctx):
    templates = meme_cache.fetch_templates()
    if not templates:
        await ctx.respond("Could not load meme templates. Please try again later.", ephemeral=True)
        return

    view = MemeGallery(user_id=ctx.author.id, templates=templates)
    embed = view.create_embed()
    await ctx.respond(embed=embed, view=view, ephemeral=True)

@bot.slash_command(name="caption", description="Create a meme from your selected template")
async def caption(ctx: discord.ApplicationContext,
                  text0: discord.Option(str, 'First Text'),
                  text1: discord.Option(str,'Second Text', required=False),):
    user_id = ctx.author.id
    
    if user_id not in user_template_selection:
        await ctx.respond("Please select a meme template first using `/meme`.", ephemeral=True)
        return

    template_id = user_template_selection[user_id]

    # Generate meme using Imgflip
    response = requests.post("https://api.imgflip.com/caption_image", data={
        "template_id": template_id,
        "username": os.getenv("API_USERNAME"),
        "password": os.getenv("API_PASSWORD"),
        "text0": text0,
        "text1": text1
    })

    data = response.json()
    if data["success"]:
        await ctx.respond(data["data"]["url"])
    else:
        await ctx.respond(f"Error: {data.get('error_message', 'Unknown error')}")

@bot.slash_command(name="hello", description="Say hello to the bot")
async def hello(ctx: discord.ApplicationContext):
    await ctx.respond(f"Hello {ctx.author.mention}!")

@bot.event
async def on_ready():
    print(f"{bot.user} is ready and online!")

# Initialize globally
meme_cache = MemeTemplateCache()

bot.run(os.getenv('TOKEN'))