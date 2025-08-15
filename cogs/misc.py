from discord.ext import commands
import discord
import random


class Misc(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.slash_command(name="hello", description="Say hello to the bot")
    async def hello(self, ctx: discord.ApplicationContext):
        await ctx.respond(f"Hello {ctx.author.mention}!")

    @commands.slash_command(name="roll", description="Roll between 1 and 100")
    async def roll(self, ctx: discord.ApplicationContext):
        await ctx.respond(random.randint(1, 100))

# This is required so the bot can load the cog
def setup(bot):
    bot.add_cog(Misc(bot))