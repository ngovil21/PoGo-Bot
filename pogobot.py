#!/usr/bin/python3
# -*- coding: utf-8 -*-

import discord
import os

from discord.ext import commands
import asyncio
import configparser
import json

from utility import getfieldbyname, check_role, check_footer, \
    getrolefromname

BOT_PREFIX = "!"
BOT_TOKEN = None
MOD_ROLE_ID = None
IMAGE_URL = ""
EX_RAID_CHANNEL = None

bot = commands.Bot(command_prefix=BOT_PREFIX, case_insensitive=True,
                   description='A bot that manages Pokemon Go Discord communities.')

locale = None
base_stats = None
cp_multipliers = None
boss_tiers = None

running_updater = False


@bot.event
@asyncio.coroutine
async def on_ready():
    global running_updater
    print(discord.version_info)
    print('Logged in as: {}'.format(bot.user.name))
    print('Bot ID: {}'.format(bot.user.id))
    print("Mod Role ID: {}".format(MOD_ROLE_ID))
    print("Image URL: {}".format(IMAGE_URL))
    print("Ex-Raid Channel: ".format(EX_RAID_CHANNEL))
    print('------')

    if EX_RAID_CHANNEL:
        exchan = bot.get_channel(EX_RAID_CHANNEL)
        if exchan:
            running_updater = True
            await exchan.send("Scanning ex-raid channel for updates",
                              delete_after=30.0)
            await exupdaterloop(exchan, 5)


# @bot.event
# async def on_raw_reaction_add(*payload):
#     print(payload)

@bot.event
async def on_reaction_add(reaction, user):
    async def confirm(msg):
        if msg.author == user and msg.content.lower().startswith("y"):
            await msg.delete()
            return True
        return False

    channel = reaction.message.channel
    if user == bot.user or reaction.message.author != bot.user or \
            not reaction.message.embeds:
        return
    loc = getfieldbyname(reaction.message.embeds[0].fields, "Location")
    loc = loc.value if loc else "Unknown"
    if reaction.emoji == "❌":
        if check_role(user, MOD_ROLE_ID) or \
                        reaction.message.embeds[0].author == user.name:
            await channel.send("Are you sure you would like to "
                               "delete raid *{}*? (yes/no)".format(loc))
            try:
                await bot.wait_for("message", timeout=30.0, check=confirm)
            except asyncio.TimeoutError:
                await reaction.message.remove_reaction(reaction.emoji, user)
            else:
                print("Raid {} deleted by user {}".format(loc, user.name))
                await channel.send("Raid *{}* deleted by {}"
                                   .format(loc, user.name), delete_after=20.0)
                await reaction.message.delete()
            return
    if reaction.message.embeds and check_footer(reaction.message, "raid"):
        print("notifying raid {}: {} with {}".format(loc, user.name,
                                                      reaction.emoji))
        await notify_raid(reaction.message)
        if isinstance(reaction.emoji, str):
            await reaction.message.channel.send(
                "{} is bringing {} to raid {}".format(
                    user.name, reaction.emoji, loc))
        return

    if reaction.message.embeds and check_footer(reaction.message, "ex-"):
        print("notifying exraid {}: {} with {}".format(loc, user.name,
                                                       reaction.emoji))
        await notify_exraid(reaction.message)
        if isinstance(reaction.emoji, str):
            await reaction.message.channel.send(
                "{} is bringing {} to ex-raid *{}*".format(
                    user.name, reaction.emoji, loc))
        return


@bot.event
async def on_reaction_remove(reaction, user):
    if user == bot.user and not reaction.message.embeds:
        return
    loc = getfieldbyname(reaction.message.embeds[0].fields, "Location")
    loc = loc.value if loc else "Unknown"
    if check_footer(reaction.message, "raid"):
        print("Notifying raid: User {} is leaving {}".format(user.name, loc))
        await notify_raid(reaction.message)
    if check_footer(reaction.message, "ex-"):
        role_name = reaction.message.embeds[0].footer.text
        if role_name and role_name != "ex-raid" and \
                not isinstance(reaction.emoji, str):
            for role in user.roles:
                if role.name == role_name:
                    await user.remove_roles(role)
                    await reaction.message.channel.send(
                        "{} you have left *{}*".format(user.mention, role_name),
                        delete_after=10)
        print("Notifying Ex-raid: User {} is leaving {}".format(user.name, loc))
        await notify_exraid(reaction.message)
        await asyncio.sleep(0.1)


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
                    value="[Invite link](<OAuth invitation link here>)")
    await ctx.send(embed=embed)


@bot.command(aliases=["clr"],
             brief="[MOD] Clear all members from role",
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

    await ctx.send(
        "Cleared {} members from role {}".format(count, rolex), delete_after=5)
    await asyncio.sleep(0.1)
    await ctx.message.delete()


@bot.command(aliases=[],
             brief="Purge messages from channel",
             pass_context=True)
async def purge(ctx, pinned=False):
    def notpinned(message):
        return not message.pinned

    if await checkmod(ctx):
        await ctx.message.channel.purge(check=notpinned if not pinned else None)
        await asyncio.sleep(0.1)
        # await ctx.message.delete()


@bot.command(aliases=["sex"],
             brief="[MOD] Manually scan channel for ex-raid posts. !scanex ",
             pass_context=True)
async def scanex(ctx):
    if not await checkmod(ctx):
        return

    await manualexscan(ctx.message.channel)
    await ctx.send("Scan completed", delete_after=10)
    await ctx.message.delete()


@bot.command(aliases=["exu"],
             brief="[MOD] Continuously update ex-raid channel manually. "
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

    await exupdaterloop(ctx.message.channel, minutes)


async def exupdaterloop(channel, minutes):
    while running_updater:
        await manualexscan(channel)
        await asyncio.sleep(minutes * 60)

    await channel.send("exupdater stopped", delete_after=60)


async def manualexscan(channel):
    async for msg in channel.history(limit=500):
        if msg.author != bot.user:
            continue
        if msg.embeds and msg.embeds[0].footer and \
                msg.embeds[0].footer.text.startswith("ex-"):
            await notify_exraid(msg)


@bot.command(aliases=[],
             brief="[MOD] Clear raid posts from channel. !clearraids",
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

    # check for valid url
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
    embed.add_field(name=str(getEmoji("mystic")) + "__Mystic (0)__", value="[]",
                    inline=True)
    embed.add_field(name=str(getEmoji("valor")) + "__Valor (0)__", value="[]",
                    inline=True)
    embed.add_field(name=str(getEmoji("instinct")) + "__Instinct (0)__",
                    value="[]", inline=True)
    embed.add_field(name="**Total:**", value="0", inline=False)
    embed.set_footer(text="raid")
    msg = await ctx.send(embed=embed)
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
async def raidtime(ctx, loc, timer=None):
    if not await checkmod(ctx):
        return

    async for msg in ctx.message.channel.history():
        if msg.author != bot.user or not msg.embeds:
            continue
        for field in msg.embeds[0].fields:
            if field.name.startswith("Location") and \
                            loc.lower() in field.value.lower():
                for i in range(0, len(msg.embeds[0].fields)):
                    field2 = msg.embeds[0].fields[i]
                    if field2.name.startswith("Time") or \
                            field2.name.startswith("Date"):
                        if timer:
                            msg.embeds[0].set_field_at(i, name=field2.name,
                                                       value=timer,
                                                       inline=True)
                            await msg.edit(embed=msg.embeds[0])
                            await ctx.send("Updated Raid at *{}* to time: **{}**"
                                           .format(field.value, timer))
                            await ctx.message.delete()
                            return
                        else:
                            total = getfieldbyname(msg.embeds[0].fields,
                                                   "Total")
                            total = total.value if total else 0
                            await ctx.send(
                                "Raid at *{}* at time: **{}** has  __{}__  "
                                "people registered."
                                .format(field.value, field2.value, total))
                            await ctx.message.delete()
                            return
    await ctx.message.delete()
    await ctx.send("Unable to find Raid at {}".format(loc), delete_after=30)


@bot.command(aliases=["rm"],
             usage="!raidmessage [location] [msg]",
             brief="Message members in raid "
                   "!raidmessage <location> <msg>",
             pass_context=True)
async def raidmessage(ctx, loc, message):
    if not await checkmod(ctx):
        return

    async for msg in ctx.message.channel.history():
        if msg.author != bot.user or not msg.embeds:
            continue
        for field in msg.embeds[0].fields:
            if field.name.startswith("Location") and \
                            loc.lower() in field.value.lower():
                mentions = []
                for reaction in msg.reactions:
                    async for user in reaction.users():
                        if user == bot.user:
                            continue
                        if user.mention not in mentions:
                            mentions.append(user.mention)
                await ctx.send(message + " " + "".join(mentions))
                await ctx.message.delete()
                return
        await ctx.send("Cannot find raid *{}*".format(loc), delete_after=10.0)
        await ctx.message.delete()

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
    embed.add_field(name=str(getEmoji("mystic")) + "__Mystic (0)__",
                    value="[]",
                    inline=True)
    embed.add_field(name=str(getEmoji("valor")) + "__Valor (0)__", value="[]",
                    inline=True)
    embed.add_field(name=str(getEmoji("instinct")) + "__Instinct (0)__",
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

    embed = msg.embeds[0]
    for i in range(0, len(embed.fields)):
        if "Mystic" in embed.fields[i].name:
            embed.set_field_at(i, name=str(
                getEmoji("mystic")) + "__Mystic ({})__".format(m_tot),
                               value=mystic, inline=True)
        if "Valor" in embed.fields[i].name:
            embed.set_field_at(i, name=str(
                getEmoji("valor")) + "__Valor ({})__".format(v_tot),
                               value=valor, inline=True)
        if "Instinct" in embed.fields[i].name:
            msg.embeds[0].set_field_at(i, name=str(
                getEmoji("instinct")) + "__Instinct ({})__".format(i_tot),
                                       value=instinct, inline=True)
        if "Total" in embed.fields[i].name:
            msg.embeds[0].set_field_at(i, name="**Total:**",
                                       value="**{}**".format(total),
                                       inline=False)

    await msg.edit(embed=embed)


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
                                               delete_after=30.0)
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
                                               delete_after=30.0)
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
                                               delete_after=30.0)
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

    for field in msg.embeds[0].fields:
        if field.name.startswith("Location"):
            em.add_field(name="Location:", value=field.value, inline=True)
        elif field.name.startswith("Date"):
            em.add_field(name="Date:", value=field.value, inline=True)

    em.set_thumbnail(url=msg.embeds[0].thumbnail.url)
    em.add_field(name="** **", value="** **", inline=False)
    em.add_field(
        name=str(getEmoji("mystic")) + "__Mystic ({})__".format(m_tot),
        value=mystic, inline=True)
    em.add_field(name=str(getEmoji("valor")) + "__Valor ({})__".format(v_tot),
                 value=valor, inline=True)
    em.add_field(
        name=str(getEmoji("instinct")) + "__Instinct ({})__".format(i_tot),
        value=instinct, inline=False)
    em.add_field(name="**Total:**", value=total, inline=True)
    em.set_footer(text=msg.embeds[0].footer.text)

    await msg.edit(embed=em)


async def checkmod(ctx):
    if not check_role(ctx.message.author, MOD_ROLE_ID):
        print("Not a mod!")
        await ctx.send("You must be a mod in order to use " +
                       "this command!", delete_after=10)
        await ctx.message.delete()
        return False
    return True


def getEmoji(name):
    return discord.utils.get(bot.emojis, name=name)

if __name__ == "__main__":
    cfg = configparser.ConfigParser()
    cfg.read('config.ini')
    bot.command_prefix = cfg['PoGoBot']['BotPrefix']
    MOD_ROLE_ID = cfg['PoGoBot']['ModRoleID']
    IMAGE_URL = cfg['PoGoBot']['ImageURL']
    EX_RAID_CHANNEL = cfg['PoGoBot']['ExRaidChannel']
    with open(os.path.join('locales', '{}.json'
            .format(cfg['PoGoBot']['Locale'] or 'en'))) as f:
        locale = json.load(f)
    with open(os.path.join('data', 'base_stats.json')) as fb:
        base_stats = json.load(fb)
    with open(os.path.join('data', 'cp_multipliers.json')) as fc:
        cp_multipliers = json.load(fc)
    with open(os.path.join('data', 'boss_tiers.json')) as fc:
        boss_tiers = json.load(fc)

    bot.run(cfg['PoGoBot']['BotToken'])
