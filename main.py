import discord
from dotenv import load_dotenv
import os
import requests
import asyncio
from flask import Flask
import threading
from pymongo import MongoClient

user_preferences = []

#initialize env
load_dotenv()

#initialize flask
app = Flask("McAtlasBot")

#initialize mongoDB
mongodb_uri = os.getenv('MONGO_CONNECTION_STRING')
client = MongoClient(mongodb_uri)
db = client[os.getenv('DATABASE_NAME')]
user_collection = db[os.getenv('USER_PREFERENCES_COLLECTION_NAME')]

server_name = os.getenv('SERVER')
intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

# global state to track players
online_players_old = set()

def get_server_status():
    try:
        res = requests.get(f'https://api.mcsrvstat.us/3/{server_name}')
    except requests.exceptions.RequestException as e:
        print(f"Error fetching server status: {e}")
    finally:
        if not res:
            return {}, False
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
async def on_message(message : discord.Message):
    if message.author == client.user:
        return

    if message.content.startswith('$players'):
        res, succ = get_online_players()
        players = set(res) - set(get_silent_players())
        if (not succ):
            await message.channel.send('❌ Error fetching mcsrvstat api.')
            return
        if players:
            await message.channel.send(f'Online non hidden players on MC server are: {", ".join(players)}')
        else:
            await message.channel.send('😢 No players online.')

    elif message.content.startswith("$hide"):
        user = None

        try:
            user = user_collection.find_one({"user": message.author.name})
        except Exception as e:
            print(f"Database find error: {e}")

        if user:
            try:
                user_collection.update_one(
                    {"user": message.author.name},
                    {"$set": {"silent_join": True}}
                )
                await message.channel.send(f"{message.author.name} is now hidden 😶‍🌫️")
                update_user_preferences(message.author.name, silent=True)
            except Exception as e:
                await message.channel.send("❌ Error updating user in database.")
                print(f"Database update error: {e}")
                return
        else:
            #result = user_collection.insert_one({
            #    "user": f"{message.author.name}",
            #    "silent_join": True,
            #    "nick": "unknown_nickname"
            #})
            #user = user_collection.find_one({"user": message.author.name})
            await message.channel.send(f"{message.author.name} não está cadastrado... Informe ao ademir!")
            print("User not registered")

    elif message.content.startswith("$unhide"):
        user = None

        try:
            user = user_collection.find_one({"user": message.author.name})
        except Exception as e:
            print(f"Database find error: {e}")

        if user:
            try:
                user_collection.update_one(
                    {"user": message.author.name},
                    {"$set": {"silent_join": False}}
                )
                await message.channel.send(f"{message.author.name} is not hidden anymore 😱")
                update_user_preferences(message.author.name, silent=False)
            except Exception as e:
                await message.channel.send("❌ Error updating user in database.")
                print(f"Database update error: {e}")
                return
        else:
            #result = user_collection.insert_one({
            #    "user": f"{message.author.name}",
            #    "silent_join": False,
            #    "nick": "unknown_nickname"
            #})
            #user = user_collection.find_one({"user": message.author.name})
            await message.channel.send(f"{message.author.name} não está cadastrado... Informe ao ademir!")
            print("User not registered")

    elif message.content.startswith("$help"):
        await message.channel.send("**Commands:**\n"
                                   "$players - shows non hidden online players\n"
                                   "$hide - hide your join messages\n"
                                   "$unhide - unhide your join messages\n"
                                   "$help - show this help message")


# Background task to run every 1 minute
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
                for name in new_players - set(get_silent_players()):
                    await channel.send(f'🎮 **{name}** just joined the minecraft server!')
    
            online_players_old = current_players
        await asyncio.sleep(60)  # wait 1 minutes

@app.route('/')
def hello():
    return "Hello from McAtlasBot!"

def run_flask():
    app.run(host='0.0.0.0', port=5000) 

def run_bot():
    client.run(os.getenv('TOKEN'))

def update_user_preferences(user: str, silent: bool):
    for user_preference in user_preferences:
        if user == user_preference["user"]:
            user_preference["silent_join"] = silent
            break
def get_silent_players():
    playerlist = []
    for user in user_preferences:
        if user["silent_join"] == True:
            playerlist.append(user["nick"])
    return playerlist

def load_preferences():
    # get everyone from the database and set the default preference
    try:
        users = user_collection.find()
        for user in users:
            user_preferences.append({"user": user['user'], "silent_join": user["silent_join"], "nick": user["nick"]})
    except Exception as e:
        print(f"Database error: {e}")

    print(user_preferences)

if __name__ == "__main__":
    
    load_preferences()
    threading.Thread(target=run_flask).start()
    
    # Start the Discord bot
    run_bot()