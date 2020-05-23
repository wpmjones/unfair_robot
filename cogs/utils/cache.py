import asyncpg

from config import settings


async def get_neighbors(player_tag):
    """Retrieve the nearest 5 neighbors from the provided player, sorted by score"""
    conn = await asyncpg.connect(f"{settings['pg']['uri']}")
    sql = ("WITH cte AS ("
           "SELECT score, player_name, player_tag, ROW_NUMBER() OVER (ORDER BY score DESC) AS row_num "
           "FROM uw_push "
           "), curr AS ( "
           "SELECT row_num FROM cte "
           "WHERE player_tag = $1 "
           ") "
           "SELECT cte.* "
           "FROM cte, curr "
           "WHERE ABS(cte.row_num - curr.row_num) <= 5 "
           "ORDER BY cte.row_num")
    fetch = await conn.fetch(sql, player_tag[1:])
    await conn.close()
    return fetch


async def get_data():
    """Retrieve all clans that are a part of UW"""
    conn = await asyncpg.connect(f"{settings['pg']['uri']}")
    sql = "SELECT player_name, player_tag, clan_name, clan_tag FROM uw_push_1 ORDER BY player_name"
    fetch = await conn.fetch(sql)
    await conn.close()
    return fetch
