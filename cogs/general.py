from discord.ext import commands
from cogs.utils.converters import PlayerConverter
from config import settings


class General(commands.Cog):
    """Default commands for Unfair Robot"""
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="player")
    async def player(self, ctx, *, player: PlayerConverter = None):
        if not player:
            return await ctx.send("Player not found. Please try using the player tag.")
        return await ctx.send(f"Player: {player.name} ({player.tag})")
