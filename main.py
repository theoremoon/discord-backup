import discord
import re
import os
import requests
import sys
import git
from pathlib import Path

client = discord.Client()

repository = sys.argv[1]
token = sys.argv[2]

def avoid_filename_collision(orig_p: Path):
    cnt = 2
    p = orig_p
    while p.exists():
        p = orig_p.with_name(orig_p.stem + "_{}_".format(cnt) + orig_p.suffix)
        cnt += 1
    return p


async def save_channel_messages(repo, prefix, ch):
    ch_dir = Path(repo) / prefix / ch.name
    attachment_dir = ch_dir / "attachments"
    os.makedirs(ch_dir, exist_ok=True)
    os.makedirs(attachment_dir, exist_ok=True)

    msgs = await ch.history(limit=None).flatten()

    text = ""
    for msg in msgs[::-1]:
        if msg.type != discord.MessageType.default:
            continue
        text += "**[{}]**\n{}\n".format(msg.author.name,
                                        re.sub(r"(.)```", "\1\n```", msg.content))

        for a in msg.attachments:
            r = requests.get(a.url)
            try:
                r.raise_for_status()
                attachment_path = avoid_filename_collision(attachment_dir / a.filename)
                with open(attachment_path, "wb") as f:
                    f.write(r.content)
                text += "![attachments/{}](attachments/{})\n".format(attachment_path.name, attachment_path.name)
            except Exception as e:
                print("[-] failed to save attachment: {}".format(e))
        text += "\n"

    with open(os.path.join(ch_dir, ch.name + ".md"), "w") as f:
        f.write(text)


async def backup_category(message, category, repository):
    for ch in category.text_channels:
        await save_channel_messages(repository, category.name, ch)
        await message.channel.send("[+] backup channel: {}".format(ch.name))

    try:
        repo = git.Repo(repository)
        repo.git.add(".")
        repo.index.commit("backup category: {}".format(category.name))
        repo.git.push("origin", "master")
        await message.channel.send("[+] backup category: {}".format(category.name))

    except Exception as e:
        await message.channel.send("[-] git error: {}".format(e))


async def remove_category(message, category):
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


@client.event
async def on_message(message):
    if message.author == client.user:
        return

    if message.content.startswith("!ping"):
        await message.channel.send("pong")
        return

    if message.content.startswith("!backup "):
        category = message.content[len("!backup "):].lower()
        categories = {c.name.lower(): c for c in message.guild.categories}
        if category not in categories:
            await message.channel.send("no such category: {}".format(category))
            return

        category = categories[category]
        await backup_category(message, category, repository)

    if message.content.startswith("!remove "):
        category = message.content[len("!remove "):].lower()
        categories = {c.name.lower(): c for c in message.guild.categories}
        if category not in categories:
            await message.channel.send("no such category: {}".format(category))
            return

        category = categories[category]
        await remove_category(message, category)

    if message.content.startswith("!archive "):
        category_name = message.content[len("!archive "):].lower()
        categories = {c.name.lower(): c for c in message.guild.categories}
        if category_name not in categories:
            await message.channel.send("no such category: {}".format(category_name))
            return

        category = categories[category_name]
        await backup_category(message, category, repository)
        await remove_category(message, category)

        category_name = category_name + "-solved"
        if category_name not in categories:
            await message.channel.send("no such category: {}".format(category_name))
            return

        category = categories[category_name]
        await backup_category(message, category, repository)
        await remove_category(message, category)


client.run(token)
