import coc
import re

from discord.ext import commands
from cogs.utils.cache import get_data


tag_validator = re.compile("^#?[PYLQGRJCUV0289]+$")


class PlayerConverter(commands.Converter):
    async def convert(self, ctx, argument):
        if isinstance(argument, coc.BasicPlayer):
            return argument

        tag = coc.utils.correct_tag(argument)
        name = argument.strip().lower()
        print(name)
        data = await get_data()

        if tag_validator.match(argument):
            try:
                for row in data:
                    if row['player_tag'] == tag[1:]:
                        return await ctx.coc.get_player(tag)
                else:
                    raise commands.BadArgument("Player not found in database. "
                                               "Only UW members are listed in the database.")
            except coc.NotFound:
                raise commands.BadArgument("I detected a player tag; and couldn't "
                                           "find an account with that tag! "
                                           "If you didn't pass in a tag, "
                                           "please drop the owner a message.")
        print("past tag")
        for row in data:
            if row['player_name'].lower() == name:
                print(f"#{row['player_tag']}")
                return await ctx.coc.get_player(f"#{row['player_tag']}")
        raise commands.BadArgument("Invalid tag or in-game name.")


class ClanConverter(commands.Converter):
    async def convert(self, ctx, argument):
        if argument == "all" or not argument:
            return await get_data()
        if isinstance(argument, coc.BasicClan):
            return [argument]

        tag = coc.utils.correct_tag(argument)
        name = argument.strip().lower()
        data = await get_data()

        if tag_validator.match(argument):
            try:
                for row in data:
                    if row['clan_tag'] == tag[1:]:
                        return await ctx.coc.get_clan(tag)
                else:
                    raise commands.BadArgument("Clan not found in database. "
                                               "Only UW clans are listed in the database.")
            except coc.NotFound:
                raise commands.BadArgument(f'{tag} is not a valid clan tag.')
        for row in data:
            if row['clan_name'].lower() == name:
                return await ctx.coc.get_clan(row['clan_tag'])
        raise commands.BadArgument(f'Clan name or tag `{argument}` not found')
