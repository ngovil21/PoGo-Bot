#!/usr/bin/python3
# -*- coding: utf-8 -*-
import string

import discord
import os

from discord import PartialEmoji
from discord.ext import commands
import asyncio
import configparser
import json
import datetime

from utility import getfieldbyname, check_role, check_footer, \
    getrolefromname, get_static_map_url, load_locale, load_base_stats, \
    load_cp_multipliers, load_gyms, get_gym_coords, get_cp_range, \
    get_pokemon_id_from_name

BOT_PREFIX = "!"
BOT_TOKEN = None
MOD_ROLE_ID = None
IMAGE_URL = ""
EX_RAID_CHANNEL = None
GMAPS_KEY = None

bot = commands.Bot(command_prefix=BOT_PREFIX, case_insensitive=True,
                   description='A bot that manages Pokemon Go Discord communities.')

running_updater = False

reaction_list = ["mystic", "valor", "instinct", "1⃣", "2⃣", "3⃣", "❌"]

@bot.event
@asyncio.coroutine
async def on_ready():
    global running_updater
    print(discord.version_info)
    print('Logged in as: {}'.format(bot.user.name))
    print('Bot ID: {}'.format(bot.user.id))
    print("Mod Role ID: {}".format(MOD_ROLE_ID))
    print("Image URL: {}".format(IMAGE_URL))
    print("Ex-Raid Channel: {}".format(EX_RAID_CHANNEL))
    print("GMaps Key: {}...".format(GMAPS_KEY[:10]))
    print('------')

    # if EX_RAID_CHANNEL:
    #     exchan = bot.get_channel(int(EX_RAID_CHANNEL))
    #     if exchan:
    #         running_updater = True
    #         await exchan.send("Scanning ex-raid channel for updates",
    #                           delete_after=30.0)
    #         await exupdaterloop(exchan, 5)


@bot.event
# Payload( PartialEmoji, Message_id, Channel_id, User_id)
async def on_raw_reaction_add(*payload):

    if len(payload) == 4:
        emoji = payload[0]
        mid = payload[1]
        channel = bot.get_channel(payload[2])
        user = channel.guild.get_member(payload[3]) if channel \
            else bot.get_user(payload[3])

        if not channel or (emoji and emoji.name not in reaction_list):
            return
        try:
            message = await channel.get_message(mid)
            if message:
                await on_reaction_add(message, emoji, user)
        except discord.NotFound:
            print("Message {} not found".format(mid))


@bot.event
# Payload( PartialEmoji, Message_id, Channel_id, User_id)
async def on_raw_reaction_remove(*payload):
    if len(payload) == 4:
        emoji = payload[0]
        mid = payload[1]
        channel = bot.get_channel(payload[2])
        user = channel.guild.get_member(payload[3]) if channel \
            else bot.get_user(payload[3])

        if emoji and emoji.name not in reaction_list:
            return

        if not channel:
            return
        try:
            message = await channel.get_message(mid)
            if message:
                await on_reaction_remove(message, emoji, user)
        except:
            print("Message id {} not found".format(mid))


async def on_reaction_add(message, emoji, user):
    def confirm(m):
        if m.author == user and m.content.lower().startswith("y"):
            return True
        return False

    channel = message.channel
    if user == bot.user or message.author != bot.user or \
            not message.embeds:
        return
    loc = getfieldbyname(message.embeds[0].fields, "Location")
    loc = loc.value if loc else "Unknown"
    if emoji.name == "❌":
        if check_role(user, MOD_ROLE_ID) or \
                        message.embeds[0].author == user.name:
            ask = await channel.send("Are you sure you would like to "
                                     "delete raid *{}*? (yes/no)".format(loc))
            try:
                msg = await bot.wait_for("message", timeout=30.0, check=confirm)
            except asyncio.TimeoutError:
                await message.remove_reaction(emoji, user)
                await ask.delete()
            else:
                print("Raid {} deleted by user {}".format(loc, user.name))
                await channel.send("Raid *{}* deleted by {}"
                                   .format(loc, user.name), delete_after=20.0)
                await message.delete()
                await ask.delete()
                await msg.delete()
        return
    if message.embeds and check_footer(message, "raid"):
        print("notifying raid {}: {}".format(loc, user.name))
        await notify_raid(message)
        if isinstance(emoji, str):
            await message.channel.send(
                "{} is bringing +{} to raid {}".format(
                    user.name, emoji, loc))
        return

    if message.embeds and check_footer(message, "ex-"):
        print("notifying exraid {}: {}".format(loc, user.name))
        await notify_exraid(message)
        if isinstance(emoji, str):
            await message.channel.send(
                "{} is bringing +{} to ex-raid *{}*".format(
                    user.name, emoji, loc))
        return


async def on_reaction_remove(message, emoji, user):
    if user == bot.user and not message.embeds:
        return
    loc = getfieldbyname(message.embeds[0].fields, "Location")
    if loc:
        loc = loc.value
    else:
        loc = "Unknown"
    if emoji.name == "❌":
        return
    if check_footer(message, "raid"):
        print("Notifying raid: User {} has left {}".format(user.name, loc))
        await notify_raid(message)
    if check_footer(message, "ex-"):
        role_name = message.embeds[0].footer.text
        if role_name and role_name != "ex-raid" and \
                not isinstance(emoji, str):
            for role in user.roles:
                if role.name == role_name:
                    await user.remove_roles(role)
                    await message.channel.send(
                        "{} you have left *{}*".format(user.mention, role_name),
                        delete_after=10)
        print("Notifying Ex-raid: User {} has left {}".format(user.name, loc))
        await notify_exraid(message)
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
                    value="No Invite. This bot must be self-hosted")
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
             brief="[MOD] Purge messages from channel. !purge [pinned]",
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
    try:
        async for msg in channel.history(limit=500):
            if msg.author != bot.user:
                continue
            if msg.embeds and msg.embeds[0].footer and \
                    msg.embeds[0].footer.text.startswith("ex-"):
                await notify_exraid(msg)
    except:
        pass


@bot.command(aliases=[],
             brief="[MOD] Clear raid posts from channel. !clearraids",
             pass_context=True)
async def clearraids(ctx):
    def raid(msg):
        return msg.author == bot.user and check_footer(msg, "raid")

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
async def raid(ctx, pkmn, *, locationtime):
    if not await checkmod(ctx):
        return

    lt = locationtime.split()
    location = (" ".join(lt[:-1])).strip()
    timer = lt[-1].strip()

    async for msg in ctx.message.channel.history():
        if msg.author == bot.user and msg.embeds:
            loc = getfieldbyname(msg.embeds[0].fields, "Location")
            if loc and location.lower() == loc.value.lower() and pkmn.lower() in \
                    msg.embeds[0].title.lower():
                if (datetime.utcnow() - msg.created_at) < \
                        datetime.timedelta(minutes=30):
                    await ctx.send("Raid at {} already exists,please use "
                                   "previous post".format(loc.value),
                                   delete_after=10.0)
                    await ctx.message.delete()
                    return

    thumb = None
    descrip = ""
    pkmn = string.capwords(pkmn, "-")
    pid = get_pokemon_id_from_name(pkmn)
    if pid:
        if IMAGE_URL:
            thumb = IMAGE_URL.format(pid)

        mincp20, maxcp20 = get_cp_range(pid, 20)
        mincp25, maxcp25 = get_cp_range(pid, 25)

        descrip = "CP: ({}-{})\nWB: ({}-{})".format(mincp20, maxcp20,
                                                    mincp25, maxcp25)
    coords = get_gym_coords(location)

    embed = discord.Embed(title="Raid - {}".format(pkmn),
                          description=descrip)
    embed.set_author(name=ctx.message.author.name)
    if thumb:
        embed.set_thumbnail(url=thumb)
    if coords and GMAPS_KEY:
        map_image = get_static_map_url(coords[0], coords[1], api_key=GMAPS_KEY)
        embed.set_image(url=map_image)
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
    await asyncio.sleep(7200)
    await msg.unpin()


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
                if ctx.message.author.name != msg.embeds[
                    0].author.name and not check_role(ctx.message.author,
                                                     MOD_ROLE_ID):
                    await ctx.send("You cannot edit this raid post. "
                                   "Only the original poster can.",
                                   delete_after=20.0)
                    await ctx.message.delete()
                    return
                for i in range(0, len(msg.embeds[0].fields)):
                    field2 = msg.embeds[0].fields[i]
                    if field2.name.startswith("Time") or \
                            field2.name.startswith("Date"):
                        if timer:
                            if ctx.message.author.name != msg.embeds[
                                0].author.name and not check_role(
                                    ctx.message.author, MOD_ROLE_ID):
                                await ctx.send("You cannot edit this raid post."
                                               " Only the original poster can.",
                                               delete_after=20.0)
                                await ctx.message.delete()
                                return
                            msg.embeds[0].set_field_at(i, name=field2.name,
                                                       value=timer,
                                                       inline=True)
                            await msg.edit(embed=msg.embeds[0])
                            await ctx.send(
                                "Updated Raid at *{}* to time: **{}**"
                                .format(field.value, timer))
                            await ctx.message.delete()
                            return
                        else:
                            total = getfieldbyname(msg.embeds[0].fields,
                                                   "Total")
                            total = total.value if total else 0
                            await ctx.send(
                                "Raid at **{}** at time: **{}** has  **{} **  "
                                "people registered."
                                .format(field.value, field2.value, total))
                            await ctx.message.delete()
                            return
    await ctx.message.delete()
    await ctx.send("Unable to find Raid at {}".format(loc), delete_after=30)


@bot.command(aliases=["rp"],
             usage="!raidpokemon [location] [pokemon]",
             brief="Edit the pokemon on a previous raid post. "
                   "!raidpokemon <location> <pokemon>",
             pass_context=True)
async def raidpokemon(ctx, loc, pkmn):
    if not await checkmod(ctx):
        return

    async for msg in ctx.message.channel.history():
        if msg.author != bot.user or not msg.embeds:
            continue
        for field in msg.embeds[0].fields:
            if field.name.startswith("Location") and \
                            loc.lower() in field.value.lower():
                if ctx.message.author.name != msg.embeds[
                    0].author.name and not check_role(ctx.message.author,
                                                     MOD_ROLE_ID):
                    await ctx.send("You cannot edit this raid post. "
                                   "Only the original poster can.",
                                   delete_after=20.0)
                    await ctx.message.delete()
                    return
                descrip = msg.embeds[0].description
                pkmn = string.capwords(pkmn, "-")
                pid = get_pokemon_id_from_name(pkmn)
                if pid:
                    if IMAGE_URL:
                        thumb = IMAGE_URL.format(pid)
                        msg.embeds[0].set_thumbnail(url=thumb)
                    mincp20, maxcp20 = get_cp_range(pid, 20)
                    mincp25, maxcp25 = get_cp_range(pid, 25)

                    descrip = "CP: ({}-{})\nWB: ({}-{})".format(mincp20,
                                                                maxcp20,
                                                                mincp25,
                                                                maxcp25)
                if check_footer(msg, "raid"):
                    msg.embeds[0].title = "Raid - {}".format(pkmn)
                elif check_footer(msg, "ex-"):
                    msg.embeds[0].title = "Ex-Raid - {}".format(pkmn)
                msg.embeds[0].description = descrip
                await msg.edit(embed=msg.embeds[0])
                await ctx.send("Raid at **{}** updated to **{}**"
                               .format(field.value, pkmn))
                await ctx.message.delete()
                return
    await ctx.message.delete()
    await ctx.send("Unable to find Raid at {}".format(loc), delete_after=30)


@bot.command(aliases=["rm"],
             usage="!raidmessage [location] [msg]",
             brief="Message members in raid "
                   "!raidmessage <location> <msg>",
             pass_context=True)
async def raidmessage(ctx, loc, *, message):
    if not await checkmod(ctx):
        return

    async for msg in ctx.message.channel.history():
        if msg.author != bot.user or not msg.embeds:
            continue
        for field in msg.embeds[0].fields:
            if field.name.startswith("Location") and \
                            loc.lower() in field.value.lower():
                registered = []
                for reaction in msg.reactions:
                    async for user in reaction.users():
                        if user == bot.user:
                            continue
                        if user.mention not in registered:
                            registered.append(user)
                auth = ctx.message.author
                if auth not in registered and not check_role(auth, MOD_ROLE_ID) \
                        and msg.embeds[0].author.name != auth.name:
                    await ctx.send("You are not involved with this raid.",
                                   delete_after=10.0)
                    await ctx.msg.delete()
                    return
                await ctx.send("".join(map(lambda u: u.mention, registered)) +
                               " " + message)
                await ctx.message.delete()
                return
        await ctx.send("Cannot find raid *{}*".format(loc), delete_after=10.0)
        await ctx.message.delete()


@bot.command(aliases=["rc"],
             usage="!raidcoords [location] [latitude] [longitude]",
             brief="Set raid coordinates to display map"
                   "!raidcoords <location> <latitude> <longitude>",
             pass_context=True)
async def raidcoords(ctx, loc, *, coords):
    if not await checkmod(ctx):
        return

    coords = coords.replace(",", " ").replace("  ", " ").split(" ")
    if len(coords) > 2 or len(coords) < 2:
        await ctx.send("Unable to process coordinates.", delete_after=10.0)
        await ctx.message.delete()
        return
    async for msg in ctx.message.channel.history():
        if msg.author != bot.user or not msg.embeds:
            continue
        for field in msg.embeds[0].fields:
            if field.name.startswith("Location") and \
                            loc.lower() in field.value.lower():
                if msg.embeds[0].author.name != ctx.message.author.name and \
                        not check_role(ctx.message.author, MOD_ROLE_ID):
                    await ctx.send("You cannot set coordinates for this raid!",
                                   delete_after=10.0)
                    await ctx.message.delete()
                    return
                if check_footer(msg, "raid"):
                    await notify_raid(msg, coords)
                    await ctx.send("Raid {} updated to coords: ({},{})"
                                   .format(field.value, coords[0], coords[1]),
                                   delete_after=10.0)
                    await ctx.message.delete()
                    return
                elif check_footer(msg, "ex-"):
                    await notify_exraid(msg, coords)
                    await ctx.send("Ex-Raid {} updated to coords: ({},{})"
                                   .format(field.value, coords[0], coords[1]),
                                   delete_after=10.0)
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

    pkmn_case = string.capwords(pkmn, '-')
    pid = get_pokemon_id_from_name(pkmn)
    if pid:
        if IMAGE_URL:
            thumb = IMAGE_URL.format(pid)

        mincp20, maxcp20 = get_cp_range(pid, 20)
        mincp25, maxcp25 = get_cp_range(pid, 25)

        descrip = "CP: ({}-{})\nWB: ({}-{})".format(mincp20, maxcp20,
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


async def notify_raid(msg, coords=None):
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

    if GMAPS_KEY and coords:
        map_image = get_static_map_url(coords[0], coords[1], api_key=GMAPS_KEY)
        embed.set_image(url=map_image)

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


async def notify_exraid(msg, coords=None):
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

    embed = msg.embeds[0]

    if GMAPS_KEY and coords and len(coords) == 2:
        map_image = get_static_map_url(coords[0], coords[1], api_key=GMAPS_KEY)
        embed.set_image(url=map_image)

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
    bot.command_prefix = cfg['PoGoBot']['BotPrefix'] or "!"
    MOD_ROLE_ID = cfg['PoGoBot'].get('ModRoleID') or -1
    IMAGE_URL = cfg['PoGoBot'].get('ImageURL') or None
    EX_RAID_CHANNEL = cfg['PoGoBot'].get('ExRaidChannel') or 0
    GMAPS_KEY = cfg['PoGoBot'].get('GMapsKey') or None
    load_locale(os.path.join('locales', '{}.json'
                             .format(cfg['PoGoBot']['Locale'] or 'en')))
    load_base_stats(os.path.join('data', 'base_stats.json'))
    load_cp_multipliers(os.path.join('data', 'cp_multipliers.json'))

    if os.path.exists('gyms.json'):
        load_gyms('gyms.json')

    bot.run(cfg['PoGoBot']['BotToken'])
