import discord
import os
from discord.ext import commands
import asyncio
import configparser
import json

BOT_PREFIX = "!"
BOT_TOKEN = None
MOD_ROLE_ID = None
IMAGE_URL = ""

bot = commands.Bot(command_prefix=BOT_PREFIX,
                   description='A bot that manages Pokemon Go Discord communities.')

locale = None
base_stats = None
cp_multipliers = None
boss_tiers = None


@bot.event
@asyncio.coroutine
def on_ready():
    print('Logged in as')
    print(bot.user.name)
    print(bot.user.id)
    print('------')


@bot.event
async def on_reaction_add(reaction, user):
    if user == bot.user:
        return
    if reaction.message.embeds and reaction.emoji == "❌":
        for role in user.roles:
            if role.id == MOD_ROLE_ID:
                print("Message deleted by mod " + user.name)
                await bot.delete_message(reaction.message)
                return
        for embed in reaction.message.embeds:
            for field in embed.get('fields'):
                if field.get('name') == "Created by:" \
                        and field.get('value', "").lower() == user.name.lower():
                    print("Message deleted by user " + user.name)
                    await bot.delete_message(reaction.message)
                    return
    if reaction.message.embeds and check_footer(reaction.message, "raid"):
        print("notifiying raid: " + user.name)
        await notify_raid(reaction.message)
        return

    if reaction.message.embeds and check_footer(reaction.message, "ex-"):
        role_name = reaction.message.embeds[0].get('footer', {}).get('text')
        if role_name and role_name != "ex-raid":
            roles = reaction.message.server.roles
            role = None
            for r in roles:
                if r.name == role_name or r.id == role_name:
                    role = r
                    break
            if not role:
                role = await bot.create_role(reaction.message.server,
                                             name=role_name, mentionable=True)
                await asyncio.sleep(0.25)
            print("Adding user " + user.name + " to role " + role_name)
            await bot.add_roles(user, role)
            await asyncio.sleep(0.1)
        print("notifiying exraid: " + user.name)
        await notify_exraid(reaction.message)
        await asyncio.sleep(0.1)
        await selfdestuctmessage(reaction.message.channel,
                                 "<@{}> you have been added to {}".
                                 format(user.id, role_name), 10)
        return


@bot.event
async def on_reaction_remove(reaction, user):
    if user == bot.user:
        return
    if reaction.message.embeds and check_footer(reaction.message, "raid"):
        print("notifiying raid")
        await notify_raid(reaction.message)
    if reaction.message.embeds and check_footer(reaction.message, "ex-"):
        role_name = reaction.message.embeds[0].get('footer', {}).get('text')
        if role_name and role_name != "ex-raid":
            for role in user.roles:
                if role.name == role_name:
                    await bot.remove_roles(user, role)
        print("notifiying exraid")
        await notify_exraid(reaction.message)
        await asyncio.sleep(0.1)
        await selfdestuctmessage(reaction.message.channel,
                                 "<@{}> you have left {}".
                                 format(user.id, role_name), 10)


@bot.command(pass_context=True)
async def info(ctx):
    embed = discord.Embed(title="PoGo Bot",
                          description="Pokemon Go Discord Bot.",
                          color=0xeee657)
    # give info about you here
    embed.add_field(name="Author", value="D4rKngh7")
    # Shows the number of servers the bot is member of.
    embed.add_field(name="Server count", value="{}".format(len(bot.guilds)))
    # give users a link to invite this bot to their server
    embed.add_field(name="Invite",
                    value="[Invite link](<insert your OAuth invitation link here>)")
    await ctx.send(embed=embed)


@bot.command(aliases=["clr"],
             brief="Clear all members from role",
             pass_context=True)
async def clearrole(ctx, rolex):
    if not await checkmod(ctx):
        return

    members = bot.get_all_members()
    count = 0
    for member in members:
        for role in member.roles:
            if role.name.lower() == rolex.lower():
                print("Found member {} with role {}".format(member.name,
                                                            role.name))
                await bot.remove_roles(member, role)
                count += 1
    await bot.delete_message(ctx.message)
    await asyncio.sleep(0.1)
    await selfdestuctmessage(ctx.message.channel,
                             "Cleared {} members from role {}".format(count,
                                                                      rolex))


@bot.command(aliases=[""],
             brief="Purge messages from channel",
             pass_context=True)
async def purge(ctx, pinned=False):
    def notpinned(message):
        return not message.pinned

    if await checkmod(ctx):
        await bot.purge_from(ctx.message.channel,
                             check=notpinned if not pinned else None)
        await asyncio.sleep(0.1)
        # await bot.delete_message(ctx.message)


@bot.command(aliases=["r"],
             usage="!raid [pokemon] [location] [time]",
             help="Create a new raid posting. Users will also be listed in "
                  "the post by team. Press 1, 2, or 3 to specify other teamless"
                  "guests that will accompany you.",
             brief="Create a new raid post. !raid <pkmn> <location> <time>",
             pass_context=True)
async def raid(ctx, pkmn, location, timer="45 mins"):

    if not await checkmod(ctx):
        return

    thumb = None
    descrip = "Located: {}\nTime: {}".format(location, timer)
    pkmn_case = pkmn[0].upper() + pkmn[1:].lower()
    if pkmn_case in locale['pokemon']:
        pkmn_id = locale['pokemon'][pkmn_case]
        if IMAGE_URL:
            thumb = IMAGE_URL.format(pkmn_id)
        lvl20cpm = cp_multipliers['20']
        lvl25cpm = cp_multipliers['25']

        stats = base_stats["{0:03d}".format(pkmn_id)]

        mincp20 = int(((stats['attack'] + 10.0) *
                       pow((stats['defense'] + 10.0), 0.5) *
                       pow((stats['stamina'] + 10.0), 0.5) *
                       pow(lvl20cpm, 2)) / 10.0)
        maxcp20 = int(((stats['attack'] + 15.0) *
                       pow((stats['defense'] + 15.0), 0.5) *
                       pow((stats['stamina'] + 15.0), 0.5) *
                       pow(lvl20cpm, 2)) / 10.0)

        descrip += "\nCP: ({}-{})".format(mincp20, maxcp20)

    embed = discord.Embed(title="Raid - {}".format(pkmn_case),
                          description=descrip)
    if thumb:
        embed.set_thumbnail(url=thumb)
    embed.add_field(name="<:mystic:446018237721739276>Mystic (0)", value="[]",
                    inline=True)
    embed.add_field(name="<:valor:446018241542750209>Valor (0)", value="[]",
                    inline=True)
    embed.add_field(name="<:instinct:446018246605537300>Instinct (0)",
                    value="[]", inline=True)
    embed.add_field(name="Total:", value="0", inline=False)
    embed.add_field(name="Created by:", value=ctx.message.author.name,
                    inline=True)
    embed.set_footer(text="raid")
    msg = await bot.send_message(ctx.message.channel, embed=embed)
    await asyncio.sleep(0.1)
    await bot.delete_message(ctx.message)
    await bot.pin_message(msg)
    await bot.add_reaction(msg, getEmoji("mystic"))
    await asyncio.sleep(0.1)
    await bot.add_reaction(msg, getEmoji("valor"))
    await asyncio.sleep(0.1)
    await bot.add_reaction(msg, getEmoji("instinct"))
    await asyncio.sleep(0.1)
    await bot.add_reaction(msg, "1⃣")
    await asyncio.sleep(0.1)
    await bot.add_reaction(msg, "2⃣")
    await asyncio.sleep(0.1)
    await bot.add_reaction(msg, "3⃣")
    await asyncio.sleep(0.1)
    await bot.add_reaction(msg, "❌")
    await asyncio.sleep(3600)
    await bot.delete_message(msg)


@bot.command(aliases=["ex"],
             name="exraid",
             brief="Create a new Ex-Raid post. !exraid <pkmn> <location>"
                   " <data> <role>",
             help="Create a new Ex-Raid post. Reactions to the post will add"
                  " the user to the provided role. Users will also be listed in"
                  " the post by team. Press 1, 2, or 3 to specify other "
                  "teamless guests.",
             usage="!exraid [pokemon] [location] [date] [role]",
             pass_context=True)
async def exraid(ctx, pkmn, location, date, role="ex-raid"):
    if not await checkmod(ctx):
        return

    thumb = None

    descrip = "Located: {}\nDate: {}".format(location, date)

    pkmn_case = pkmn[0].upper() + pkmn[1:].lower()
    if pkmn_case in locale['pokemon']:
        pkmn_id = locale['pokemon'][pkmn_case]
        if IMAGE_URL:
            thumb = IMAGE_URL.format(pkmn_id)
        lvl20cpm = cp_multipliers['20']
        lvl25cpm = cp_multipliers['25']

        stats = base_stats["{0:03d}".format(pkmn_id)]

        mincp20 = int(((stats['attack'] + 10.0) *
                       pow((stats['defense'] + 10.0), 0.5) *
                       pow((stats['stamina'] + 10.0), 0.5) *
                       pow(lvl20cpm, 2)) / 10.0)
        maxcp20 = int(((stats['attack'] + 15.0) *
                       pow((stats['defense'] + 15.0), 0.5) *
                       pow((stats['stamina'] + 15.0), 0.5) *
                       pow(lvl20cpm, 2)) / 10.0)

        descrip += "\nCP: ({}-{})".format(mincp20, maxcp20)

    embed = discord.Embed(title="EX-Raid - {}".format(pkmn_case),
                          description=descrip)
    if thumb:
        embed.set_thumbnail(url=thumb)
    embed.add_field(name="Mystic:", value="[]", inline=True)
    embed.add_field(name="Valor:", value="[]", inline=True)
    embed.add_field(name="Instinct:", value="[]", inline=True)
    embed.set_footer(text=role)
    msg = await bot.send_message(ctx.message.channel, embed=embed)
    await asyncio.sleep(0.25)
    await bot.delete_message(ctx.message)
    await bot.pin_message(msg)
    await bot.add_reaction(msg, getEmoji("mystic"))
    await asyncio.sleep(0.25)
    await bot.add_reaction(msg, getEmoji("valor"))
    await asyncio.sleep(0.25)
    await bot.add_reaction(msg, getEmoji("instinct"))
    await asyncio.sleep(0.25)
    await bot.add_reaction(msg, "1⃣")
    await asyncio.sleep(0.25)
    await bot.add_reaction(msg, "2⃣")
    await asyncio.sleep(0.25)
    await bot.add_reaction(msg, "3⃣")
    await asyncio.sleep(0.25)
    await bot.add_reaction(msg, "❌")


def getEmoji(name):
    return discord.utils.get(bot.get_all_emojis(), name=name)


def check_role(member, rolex):
    for role in member.roles:
        if str(role.id) == str(rolex.lower()) or str(
                        role.name.lower() == str(rolex.lower())):
            return True
    return False


def check_footer(msg, val):
    if msg.embeds:
        for embed in msg.embeds:
            if embed.get('footer', {}).get('text', "").startswith(val):
                return True
    return False


async def notify_raid(msg):
    mystic = ""
    valor = ""
    instinct = ""
    m_tot = 0
    v_tot = 0
    i_tot = 0
    total = 0
    for reaction in msg.reactions:
        if isinstance(reaction.emoji, str):
            if reaction.emoji == "1⃣":
                total += reaction.count - 1
            elif reaction.emoji == "2⃣":
                total += 2 * (reaction.count - 1)
            elif reaction.emoji == "3⃣":
                total += 3 * (reaction.count - 1)
        else:
            if reaction.emoji.name == 'mystic':
                users = await bot.get_reaction_users(reaction)
                for user in users:
                    if user == bot.user:
                        continue
                    mystic += user.display_name + ","
                    m_tot += 1
                    total += 1
                mystic = mystic.rstrip(",")
            elif reaction.emoji.name == 'valor':
                users = await bot.get_reaction_users(reaction)
                for user in users:
                    if user == bot.user:
                        continue
                    valor += user.display_name + ","
                    v_tot += 1
                    total += 1
                valor = valor.rstrip(", ")
            elif reaction.emoji.name == 'instinct':
                users = await bot.get_reaction_users(reaction)
                for user in users:
                    if user == bot.user:
                        continue
                    instinct += user.display_name + ","
                    i_tot += 1
                    total += 1
                instinct = instinct.rstrip(", ")
    mystic = "[" + mystic + "]"
    valor = "[" + valor + "]"
    instinct = "[" + instinct + "]"

    for field in msg.embeds[0]['fields']:
        if field.get('name', "").startswith("Created"):
            created_by = field.get('value')

    em = discord.Embed(title=msg.embeds[0]['title'],
                       description=msg.embeds[0]['description'])
    em.set_thumbnail(url=msg.embeds[0]['thumbnail'].get('url', None))
    em.add_field(name="<:mystic:446018237721739276>Mystic ({})".format(m_tot),
                 value=mystic, inline=True)
    em.add_field(name="<:valor:446018241542750209>Valor ({})".format(v_tot),
                 value=valor, inline=True)
    em.add_field(
        name="<:instinct:446018246605537300>Instinct ({})".format(i_tot),
        value=instinct, inline=False)
    em.add_field(name="Total:", value=total, inline=True)
    em.add_field(name="Created by:", value=created_by, inline=True)
    em.set_footer(text="Raid")

    await bot.edit_message(message=msg, embed=em)


async def notify_exraid(msg):
    mystic = ""
    valor = ""
    instinct = ""
    m_tot = 0
    v_tot = 0
    i_tot = 0
    total = 0
    for reaction in msg.reactions:
        if isinstance(reaction.emoji, str):
            if reaction.emoji == "1⃣":
                total += reaction.count - 1
            elif reaction.emoji == "2⃣":
                total += 2 * (reaction.count - 1)
            elif reaction.emoji == "3⃣":
                total += 3 * (reaction.count - 1)
        else:
            if reaction.emoji.name == 'mystic':
                users = await bot.get_reaction_users(reaction)
                for user in users:
                    if user == bot.user:
                        continue
                    mystic += user.display_name + ","
                    m_tot += 1
                    total += 1
                mystic = mystic.rstrip(",")
            elif reaction.emoji.name == 'valor':
                users = await bot.get_reaction_users(reaction)
                for user in users:
                    if user == bot.user:
                        continue
                    valor += user.display_name + ","
                    v_tot += 1
                    total += 1
                valor = valor.rstrip(", ")
            elif reaction.emoji.name == 'instinct':
                users = await bot.get_reaction_users(reaction)
                for user in users:
                    if user == bot.user:
                        continue
                    instinct += user.display_name + ","
                    i_tot += 1
                    total += 1
                instinct = instinct.rstrip(", ")
    mystic = "[" + mystic + "]"
    valor = "[" + valor + "]"
    instinct = "[" + instinct + "]"

    created_by = None
    for field in msg.embeds[0]['fields']:
        if field.get('name', "").startswith("Created"):
            created_by = field.get('value')

    em = discord.Embed(title=msg.embeds[0]['title'],
                       description=msg.embeds[0]['description'])
    em.set_thumbnail(url=msg.embeds[0]['thumbnail'].get('url', None))
    em.add_field(name="<:mystic:446018237721739276>Mystic ({})".format(m_tot),
                 value=mystic, inline=True)
    em.add_field(name="<:valor:446018241542750209>Valor ({})".format(v_tot),
                 value=valor, inline=True)
    em.add_field(
        name="<:instinct:446018246605537300>Instinct ({})".format(i_tot),
        value=instinct, inline=False)
    em.add_field(name="Total:", value=total, inline=True)
    em.add_field(name="Created by:", value=created_by, inline=True)
    em.set_footer(text=msg.embeds[0]['footer'].get('text'))

    await bot.edit_message(message=msg, embed=em)


async def checkmod(ctx):
    if not check_role(ctx.message.author, MOD_ROLE_ID):
        print("Not a mod!")
        await bot.delete_message(ctx.message)
        msg = await selfdestuctmessage(ctx.message.channel,
                                       "You must be a mod in order to use " +
                                       "this command!")
        return False
    return True


async def selfdestuctmessage(dest, cont, delay=5, tts=False, e=None):
    msg = await bot.send_message(destination=dest, content=cont,
                                 tts=tts, embed=e)
    await asyncio.sleep(delay)
    await bot.delete_message(msg)


cfg = configparser.ConfigParser()
cfg.read('config.ini')
bot.command_prefix = cfg['PoGoBot']['BotPrefix']
MOD_ROLE_ID = cfg['PoGoBot']['ModRoleID']
IMAGE_URL = cfg['PoGoBot']['ImageURL']
with open(os.path.join('locales',
                       '{}.json'.format(cfg['PoGoBot']['Locale']))) as f:
    locale = json.load(f)
with open(os.path.join('data', 'base_stats.json')) as fb:
    base_stats = json.load(fb)
with open(os.path.join('data', 'cp_multipliers.json')) as fc:
    cp_multipliers = json.load(fc)
with open(os.path.join('data', 'boss_tiers.json')) as fc:
    boss_tiers = json.load(fc)

bot.run(cfg['PoGoBot']['BotToken'])
