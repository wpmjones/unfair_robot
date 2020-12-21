import coc
import re

from discord.ext import commands
# from cogs.utils.cache import get_data
from cogs.utils.constants import clans, clan_names


tag_validator = re.compile("^#?[PYLQGRJCUV0289]+$")


class PlayerConverter(commands.Converter):
    async def convert(self, ctx, argument):
        if isinstance(argument, coc.Player):
            return argument

        tag = coc.utils.correct_tag(argument)
        name = argument.strip().lower()

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
        # if player_names.count(name) > 1:
        #     indices = [i for i, x in enumerate(data) if x['player_name'].lower() == name]
        #     print(indices)
        #     prompt_text = f"Please select the appropriate {argument}:\n"
        #     for index in indices:
        #         prompt_text += f"{data[index]['player_name']} ({data[index]['player_tag']})\n"
        #     prompt = await ctx.prompt(prompt_text, additional_options=player_names.count(name))
        #     print(f"#{data[indices[prompt-1]]['player_tag']}")
        #     return await ctx.coc.get_player(f"#{data[indices[prompt-1]]['player_tag']}")
        for row in data:
            if row['player_name'].lower() == name:
                return await ctx.coc.get_player(f"#{row['player_tag']}")
        raise commands.BadArgument("Invalid tag or in-game name.")


class ClanConverter(commands.Converter):
    async def convert(self, ctx, argument):
        # if argument == "all" or not argument:
        #     return await get_data()
        if isinstance(argument, coc.Clan) and argument.tag in clans:
            return [argument]

        tag = coc.utils.correct_tag(argument)
        name = argument.strip().lower()

        if tag_validator.match(tag):
            try:
                if tag in clans:
                    return await ctx.coc.get_clan(tag)
                else:
                    raise commands.BadArgument("Clan not found in database. "
                                               "Only UW clans are listed in the database.")
            except coc.NotFound:
                raise commands.BadArgument(f'{tag} is not a valid clan tag.')
        if name in clan_names:
            for tag in clans:
                clan = await ctx.coc.get_clan(tag)
                if clan.name == name:
                    return clan
        raise commands.BadArgument(f'Clan name or tag `{argument}` not found')
