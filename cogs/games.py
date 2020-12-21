import asyncio
import math
import re

from discord.ext import commands, tasks
from cogs.utils import formats
from cogs.utils.constants import clans
from cogs.utils.converters import ClanConverter, PlayerConverter
from datetime import datetime, timedelta

tag_validator = re.compile("^#?[PYLQGRJCUV0289]+$")


class Games(commands.Cog):
    """Cog for Clan Games"""
    def __init__(self, bot):
        self.bot = bot
        self.channel = None
        self.channel_id = 790235721470443522
        self.start_games.start()
        self.update_games.start()

    def cog_unload(self):
        self.start_games.cancel()
        self.update_games.cancel()

    async def get_last_games(self):
        """Get games ID from rcs_events for the most recent clan games"""
        now = datetime.utcnow()
        sql = ("SELECT event_id, MAX(end_time) as end_time " 
               "FROM rcs_events "
               "WHERE event_type_id = 1 AND end_time < $1 "
               "GROUP BY event_id "
               "ORDER BY end_time DESC "
               "LIMIT 1")
        row = await self.bot.pool.fetchrow(sql, now)
        return row['event_id'], row['end_time']

    async def get_current_games(self):
        """Get games ID from RCS-events for the current clan games, if active (else None)"""
        sql = ("SELECT event_id, player_points, clan_points  "
               "FROM rcs_events "
               "WHERE event_type_id = 1 AND CURRENT_TIMESTAMP BETWEEN start_time AND end_time")
        row = await self.bot.pool.fetchrow(sql)
        if row:
            return {"games_id": row['event_id'],
                    "player_points": row['player_points'],
                    "clan_points": row['clan_points']}
        else:
            return None

    async def get_next_games(self):
        """Get games ID from rcs_events for the next clan games, if available (else None)"""
        now = datetime.utcnow()
        sql = ("SELECT event_id, MIN(start_time) as start_time "
               "FROM rcs_events "
               "WHERE event_type_id = 1 AND start_time > $1 "
               "GROUP BY event_id")
        row = await self.bot.pool.fetchrow(sql, now)
        if row:
            return row['event_id'], row['start_time']
        else:
            return None

    async def closest_games(self):
        """Get the most recent or next games, depending on which is closest"""
        last_games_id, _last = await self.get_last_games()
        next_games_id, _next = await self.get_next_games()
        now = datetime.utcnow()
        time_to_last = now - _last
        time_to_next = _next - now
        if time_to_next > time_to_last:
            # deal with last games
            return "last", last_games_id
        else:
            # deal with next games
            return "next", next_games_id

    @tasks.loop(minutes=10)
    async def start_games(self):
        """Task to pull initial Games data for the new clan games"""
        now = datetime.utcnow()
        conn = self.bot.pool
        games_id, start_time = await self.get_next_games()
        # games_id = 22
        if games_id:
            # sql = "SELECT start_time FROM rcs_events WHERE event_id = $1"
            # start_time = await conn.fetchval(sql, games_id)
            if start_time - now < timedelta(minutes=10):
                to_insert = []
                counter = 0
                async for clan in self.bot.coc.get_clans(clans):
                    async for member in clan.get_detailed_members():
                        counter += 1
                        to_insert.append((counter,
                                          games_id,
                                          member.tag[1:],
                                          clan.tag[1:],
                                          member.get_achievement("Games Champion").value,
                                          0, None
                                          ))
                sql = ("INSERT INTO uw_clan_games "
                       "(event_id, player_tag, clan_tag, starting_points, current_points, max_reached) "
                       "SELECT x.event_id, x.player_tag, x.clan_tag, x.starting_points, "
                       "x.current_points, x.max_reached "
                       "FROM unnest($1::uw_clan_games[]) as x")
                await conn.execute(sql, to_insert)
                self.bot.logger.info(f"{counter} players added to UW Clan Games event. Game on!")

    @start_games.before_loop
    async def before_start_games(self):
        await self.bot.wait_until_ready()

    @tasks.loop(minutes=12)
    async def update_games(self):
        """Task to pull API data for clan games"""
        conn = self.bot.pool
        games = await self.get_current_games()
        now = datetime.utcnow()
        if not self.channel:
            self.channel = self.bot.get_channel(self.channel_id)
        if games:
            sql = "SELECT player_tag, clan_tag, starting_points, max_reached FROM uw_clan_games WHERE event_id = $1"
            players = await conn.fetch(sql, games['games_id'])
            for row in players:
                player = await self.bot.coc.get_player(row['player_tag'])
                current_points = player.get_achievement("Games Champion").value - row['starting_points']
                if current_points >= games['player_points'] and not row['max_reached']:
                    max_reached = now
                    sql = ("UPDATE uw_clan_games "
                           "SET current_points = $1, max_reached = $2 "
                           "WHERE player_tag = $3")
                    await conn.execute(sql, current_points, max_reached, player.tag[1:])
                    clan = await self.bot.coc.get_clan(row['clan_tag'])
                    content = f":trophy: {player.name} ({clan.name}) just hit max points for Clan Games!"
                    await self.channel.send(content)
                else:
                    sql = ("UPDATE uw_clan_games "
                           "SET current_points = $1 "
                           "WHERE player_tag = $2")
                    await conn.execute(sql, current_points, player.tag[1:])
            print("Done")

    @update_games.before_loop
    async def before_update_games(self):
        await self.bot.wait_until_ready()

    @commands.group(invoke_without_command=True)
    async def games(self, ctx, *, clan: ClanConverter = None):
        """[Group] Commands for clan games"""
        if ctx.invoked_subcommand is not None:
            return

        if not clan:
            await ctx.invoke(self.games_all)
        else:
            await ctx.invoke(self.games_clan, clan=clan)

    @games.command(name="all")
    async def games_all(self, ctx):
        """Returns clan points for all participating clans"""
        conn = self.bot.pool
        games = await self.get_current_games()
        if games:
            sql = ("SELECT SUM(current_points) AS clan_total, clan_tag "
                   "FROM uw_clan_games "
                   "WHERE event_id = $1 "
                   "GROUP BY clan_tag "
                   "ORDER BY clan_total DESC")
            fetch = await conn.fetch(sql, games['games_id'])
            data = []
            for row in fetch:
                clan = await self.bot.coc.get_clan(row['clan_tag'])
                prefix = "* " if row['clan_total'] >= games['clan_points'] else ""
                data.append([row['clan_total'], prefix + clan.name])
            page_count = math.ceil(len(data) / 25)
            title = "UWF Clan Games Points"
            ctx.icon = "https://cdn.discordapp.com/emojis/639623355770732545.png"
            p = formats.TablePaginator(ctx, data=data, title=title, page_count=page_count)
            await p.paginate()
        else:
            closest, games_id = await self.closest_games()
            if closest == "next":
                sql = "SELECT start_time FROM rcs_events WHERE event_id = $1"
                next_start = await conn.fetchval(sql, games_id)
                # TODO Next line will need formatting
                return await ctx.send(f"Clan Games are not currently active. Next games starts at {next_start}")
            else:
                sql = ("SELECT SUM(current_points) AS clan_total, clan_tag "
                       "FROM uw_clan_games "
                       "WHERE event_id = $1 "
                       "GROUP BY clan_tag "
                       "ORDER BY clan_total DESC")
                fetch = await conn.fetch(sql, games_id)
                data = []
                for row in fetch:
                    clan = await self.bot.coc.get_clan(row['clan_tag'])
                    prefix = "* " if row['clan_total'] >= games['clan_points'] else ""
                    data.append([row['clan_total'], prefix + clan.name])
                page_count = math.ceil(len(data) / 25)
                title = "Last Clan Games Points"
                ctx.icon = "https://cdn.discordapp.com/emojis/639623355770732545.png"
                p = formats.TablePaginator(ctx, data=data, title=title, page_count=page_count)
                await p.paginate()

    @games.command(name="top")
    async def games_top(self, ctx):
        """Show top ten players' games points"""
        async with ctx.typing():
            conn = self.bot.pool
            games = await self.get_current_games()
            if games:
                sql = ("SELECT player_tag, current_points "
                       "FROM uw_clan_games "
                       "WHERE event_id = $1 "
                       "ORDER BY current_points DESC "
                       "LIMIT 10")
                fetch = await conn.fetch(sql, games['games_id'])
                data = []
                for row in fetch:
                    player = await self.bot.coc.get_player(row['player_tag'])
                    data.append([row['current_points'], f"{player.name} ({player.clan.name})"])
                title = "UW Top Ten for Clan Games"
                ctx.icon = "https://cdn.discordapp.com/emojis/635642869750824980.png"
                p = formats.TablePaginator(ctx, data=data, title=title, page_count=1)
            await p.paginate()

    @games.command(name="average", aliases=["avg", "averages"])
    async def games_average(self, ctx):
        """Returns the average player points for all participating clans"""
        conn = self.bot.pool
        sql = ("SELECT clan_avg, clan_tag "
               "FROM uw_clan_games_average "
               "ORDER BY clan_avg DESC")
        fetch = await conn.fetch(sql)
        data = []
        for row in fetch:
            clan = await self.bot.coc.get_clan(row['clan_tag'])
            data.append([row['clan_avg'], clan.name])
        page_count = math.ceil(len(data) / 25)
        title = "UWF Clan Games Averages"
        ctx.icon = "https://cdn.discordapp.com/emojis/639623355770732545.png"
        p = formats.TablePaginator(ctx, data=data, title=title, page_count=page_count)
        await p.paginate()

    @games.command(name="clan")
    async def games_clan(self, ctx, *, clan: ClanConverter = None):
        """Returns the individual player points for the specified clan
        Examples:
        `++games clan Unfair Warfare`
        `++games clan #UUJJ80`
        """
        async with ctx.typing():
            conn = self.bot.pool
            sql = ("SELECT player_points "
                   "FROM rcs_events "
                   "WHERE event_type_id = 1 and start_time < NOW() "
                   "ORDER BY start_time DESC")
            player_points = await conn.fetchval(sql)
            sql = ("SELECT player_tag, current_points "
                   "FROM uw_clan_games "
                   "WHERE clan_tag = $1"
                   "ORDER BY current_points DESC")
            fetch = await conn.fetch(sql, clan.tag[1:])
            clan_total = 0
            clan_size = len(fetch)
            data = []
            for member in fetch:
                player = await self.bot.coc.get_player(member['player_tag'])
                player_name = player.name
                if member['current_points'] >= player_points:
                    clan_total += player_points
                    data.append([member['current_points'], "* " + player_name])
                else:
                    clan_total += member['current_points']
                    data.append([member['current_points'], player_name])
            clan_average = clan_total / clan_size
        page_count = math.ceil(len(data) / 25)
        title = f"{clan.name} Points {clan_total} ({clan_average:.2f} avg)"
        ctx.icon = "https://cdn.discordapp.com/emojis/639623355770732545.png"
        p = formats.TablePaginator(ctx, data=data, title=title, page_count=page_count)
        await p.paginate()


def setup(bot):
    bot.add_cog(Games(bot))
