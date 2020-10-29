import csv

from discord.ext import commands
from cogs.utils.converters import PlayerConverter


class General(commands.Cog):
    """Default commands for Unfair Robot"""
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="player")
    async def player(self, ctx, *, player: PlayerConverter = None):
        if not player:
            return await ctx.send("Player not found. Please try using the player tag.")
        return await ctx.send(f"Player: {player.name} ({player.tag})")

    @commands.command(name="csv", hidden=True)
    @commands.is_owner()
    async def save_csv(self, ctx, filename, *, sql):
        conn = self.bot.pool
        fetch = await conn.fetch(sql)
        with open(f"{filename}.csv", mode='w', newline='') as f:
            f_writer = csv.writer(f, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)
            headers = [x for x in fetch[0].keys()]
            f_writer.writerow(headers)
            for row in fetch:
                f_writer.writerow([x for x in row.values()])


def setup(bot):
    bot.add_cog(General(bot))
