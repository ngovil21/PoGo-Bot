import asyncio
import json
import re
from fuzzywuzzy import fuzz, process

base_stats = {}
locale = {}
cp_multipliers = {}
boss_tiers = {}
gyms = {}
gym_names = []


def check_roles(member, roles):
    if not isinstance(roles, list):
        roles = [roles]
    for role in member.roles:
        for r in roles:
            if str(role.id) == str(r) or role.name.lower() == str(r).lower():
                return True
    return False


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


def getfieldbyname(fields, name):
    for field in fields:
        if name.lower() in field.name.lower():
            return field
    return None


def check_footer(msg, val):
    if msg.embeds:
        for embed in msg.embeds:
            if embed.footer and embed.footer.text.startswith(val):
                return True
    return False


# Returns a static map url with <lat> and <lng> parameters for dynamic test
# Taken and modified from PokeAlarm
def get_static_map_url(lat, lng, width='250', height='125',
                       maptype='roadmap', zoom='15', api_key=None):
    center = '{},{}'.format(lat, lng)
    query_center = 'center={}'.format(center)
    query_markers = 'markers=color:red%7C{}'.format(center)
    query_size = 'size={}x{}'.format(width, height)
    query_zoom = 'zoom={}'.format(zoom)
    query_maptype = 'maptype={}'.format(maptype)

    map_ = ('https://maps.googleapis.com/maps/api/staticmap?' +
            query_center + '&' + query_markers + '&' +
            query_maptype + '&' + query_size + '&' + query_zoom)

    if api_key is not None:
        map_ += ('&key=%s' % api_key)
    return map_


def load_base_stats(fp):
    global base_stats
    with open(fp) as f:
        base_stats = json.load(f)


def load_cp_multipliers(fp):
    global cp_multipliers
    with open(fp) as f:
        cp_multipliers = json.load(f)


def load_locale(fp):
    global locale
    with open(fp) as f:
        locale = json.load(f)


def load_gyms(fp):
    global gyms, gym_names
    with open(fp) as f:
        gyms = json.load(f)
    gym_names = []
    for d in gyms:
        if 'name' in d:
            gym_names.append(d['name'])


def get_pokemon_id_from_name(pkmn):
    return locale['pokemon'].get(pkmn)


def pokemon_match(pkmn):
    result = process.extractOne(pkmn, locale['pokemon'].keys(),
                                scorer=fuzz.ratio, score_cutoff=75)
    if result:
        return result[0]
    return None


def get_cp_range(pid, level):
    stats = base_stats["{0:03d}".format(pid)]
    cpm = cp_multipliers['{}'.format(level)]

    min_cp = int(((stats['attack'] + 10.0) *
                  pow((stats['defense'] + 10.0), 0.5) *
                  pow((stats['stamina'] + 10.0), 0.5) *
                  pow(cpm, 2)) / 10.0)

    max_cp = int(((stats['attack'] + 15.0) *
                  pow((stats['defense'] + 15.0), 0.5) *
                  pow((stats['stamina'] + 15.0), 0.5) *
                  pow(cpm, 2)) / 10.0)

    return min_cp, max_cp


def get_types(pid):
    stats = base_stats["{0:03d}".format(pid)]
    type1 = locale["types"]["{0:03d}".format(stats.get("type1"))]
    if "type2" in stats:
        type2 = locale["types"]["{0:03d}".format(stats.get("type2"))]
    else:
        type2 = None
    return type1, type2


def get_gym_coords(gn):
    results = process.extractBests(gn, gym_names, scorer=fuzz.partial_ratio,
                                   score_cutoff=70)
    if not results:
        return None
    if len(results) > 1:
        results = process.extractBests(gn, gym_names, scorer=fuzz.ratio,
                                       limit=2, score_cutoff=60)
        if not results:
            return None
        if len(results) > 1:
            if abs(results[0][1] - results[1][1]) < 7:
                printr("Too many similar results for {}".format(gn))
                return None
    name, match = results[0]
    printr("{} matched {} with score {}".format(gn, name, match))
    for d in gyms:
        if name == d.get("name"):
            return [d.get("latitude"), d.get("longitude")]

    return None


# Replace non-ascii characters with '?' and print
def printr(s):
    print(re.sub(r'[^\x00-\x7F]', '?', str(s)))
