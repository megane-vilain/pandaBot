from discord.ext import commands
import discord


class Greetings(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # Slash command in a cog
    @commands.slash_command(name="hello", description="Say hello to the bot")
    async def hello(self, ctx: discord.ApplicationContext):
        await ctx.respond(f"Hello {ctx.author.mention}!")

# This is required so the bot can load the cog
def setup(bot):
    bot.add_cog(Greetings(bot))