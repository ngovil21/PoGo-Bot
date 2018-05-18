import asyncio


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
