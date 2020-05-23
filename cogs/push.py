import discord
import math
import time

from discord.ext import commands, tasks
from cogs.utils.cache import get_neighbors
from cogs.utils.constants import clans
from cogs.utils.converters import PlayerConverter, ClanConverter
from cogs.utils import formats
from datetime import datetime


class Push(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.title = "Unfair Warfare Trophy Push"
        self.start_time = datetime(2020, 5, 25, 5, 0, 0)
        self.end_time = datetime(2020, 5, 30, 0, 0, 0)
        self.update_push.start()

    def cog_unload(self):
        self.update_push.cancel()

    @tasks.loop()
    async def push_start(self, ctx):
        msg = await ctx.send("Starting process...")
        start = time.perf_counter()
        player_list = []
        async for clan in self.bot.coc.get_clans(clans):
            for member in clan.itermembers:
                player_list.append(member.tag)
        to_insert = []
        counter = 1
        async for player in self.bot.coc.get_players(player_list):
            to_insert.append((counter,
                              player.tag[1:],
                              player.name.replace("'", "''"),
                              player.clan.tag[1:],
                              player.clan.name,
                              player.trophies if player.trophies <= 5000 else 5000,
                              player.trophies if player.trophies <= 5000 else 5000,
                              player.best_trophies,
                              player.town_hall
                              ))
            counter += 1
        conn = self.bot.pool
        sql = ("INSERT INTO uw_push_1 (player_tag, player_name, clan_tag, clan_name, "
               "starting_trophies, current_trophies, best_trophies, current_th_level) "
               "SELECT x.player_tag, x.player_name, x.clan_tag, x.clan_name, x.starting_trophies, "
               "x.current_trophies, x.best_trophies, x.current_th_level "
               "FROM unnest($1::uw_push_1[]) as x")
        await conn.execute(sql, to_insert)
        await msg.delete()
        await ctx.send(f"Elapsed time: {(time.perf_counter() - start) / 60:.2f} minutes")

    @tasks.loop(minutes=10.0)
    async def update_push(self):
        """Update trophy count and TH level"""
        now = datetime.utcnow()
        if self.start_time < now < self.end_time:
            conn = self.bot.pool
            sql = "SELECT player_tag FROM uw_push_1"
            fetch = await conn.fetch(sql)
            player_list = ["#" + x['player_tag'] for x in fetch]
            sql = "UPDATE uw_push_1 SET current_trophies = $1, current_th_level = $2 WHERE player_tag = $3"
            async for player in self.bot.coc.get_players(player_list):
                await conn.execute(sql, player.trophies, player.town_hall, player.tag[1:])

    @commands.group(name="push",  invoke_without_command=True)
    async def push(self, ctx):
        """Use `+help push` for details on using this category"""
        if ctx.invoked_subcommand is not None:
            return

        await ctx.invoke(self.push_info)

    @push.command(name="info")
    async def push_info(self, ctx):
        """Provides information on the push event."""
        now = datetime.utcnow()
        conn = self.bot.pool
        sql = ("SELECT COUNT(*) AS num_players, MAX(current_trophies) AS max_trophies, "
               "MAX(current_trophies - starting_trophies) AS max_gain FROM uw_push_1")
        fetch = await conn.fetchrow(sql)
        player_count = fetch['num_players']
        clan_count = len(clans)
        max_trophies = fetch['max_trophies']
        max_gain = fetch['max_gain']
        delta = (self.end_time - now)
        days = delta.days
        hours, rem = divmod(delta.seconds, 3600)
        mins, rem = divmod(rem, 60)
        if days > 0:
            time_left = f"{days} days, {hours} hours"
        else:
            time_left = f"{hours} hours, {mins} minutes"
        embed = discord.Embed(title="UW Trophy Push Stats", color=discord.Color.dark_red())
        embed.add_field(name="Clans", value=str(clan_count), inline=True)
        embed.add_field(name="Players", value=str(player_count), inline=True)
        embed.add_field(name="End Time", value=self.end_time.strftime("%d %b %Y %H:%M"), inline=True)
        embed.add_field(name="Highest Trophies", value=str(max_trophies), inline=True)
        embed.add_field(name="Biggest Gain", value=str(max_gain), inline=True)
        embed.add_field(name="Time Left", value=time_left, inline=True)
        embed.set_thumbnail(url="http://www.mayodev.com/images/trophy2.png")
        await ctx.send(embed=embed)

    @push.command(name="top")
    async def push_top(self, ctx):
        """Returns the top 20 players"""
        conn = self.bot.pool
        sql = ("SELECT "
               "CASE current_th_level "
               "WHEN 13 THEN current_trophies - 5000 "
               "WHEN 12 THEN current_trophies - 4000 "
               "WHEN 11 THEN current_trophies - 3500 "
               "WHEN 10 THEN current_trophies - 3000 "
               "ELSE 1 "
               "END AS score, "
               "player_name, current_th_level "
               "FROM uw_push_1 "
               "WHERE current_th_level > 9 "
               "ORDER BY score DESC")
        fetch = await conn.fetch(sql)
        ctx.icon = "https://cdn.discordapp.com/emojis/635642869738111016.png"
        p = formats.TopTenPaginator(ctx, data=fetch)
        await p.paginate()

    @push.command(name="all")
    async def push_all(self, ctx):
        """Return all players"""
        conn = self.bot.pool
        sql = ("SELECT "
               "CASE current_th_level "
               "WHEN 13 THEN current_trophies - 5000 "
               "WHEN 12 THEN current_trophies - 4000 "
               "WHEN 11 THEN current_trophies - 3500 "
               "WHEN 10 THEN current_trophies - 3000 "
               "ELSE 1 "
               "END AS score, "
               "player_name, current_th_level "
               "FROM uw_push_1 "
               "WHERE current_th_level > 9 "
               "ORDER BY score DESC")
        fetch = await conn.fetch(sql)
        ctx.icon = "https://cdn.discordapp.com/emojis/635642869738111016.png"
        p = formats.TablePaginator(ctx, data=fetch, title="All players", page_count=4)
        await p.paginate()

    @push.command(name="player", aliases=["p"])
    async def push_player(self, ctx, *, player: PlayerConverter = None):
        """Displays the ranking of the individual and 5 players on either side
        You may provide the player name or tag. If there are multiple players
        with the same name, it is best to use the tag.

        Examples:
        /push player Ristey
        /push p #8GQPJG2CL"""
        if not player:
            return await ctx.send("Please provide a player name or a player tag")
        fetch = await get_neighbors(player.tag)
        ctx.icon = "https://cdn.discordapp.com/emojis/635642869738111016.png"
        p = formats.TablePaginator(ctx, data=fetch, title="Nearby players")
        await p.paginate()

    @push.command(name="clan", aliases=["c"])
    async def push_clan(self, ctx, *, clan: ClanConverter = None):
        """Displays the ranking of individuals in the specified clan
        You may provide the clan name or tag. If there are multiple clans
        with the same name, it is best to use the tag.

        Examples:
        /push clan Unfair Warfare
        /push c AphelionESPORTS"""
        if not clan:
            return await ctx.send("Please provide a clan name or clan tag")
        conn = self.bot.pool
        sql = ("SELECT score, player_name FROM uw_push "
               "WHERE clan_tag = $1 ORDER BY score DESC")
        fetch = await conn.fetch(sql, clan.tag[1:])
        ctx.icon = "https://cdn.discordapp.com/emojis/635642869738111016.png"
        p = formats.TablePaginator(ctx, data=fetch, title=clan.name, page_count=2, rows_per_table=25)
        await p.paginate()

    @push.command(name="clans")
    async def push_clans(self, ctx):
        """Displays the ranking of clans based on total scores"""
        conn = self.bot.pool
        sql = ("SELECT SUM(score) as total, clan_name FROM uw_push "
               "GROUP BY clan_name "
               "ORDER BY total DESC")
        fetch = await conn.fetch(sql)
        ctx.icon = "https://cdn.discordapp.com/emojis/635642869738111016.png"
        p = formats.TablePaginator(ctx, data=fetch, title="All Clans", page_count=1, rows_per_table=20)
        await p.paginate()


def setup(bot):
    bot.add_cog(Push(bot))
