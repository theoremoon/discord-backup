import discord
import re
import os
import requests
import sys
import git
from pathlib import Path
from typing import List

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


async def backup_category(category, repository) -> List[str]:
    messages = []

    for ch in category.text_channels:
        try:
            messages += await save_channel_messages(repository, category.name, ch)
            messages.append("[+] backup channel: {}".format(ch.name))
        except Exception as e:
            messages.append("[-] channel backup error: (channel: {}, error: {})".format(ch.name, e))

    try:
        repo = git.Repo(repository)
        repo.git.add(".")
        repo.index.commit("backup category: {}".format(category.name))
        repo.git.push("origin", "master")
        messages.append("[+] category backup: {}".format(category.name))
    except Exception as e:
        messages.append("[-] category backup error: (channel: {}, error: {})".format(category.name, e))

    return messages


async def remove_category(category)->List[str]:
    messages = []

    for ch in category.text_channels:
        try:
            await ch.delete()
            messages.append("[+] remove channel: {}".format(ch.name))
        except Exception as e:
            messages.append("[-] channel remove error: (category: {}, error: {})".format(ch.name, e))

    try:
        await category.delete()
        messages.append("[+] remove category: {}".format(category.name))
    except Exception as e:
        messages.append("[-] category remove error: (category: {}, error: {})".format(category.name, e))

    return messages


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
        messages = await backup_category(message, category, repository)
        embed = discord.Embed(title=message.content, description="\n".join(messages))
        await message.channel.send(embed)

    if message.content.startswith("!remove "):
        category = message.content[len("!remove "):].lower()
        categories = {c.name.lower(): c for c in message.guild.categories}
        if category not in categories:
            await message.channel.send("no such category: {}".format(category))
            return

        category = categories[category]
        messages = await remove_category(message, category)
        embed = discord.Embed(title=message.content, description="\n".join(messages))
        await message.channel.send(embed)

    if message.content.startswith("!archive "):
        category_prefix = message.content[len("!archive "):].lower()
        categories = {c.name.lower(): c for c in message.guild.categories}

        for postfix in ["", "-solved", "-unsolved"]:
            category_name = category_prefix + postfix
            if category_name not in categories:
                embed = discord.Embed(title=message.content, description="no such category: {}".format(category_name))
                await message.channel.send(embed)
                continue

            category = categories[category_name]

            messages = await backup_category(message, category, repository)
            embed = discord.Embed(title="backup {}".format(category_name), description="\n".join(messages))
            await message.channel.send(embed)

            messages = await remove_category(message, category, repository)
            embed = discord.Embed(title="remove {}".format(category_name), description="\n".join(messages))
            await message.channel.send(embed)


client.run(token)
