import asyncio
import json

base_stats = {}
locale = {}
cp_multipliers = {}
boss_tiers = {}
gyms = {}

def check_role(member, rolex):
    for role in member.roles:
        if (str(role.id) == rolex) or (
                    str(role.name.lower()) == str(rolex.lower())):
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
    global gyms
    with open(fp) as f:
        gyms = json.load(f)


def get_pokemon_id_from_name(pkmn):
    return locale['pokemon'].get(pkmn)


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


def get_gym_coords(gn):
    for d in gyms:
        if gn in d.get("name", '').lower():
            return [d.get("latitude"), d.get("longitude")]

    return None
