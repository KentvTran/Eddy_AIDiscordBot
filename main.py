import random
import discord
import openai
import json
import requests
import asyncio
import os
from discord import FFmpegPCMAudio
from discord.ext import commands
from dotenv import load_dotenv
from datetime import datetime, timedelta

# Replace 'YOUR_TOKEN_HERE' with the actual token you copied from the Discord Developer Portal
load_dotenv()
TOKEN = os.environ.get("DISCORD_TOKEN")
JOKEAPI = os.environ.get("JOKEAPI")
API_URL = 'https://canvas.instructure.com'
canvas_base_url = 'https://csufullerton.instructure.com'
CANVAS = os.environ.get("CANVAS_TOKEN")
CHAT = os.environ.get("CHATGPT_TOKEN")
openai.api_key = CHAT
# This enables features for bot, rn message and member-related events
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

# Create an instance of the bot with intents
# Prefix calls bot like {!help}
client = commands.Bot(command_prefix='!', intents=intents)

reminders = {}

# client.event are for bot features
# Event handler for when the bot is ready
# On ready = receive commands
@client.event
async def on_ready():
    print(f'{client.user.name} has connected to Discord!')
    print("------------------------------------")

# event when members join
@client.event
async def on_member_join(member):
    channel = client.get_channel(1206700172520853528)
    await channel.send(f"Greetings {member.mention}! Welcome to the server.")

# event when members leave
@client.event
async def on_member_remove(member):
    channel = client.get_channel(1206700172520853528)
    await channel.send(f"Have a good day {member.mention}!")

# Joke command
@client.command(name='joke')
async def joke(ctx):
    await ctx.send(f"Here's a joke for you:\n")

    url = "https://jokeapi-v2.p.rapidapi.com/joke/Any"

    headers = {
        "X-RapidAPI-Key": JOKEAPI,
        "X-RapidAPI-Host": "jokeapi-v2.p.rapidapi.com"
    }

    try:
        response = requests.get(url, headers=headers)
        joke_data = response.json()

        # Print the entire JSON response
        print(joke_data)

        # Check the type of the joke
        joke_type = joke_data.get('type', 'single')

        if joke_type == 'twopart':
            setup = joke_data.get('setup', 'No setup found')
            delivery = joke_data.get('delivery', 'No delivery found')
            await ctx.send(f"**Setup:** {setup}\n**Delivery:** {delivery}")
        elif joke_type == 'single':
            joke = joke_data.get('joke', 'No joke found')
            await ctx.send(f"**Joke:** {joke}")
        else:
            await ctx.send("Unknown joke type")

    except Exception as e:
        # Handle errors
        await ctx.send(f"Error getting a joke: {e}")

# Goodbye command
@client.command()
async def goodbye(ctx):
    await ctx.send("Goodbye, hope you have a good rest of your day!")

# Event handler for when a message is received
@client.event
async def on_message(message):
    # Ignore messages from the bot itself to prevent infinite loops
    if message.author == client.user:
        return

    # Respond to a specific command
    if message.content.lower().startswith('!hello'):
        # List of possible responses
        responses = ['Wassup my g!', 'Hello there!', 'Howdy!', 'Hey!']

        # Select a random response from the list
        response = random.choice(responses)

        # Send the random response
        await message.channel.send(response)

    # Process commands
    await client.process_commands(message)

@client.command(name='Eddy')
async def ask_gpt(ctx, *, question):
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "user", "content": question}
        ]
    )
    answer = response['choices'][0]['message']['content']
    await ctx.send(answer)

@client.command(name='music')
async def music(ctx):
    if ctx.author.voice:
        channel = ctx.author.voice.channel
        if ctx.voice_client:  # Check if the bot is already in a voice channel
            await ctx.voice_client.move_to(channel)
        else:
            voice = await channel.connect()

        source = FFmpegPCMAudio("Lofi.mp3")
        ctx.voice_client.play(source, after=lambda e: print('Player error: %s' % e) if e else None)
    else:
        await ctx.send("Please be in a voice channel to use this command!")


#canvas announcement function
# Command to list courses
@client.command(name='list_course_ids')
async def list_course_ids(ctx):
    global CANVAS, canvas_base_url
    if not CANVAS:
        await ctx.send("Canvas access token is missing.")
        return

    # Construct the Canvas API URL to fetch all courses
    canvas_api_url = f"{canvas_base_url}/api/v1/courses"

    headers = {
        'Authorization': f'Bearer {CANVAS}'
    }

    try:
        # Make a request to fetch all courses
        response = requests.get(canvas_api_url, headers=headers)
        response.raise_for_status()  # Raise an error for non-2xx status codes

        courses_data = response.json()

        # Check if the response contains an array of course objects
        if isinstance(courses_data, list) and len(courses_data) > 0:
            # Extract course IDs from the courses data
            course_ids = [course['id'] for course in courses_data]

            # Format the list of course IDs
            course_ids_list = "\n".join(str(course_id) for course_id in course_ids)
            await ctx.send(f"All Course IDs:\n{course_ids_list}")
        else:
            await ctx.send("No courses found.")

    except requests.exceptions.HTTPError as e:
        await ctx.send(f"HTTP error occurred: {e.response.status_code} - {e.response.reason}")
    except Exception as e:
        await ctx.send(f"Error fetching course IDs: {e}")


# Command to create a reminder for an assignment
@client.command(name='create_reminder')
async def create_reminder(ctx):
    await ctx.send("Let's create a reminder!")

    # Prompt user for assignment details
    await ctx.send("What is the name of the assignment?")
    assignment_name = await client.wait_for('message', check=lambda msg: msg.author == ctx.author)

    await ctx.send("When is the assignment due? (Please provide date and time, e.g., YYYY-MM-DD HH:MM)")
    due_datetime_str = await client.wait_for('message', check=lambda msg: msg.author == ctx.author)

    try:
        due_datetime = datetime.strptime(due_datetime_str.content, '%Y-%m-%d %H:%M')
    except ValueError:
        await ctx.send("Invalid datetime format. Please use YYYY-MM-DD HH:MM.")
        return

    await ctx.send("When do you want to receive reminders? (e.g., 1 hour before, 1 day before)")
    reminder_timing = await client.wait_for('message', check=lambda msg: msg.author == ctx.author)

    # Parse reminder timing
    seconds_before_due = parse_reminder_timing(reminder_timing.content)

    if seconds_before_due is None:
        await ctx.send("Invalid reminder timing format. Please use 'X hours before' or 'X days before'.")
        return

    # Calculate reminder datetime
    reminder_datetime = due_datetime - timedelta(seconds=seconds_before_due)

    # Store the reminder for the user
    if ctx.author.id not in reminders:
        reminders[ctx.author.id] = []

    reminders[ctx.author.id].append({
        'assignment_name': assignment_name.content,
        'due_datetime': due_datetime_str.content,
        'reminder_timing': reminder_timing.content,
        'reminder_datetime': reminder_datetime
    })

    # Schedule the reminder to be sent
    await asyncio.sleep((reminder_datetime - datetime.now()).total_seconds())
    await ctx.author.send(f"Reminder: Assignment '{assignment_name.content}' is due on {due_datetime_str.content}")

    await ctx.send("Reminder created successfully!")


# Command to list all reminders for the user
@client.command(name='list_reminders')
async def list_reminders(ctx):
    if ctx.author.id in reminders and reminders[ctx.author.id]:
        await ctx.send("Your current reminders:")
        for i, reminder in enumerate(reminders[ctx.author.id], start=1):
            await ctx.send(
                f"{i}. {reminder['assignment_name']} (Due: {reminder['due_datetime']}, Reminder: {reminder['reminder_timing']})")
    else:
        await ctx.send("You have no reminders.")


# Command to remove a specific reminder
@client.command(name='remove_reminder')
async def remove_reminder(ctx, index: int):
    if ctx.author.id in reminders and reminders[ctx.author.id]:
        if 1 <= index <= len(reminders[ctx.author.id]):
            removed_reminder = reminders[ctx.author.id].pop(index - 1)
            await ctx.send(
                f"Removed reminder: {removed_reminder['assignment_name']} (Due: {removed_reminder['due_datetime']}, Reminder: {removed_reminder['reminder_timing']})")
        else:
            await ctx.send("Invalid reminder index. Please specify a valid reminder index.")
    else:
        await ctx.send("You have no reminders.")


def parse_reminder_timing(reminder_timing):
    # Parse the reminder timing to extract the number of seconds before the due date
    try:
        parts = reminder_timing.split()
        value = int(parts[0])
        unit = parts[1].lower()

        if unit.endswith('s'):
            unit = unit[:-1]  # Remove 's' from unit (e.g., hours -> hour)

        if unit == 'hour':
            return value * 3600
        elif unit == 'day':
            return value * 86400
        elif unit == 'minute':
            return value * 60
        elif unit == 'second':
            return value
        else:
            return None
    except (ValueError, IndexError):
        return None

@client.command(name='leave')
async def leave(ctx):
    if (ctx.voice_client):
        await ctx.guild.voice_client.disconnect()
        await ctx.send("No more music D:")
    else:
        await ctx.send("I am not in a voice channel")

@client.command(name='pause')
async def pause(ctx):
    voice = discord.utils.get(client.voice_clients,guild=ctx.guild)
    if voice.is_playing():
        voice.pause()
    else:
        await ctx.send("No audio playing right now..")


@client.command(name='resume')
async def resume(ctx):
    voice = discord.utils.get(client.voice_clients, guild=ctx.guild)
    if voice.is_paused():
        voice.resume()
    else:
        await ctx.send("No song paused right now..")

# Start the bot
client.run(TOKEN)