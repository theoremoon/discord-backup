import discord
import re
import os
import requests
import sys
import git

client = discord.Client()

repository = sys.argv[1]
token = sys.argv[2]

async def save_channel_messages(repo,prefix, ch):
    dir = os.path.join(repo, prefix, ch.name)
    attachment_dir = os.path.join(dir,"attachments")
    os.makedirs(dir,exist_ok=True)
    os.makedirs(attachment_dir,exist_ok=True)

    msgs = await ch.history(limit=None).flatten()

    text = ""
    for msg in msgs[::-1]:
        if msg.type != discord.MessageType.default:
            continue
        text += "**[{}]**\n{}\n".format(msg.author.name, re.sub(r"(.)```", "\1\n```", msg.content))

        for a in msg.attachments:
            r = requests.get(a.url)
            try:
                r.raise_for_status()
                with open(os.path.join(attachment_dir,a.filename), "wb") as f:
                    f.write(r.content)
                text += "![](attachments/{})\n".format(a.filename)
            except Exception:
                pass
        text += "\n"

    with open(os.path.join(dir, ch.name + ".md"),"w") as f:
        f.write(text)


@client.event
async def on_message(message):
    if message.author == client.user:
        return

    if message.content.startswith("!ping"):
        await message.channel.send("pong")
        return

    if message.content.startswith("!backup "):
        category = message.content[len("!backup "):].lower()
        categories = {c.name.lower():c for c in message.guild.categories}
        if category not in categories:
            await message.channel.send("no such category: {}".format(category))
            return

        category = categories[category]
        for ch in category.text_channels:
            await save_channel_messages(repository, category.name, ch)
            await message.channel.send("[+] backup channel: {}".format(ch.name))

        repo = git.Repo(repository)
        repo.git.add(".")
        repo.index.commit("backup category: {}".format(category.name))
        repo.git.push("origin","master")

        await message.channel.send("[+] backup category: {}".format(category.name))

    if message.content.startswith("!remove "):
        category = message.content[len("!remove "):].lower()
        categories = {c.name.lower():c for c in message.guild.categories}
        if category not in categories:
            await message.channel.send("no such category: {}".format(category))
            return

        category = categories[category]
        for ch in category.text_channels:
            try:
                await ch.delete()
                await message.channel.send("[+] remove channel: {}".format(ch.name))
            except Exception:
                await message.channel.send("[-] failed to remove channel: {}".format(ch.name))

        try:
            await category.delete()
            await message.channel.send("[+] remove category: {}".format(category.name))
        except Exception:
            await message.channel.send("[-] failed to remove category: {}".format(category.name))




client.run(token)


