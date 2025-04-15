import discord
from dotenv import load_dotenv
import os
import requests
import asyncio

load_dotenv()

server_name = os.getenv('SERVER')
intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

# global state to track players
online_players_old = set()

def get_server_status():
    res = requests.get(f'https://api.mcsrvstat.us/3/{server_name}')
    success = res.status_code == 200
    return res.json(), success

def get_online_players():
    res, succ = get_server_status()
    if succ:
        data = res
        players = data.get("players", {}).get("list", [])
        return ([player["name"] for player in players], True)
    else:
        return ([], False)

@client.event
async def on_ready():
    print(f'✅ Logged in as {client.user}')
    # Start background task
    client.loop.create_task(check_new_players())

@client.event
async def on_message(message):
    if message.author == client.user:
        return

    if message.content.startswith('$players'):
        players = get_online_players()[0]
        succ = get_online_players()[1]
        if (not succ):
            await message.channel.send('❌ Error fetching mcsrvstat api.')
            return
        if players:
            await message.channel.send(f'Online players on MC server are: {", ".join(players)}')
        else:
            await message.channel.send('😢 No players online.')

# Background task to run every 5 minutes
async def check_new_players():
    await client.wait_until_ready()
    global online_players_old
    
    channel_id = int(os.getenv("ANNOUNCE_CHANNEL_ID"))  # Make sure to set this in your .env
    channel = client.get_channel(channel_id)
    
    if channel is None:
        print("❌ Error: Channel not found. Check ANNOUNCE_CHANNEL_ID.")
        return

    while not client.is_closed():
        result = get_online_players()
        current_players = set(result[0])
        succ = result[1]
        if succ:
            # Detect new players
            new_players = current_players - online_players_old
            if new_players:
                for name in new_players:
                    await channel.send(f'🎮 **{name}** just joined the minecraft server!')
    
            online_players_old = current_players
        await asyncio.sleep(60)  # wait 5 minutes

client.run(os.getenv('TOKEN'))
