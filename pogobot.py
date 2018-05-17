#!/usr/bin/python3
# -*- coding: utf-8 -*-

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

running_updater = False

@bot.event
@asyncio.coroutine
def on_ready():
    print('Logged in as')
    print(discord.version_info)
    print(bot.user.name)
    print(bot.user.id)
    print(MOD_ROLE_ID)
    print(IMAGE_URL)
    print('------')


# @bot.event
# async def on_raw_reaction_add(*payload):
#     print(payload)


@bot.event
async def on_reaction_add(reaction, user):
    if user == bot.user or reaction.message.author != bot.user:
        return
    if reaction.message.embeds and reaction.emoji == "❌":
        if check_role(user, MOD_ROLE_ID):
                print("Message deleted by mod " + user.name)
                await reaction.message.delete()
                return
        for embed in reaction.message.embeds:
            if embed.author == user.name:
                    print("Message deleted by user " + user.name)
                    await reaction.message.delete()
                    return
    if reaction.message.embeds and check_footer(reaction.message, "raid"):
        print("notifiying raid: " + user.name)
        await notify_raid(reaction.message)
        return

    if reaction.message.embeds and check_footer(reaction.message, "ex-"):
        print("notifiying exraid: " + user.name)
        await notify_exraid(reaction.message)
        await asyncio.sleep(0.1)

        return


@bot.event
async def on_reaction_remove(reaction, user):
    if user == bot.user:
        return
    if reaction.message.embeds and check_footer(reaction.message, "raid"):
        print("notifiying raid")
        await notify_raid(reaction.message)
    if reaction.message.embeds and check_footer(reaction.message, "ex-"):
        role_name = reaction.message.embeds[0].footer.text
        if role_name and role_name != "ex-raid":
            for role in user.roles:
                if role.name == role_name:
                    await user.remove_roles(role)
        print("notifiying exraid")
        await notify_exraid(reaction.message)
        await asyncio.sleep(0.1)
        await reaction.message.channel.send("<@{}> you have left {}".
                                            format(user.id, role_name),
                                            delete_after=10)


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
                await member.remove_roles(role)
                count += 1
    await ctx.message.delete()
    await asyncio.sleep(0.1)
    await ctx.message.channel.send(
        "Cleared {} members from role {}".format(count, rolex), delete_after=5)


@bot.command(aliases=[],
             brief="Purge messages from channel",
             pass_context=True)
async def purge(ctx, pinned=False):
    def notpinned(message):
        return not message.pinned

    if await checkmod(ctx):
        await ctx.message.channel.purge(check=notpinned if not pinned else None)
        await asyncio.sleep(0.1)
        # await bot.delete_message(ctx.message)


@bot.command(aliases=["sex"],
             brief="Manually scan channel for ex-raid posts. !scanex ",
             pass_context=True)
async def scanex(ctx):
    if not await checkmod(ctx):
        return

    await manualexscan(ctx.message.channel)
    await ctx.message.delete()
    await ctx.message.channel.send("Scan completed", delete_after=10)


@bot.command(aliases=["exu"],
             brief="Continuously update ex-raid channel manually. "
                   "!exupdater [minutes]",
             pass_context=True)
async def exupdater(ctx, minutes=5):
    global running_updater
    if not await checkmod(ctx):
        return

    ctx.message.delete()

    if minutes > 0:
        running_updater = True
        await ctx.send("Scanning every {} minutes.".format(minutes),
                       delete_after=10)
    else:
        running_updater = False
        return

    while running_updater:
        await manualexscan(ctx.message.channel)
        await ctx.message.channel.send("Scan completed", delete_after=10)
        await asyncio.sleep(minutes*60)

    await ctx.send("exupdater stopped", delete_after=60)


async def manualexscan(channel):
    async for msg in channel.history(limit=500):
        if msg.author != bot.user:
            continue
        if msg.embeds and msg.embeds[0].footer and \
                msg.embeds[0].footer.text.startswith("ex-"):
            await notify_exraid(msg)


@bot.command(aliases=[],
             brief="Clear raid posts from channel. !clearraids",
             pass_context=True)
async def clearraids(ctx):

    def raid(msg):
        return msg.author == bot.user and msg.embeds and \
               msg.embeds[0].footer and \
               msg.embeds[0].footer.text == "raid"

    if not await checkmod(ctx):
        return
    await ctx.message.channel.purge(limit=500, check=raid)
    await ctx.send("Cleared all raid posts", delete_after=10)


@bot.command(aliases=["r"],
             usage="!raid [pokemon] [location] [time]",
             help="Create a new raid posting. Users will also be listed in "
                  "the post by team. Press 1, 2, or 3 to specify other teamless"
                  "guests that will accompany you.",
             brief="Create a new raid post. !raid <pkmn> <location> <time>",
             pass_context=True)
async def raid(ctx, pkmn, location, timer="45 mins", url=None):
    if not await checkmod(ctx):
        return

    #check for valid url
    if url and not url.startswith("http"):
        url = None

    thumb = None
    descrip = ""
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
        mincp25 = int(((stats['attack'] + 10.0) *
                       pow((stats['defense'] + 10.0), 0.5) *
                       pow((stats['stamina'] + 10.0), 0.5) *
                       pow(lvl25cpm, 2)) / 10.0)
        maxcp25 = int(((stats['attack'] + 15.0) *
                       pow((stats['defense'] + 15.0), 0.5) *
                       pow((stats['stamina'] + 15.0), 0.5) *
                       pow(lvl25cpm, 2)) / 10.0)

        descrip = "CP: ({}-{})  WB: ({}-{})".format(mincp20, maxcp20,
                                                         mincp25, maxcp25)

    embed = discord.Embed(title="Raid - {}".format(pkmn_case),
                          description=descrip, url=url)
    embed.set_author(name=ctx.message.author.name)
    if thumb:
        embed.set_thumbnail(url=thumb)
    embed.add_field(name="Location:", value=location, inline=True)
    embed.add_field(name="Time:", value=timer + "\n", inline=True)
    embed.add_field(name="** **", value="** **", inline=False)
    embed.add_field(name="<:mystic:446018237721739276>__Mystic (0)__", value="[]",
                    inline=True)
    embed.add_field(name="<:valor:446018241542750209>__Valor (0)__", value="[]",
                    inline=True)
    embed.add_field(name="<:instinct:446018246605537300>__Instinct (0)__",
                    value="[]", inline=True)
    embed.add_field(name="**Total:**", value="0", inline=False)
    embed.add_field(name="Created by:",
                    value="*{}*".format(ctx.message.author.name),
                    inline=False)
    embed.set_footer(text="raid")
    msg = await ctx.message.channel.send(embed=embed)
    await asyncio.sleep(0.1)
    await ctx.message.delete()
    await msg.pin()
    await msg.add_reaction(getEmoji("mystic"))
    await asyncio.sleep(0.1)
    await msg.add_reaction(getEmoji("valor"))
    await asyncio.sleep(0.1)
    await msg.add_reaction(getEmoji("instinct"))
    await asyncio.sleep(0.1)
    await msg.add_reaction("1⃣")
    await asyncio.sleep(0.1)
    await msg.add_reaction("2⃣")
    await asyncio.sleep(0.1)
    await msg.add_reaction("3⃣")
    await asyncio.sleep(0.1)
    await msg.add_reaction("❌")


@bot.command(aliases=["rt"],
             usage="!raidtime [location] [time]",
             brief="Edit the time on a previous raid post. "
                   "!raidtime <location> <time>",
             pass_context=True)
async def raidtime(ctx, loc, timer="45 mins"):

    if not await checkmod(ctx):
        return

    async for msg in ctx.message.channel.history():
        if msg.author != bot.user or not msg.embeds:
            continue
        for field in msg.embeds[0].fields:
            if field.name.startswith("Location") and \
                            field.value.lower() == loc.lower():
                for i in range(0, len(msg.embeds[0].fields)):
                    field2 = msg.embeds[0].fields[i]
                    if field2.name.startswith("Time") or \
                            field2.name.startswith("Date"):
                        msg.embeds[0].set_field_at(i, name=field2.name,
                                                   value=timer,
                                                   inline=True)
                        await msg.edit(embed=msg.embeds[0])
                        await ctx.send("Updated Raid at {} to Time: {}"
                                       .format(loc, timer))
                        await ctx.message.delete()
                        return
    await ctx.message.delete()
    await ctx.send("Unable to find Raid at {}".format(loc), delete_after=30)


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

    descrip = ""

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
        mincp25 = int(((stats['attack'] + 10.0) *
                       pow((stats['defense'] + 10.0), 0.5) *
                       pow((stats['stamina'] + 10.0), 0.5) *
                       pow(lvl25cpm, 2)) / 10.0)
        maxcp25 = int(((stats['attack'] + 15.0) *
                       pow((stats['defense'] + 15.0), 0.5) *
                       pow((stats['stamina'] + 15.0), 0.5) *
                       pow(lvl25cpm, 2)) / 10.0)

        descrip = "CP: ({}-{})  WB: ({}-{})".format(mincp20, maxcp20,
                                                         mincp25, maxcp25)

    embed = discord.Embed(title="EX-Raid - {}".format(pkmn_case),
                          description=descrip)
    if thumb:
        embed.set_thumbnail(url=thumb)
    embed.add_field(name="Location:", value=location, inline=True)
    embed.add_field(name="Date:", value=date + "\n", inline=True)
    embed.add_field(name="** **", value="** **", inline=False)
    embed.add_field(name="<:mystic:446018237721739276>__Mystic (0)__", value="[]",
                    inline=True)
    embed.add_field(name="<:valor:446018241542750209>__Valor (0)__", value="[]",
                    inline=True)
    embed.add_field(name="<:instinct:446018246605537300>__Instinct (0)__",
                    value="[]", inline=True)
    embed.add_field(name="Total:", value="0", inline=False)
    embed.set_footer(text=role)
    msg = await ctx.message.channel.send(embed=embed)
    await asyncio.sleep(0.25)
    await ctx.message.delete()
    await msg.pin()
    await msg.add_reaction(getEmoji("mystic"))
    await asyncio.sleep(0.25)
    await msg.add_reaction(getEmoji("valor"))
    await asyncio.sleep(0.25)
    await msg.add_reaction(getEmoji("instinct"))
    await asyncio.sleep(0.25)
    await msg.add_reaction("1⃣")
    await asyncio.sleep(0.25)
    await msg.add_reaction("2⃣")
    await asyncio.sleep(0.25)
    await msg.add_reaction("3⃣")
    await asyncio.sleep(0.25)
    await msg.add_reaction("❌")


def getEmoji(name):
    return discord.utils.get(bot.emojis, name=name)


def check_role(member, rolex):
    for role in member.roles:
        if (str(role.id) == rolex) or (str(role.name.lower()) == str(rolex.lower())):
            return True
    return False


def check_footer(msg, val):
    if msg.embeds:
        for embed in msg.embeds:
            if embed.footer and embed.footer.text.startswith(val):
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
                users = await reaction.users().flatten()
                for user in users:
                    if user == bot.user:
                        continue
                    mystic += user.mention + ","
                    m_tot += 1
                    total += 1
                mystic = mystic.rstrip(",")
            elif reaction.emoji.name == 'valor':
                users = await reaction.users().flatten()
                for user in users:
                    if user == bot.user:
                        continue
                    valor += user.mention + ","
                    v_tot += 1
                    total += 1
                valor = valor.rstrip(", ")
            elif reaction.emoji.name == 'instinct':
                users = await reaction.users().flatten()
                for user in users:
                    if user == bot.user:
                        continue
                    instinct += user.mention + ","
                    i_tot += 1
                    total += 1
                instinct = instinct.rstrip(", ")
    mystic = "[" + mystic + "]"
    valor = "[" + valor + "]"
    instinct = "[" + instinct + "]"

    em = discord.Embed(title=msg.embeds[0].title,
                       description=msg.embeds[0].description,
                       url=msg.embeds[0].url)
    em.set_author(name=msg.embeds[0].author.name)
    created_by = None
    for field in msg.embeds[0].fields:
        if field.name.startswith("Created"):
            created_by = field.value.strip("* ")
        elif field.name.startswith("Location"):
            em.add_field(name="Location:", value=field.value, inline=True)
        elif field.name.startswith("Time"):
            em.add_field(name="Time:", value=field.value, inline=True)
    if msg.embeds[0].thumbnail:
        em.set_thumbnail(url=msg.embeds[0].thumbnail.url)
    em.add_field(name="** **", value="** **", inline=False)

    em.add_field(name="<:mystic:446018237721739276>__Mystic ({})__".format(m_tot),
                 value=mystic, inline=True)
    em.add_field(name="<:valor:446018241542750209>__Valor ({})__".format(v_tot),
                 value=valor, inline=True)
    em.add_field(
        name="<:instinct:446018246605537300>__Instinct ({})__".format(i_tot),
        value=instinct, inline=False)
    em.add_field(name="**Total:**", value="**{}**".format(total), inline=False)
    em.add_field(name="Created by:", value="*{}*".format(created_by), inline=False)
    em.set_footer(text="raid")

    await msg.edit(embed=em)


async def notify_exraid(msg):
    mystic = ""
    valor = ""
    instinct = ""
    m_tot = 0
    v_tot = 0
    i_tot = 0
    total = 0
    role_name = msg.embeds[0].footer.text
    role = None
    if role_name and role_name != "ex-raid":
        role = await getrolefromname(msg.guild, role_name, True)
    for reaction in msg.reactions:
        if isinstance(reaction.emoji, str):
            if reaction.emoji == "1⃣":
                total += reaction.count - 1
            elif reaction.emoji == "2⃣":
                total += 2 * (reaction.count - 1)
            elif reaction.emoji == "3⃣":
                total += 3 * (reaction.count - 1)
            elif reaction.emoji == "❌":
                users = await reaction.users().flatten()
                for user in users:
                    if user == bot.user:
                        continue
                    if check_role(user, MOD_ROLE_ID):
                        await msg.delete()
                        return
        else:
            if reaction.emoji.name == 'mystic':
                users = await reaction.users().flatten()
                for user in users:
                    if user == bot.user:
                        continue
                    if role and role not in user.roles:
                        await user.add_roles(role, atomic=True)
                        print("User {} added to role {}".format(user.name,
                                                                role_name))
                        await msg.channel.send("{} you have been added to {}".
                                         format(user.mention, role_name),
                                         delete_after=10)
                    mystic += user.mention + ","
                    m_tot += 1
                    total += 1
                mystic = mystic.rstrip(",")
            elif reaction.emoji.name == 'valor':
                users = await reaction.users().flatten()
                for user in users:
                    if user == bot.user:
                        continue
                    if role and role not in user.roles:
                        await user.add_roles(role, atomic=True)
                        print("User {} added to role {}".format(user.name,
                                                                role_name))
                        await msg.channel.send("{} you have been added to {}".
                                         format(user.mention, role_name),
                                         delete_after=10)
                    valor += user.mention + ","
                    v_tot += 1
                    total += 1
                valor = valor.rstrip(", ")
            elif reaction.emoji.name == 'instinct':
                users = await reaction.users().flatten()
                for user in users:
                    if user == bot.user:
                        continue
                    if role and role not in user.roles:
                        await user.add_roles(role, atomic=True)
                        print("User {} added to role {}".format(user.name,
                                                                role_name))
                        await msg.channel.send("{} you have been added to {}".
                                         format(user.mention, role_name),
                                         delete_after=10)
                    instinct += user.mention + ","
                    i_tot += 1
                    total += 1
                instinct = instinct.rstrip(", ")
    mystic = "[" + mystic + "]"
    valor = "[" + valor + "]"
    instinct = "[" + instinct + "]"

    em = discord.Embed(title=msg.embeds[0].title,
                       description=msg.embeds[0].description,
                       url=msg.embeds[0].url)
    created_by = None
    for field in msg.embeds[0].fields:
        if field.name.startswith("Created"):
            created_by = field.value
        elif field.name.startswith("Location"):
            em.add_field(name="Location:", value=field.value, inline=True)
        elif field.name.startswith("Date"):
            em.add_field(name="Date:", value=field.value, inline=True)

    em.set_thumbnail(url=msg.embeds[0].thumbnail.url)
    em.add_field(name="** **", value="** **", inline=False)
    em.add_field(name="<:mystic:446018237721739276>__Mystic ({})__".format(m_tot),
                 value=mystic, inline=True)
    em.add_field(name="<:valor:446018241542750209>__Valor ({})__".format(v_tot),
                 value=valor, inline=True)
    em.add_field(
        name="<:instinct:446018246605537300>__Instinct ({})__".format(i_tot),
        value=instinct, inline=False)
    em.add_field(name="**Total:**", value=total, inline=True)
    em.set_footer(text=msg.embeds[0].footer.text)

    await msg.edit(embed=em)


async def checkmod(ctx):
    if not check_role(ctx.message.author, MOD_ROLE_ID):
        print("Not a mod!")
        await ctx.message.channel.send("You must be a mod in order to use " +
                                       "this command!", delete_after=10)
        await ctx.message.delete()
        return False
    return True


async def getrolefromname(guild, role_name, create_new_role=False):
    roles = guild.roles
    role = None
    for r in roles:
        if r.name == role_name or r.id == role_name:
            role = r
            break
    if not role and create_new_role:
        role = await guild.create_role(name=role_name, mentionable=True,
                                       reason="Role created for ex-raid")
        await asyncio.sleep(0.25)
    return role


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
