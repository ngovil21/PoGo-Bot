import discord
import asyncio

client = discord.Client()

@client.event
@asyncio.coroutine
def on_ready():
    print('Logged in as')
    print(client.user.name)
    print(client.user.id)
    print('------')

@client.event
@asyncio.coroutine
def on_message(message):
    if message.content.startswith('!test'):
        counter = 0
        tmp = yield from client.send_message(message.channel, 'Calculating messages...')
        for log in client.logs_from(message.channel, limit=100):
            if log.author == message.author:
                counter += 1

        yield from client.edit_message(tmp, 'You have {} messages.'.format(counter))
    elif message.content.startswith('!sleep'):
        yield from asyncio.sleep(5)
        yield from client.send_message(message.channel, 'Done sleeping')

client.run('token')