import discord
from discord.ext import commands
from dotenv import load_dotenv
import requests
import os
import time

IMGFLIP_URL='https://api.imgflip.com'

load_dotenv()


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

bot = commands.Bot(intents=discord.Intents.default())

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

@bot.event
async def on_ready():
    print(f"{bot.user} is ready and online!")

# Initialize globally
meme_cache = MemeTemplateCache()

bot.run(os.getenv('TOKEN'))