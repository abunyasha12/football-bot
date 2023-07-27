import asyncio
import json
import logging
import logging.handlers
import sys
from datetime import datetime
from pathlib import Path
from typing import Self

import discord
from discord.ext import commands
from pydantic import BaseModel
from starlette.config import Config
from starlette.datastructures import Secret

from vkmodule import VK, groupVK, wallPost

logging.getLogger("vkbottle").setLevel(logging.WARNING)
logging.getLogger("discord.gateway").setLevel(logging.WARNING)
logging.getLogger("asyncio").setLevel(logging.WARNING)

log = logging.getLogger(__name__)
log.setLevel(logging.INFO)
log.propagate = False


fhandler = logging.handlers.TimedRotatingFileHandler("./logs/logfile.log", "D", backupCount=30, encoding="utf-8")
dt_fmt = "%Y-%m-%d %H:%M:%S"
fmt = logging.Formatter(
    "[%(asctime)s][%(levelname)s][%(name)s][%(funcName)s:%(lineno)d] %(message)s",
    dt_fmt,
)
fhandler.setFormatter(fmt)
log.addHandler(fhandler)

chandler = logging.StreamHandler(sys.stdout)
chandler.setLevel(logging.INFO)
chandler.setFormatter(fmt)
log.addHandler(chandler)

config = Config(".env")

DISCORD_TOKEN = config("DISCORD_TOKEN", cast=Secret, default="")
VK_TOKEN = config("VK_TOKEN", cast=Secret, default="")


class Bot(commands.Bot):
    """Базовый класс бота"""

    def __init__(self: Self) -> None:
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(command_prefix="!", intents=intents)


bot = Bot()
channels_to_post: list[int] = []
tracked_publics: list[int] = []


class completePost(BaseModel):
    author: groupVK
    posts: list[wallPost]


async def football_poster() -> None:
    if not VK_TOKEN:
        log.critical("No VK_TOKEN, exiting...")
        sys.exit(1)

    vk = VK(str(VK_TOKEN))
    channels = [bot.get_channel(i) for i in channels_to_post]

    while True:
        posts_list: list[completePost] = []
        try:
            for pub_id in tracked_publics:
                posts_list.append(completePost(author=await vk.get_author_data(pub_id), posts=await vk.check_for_updates(-pub_id)))

        except Exception as e:
            for channel in channels:
                if not isinstance(channel, discord.TextChannel):
                    continue
                await channel.send(f"Oops... {e}")
                log.error(f"Oops... {e}")
            sys.exit(2)

        for channel in channels:
            if not isinstance(channel, discord.TextChannel):
                continue

            for cpost in posts_list:
                if not cpost.posts:
                    continue

                for post in cpost.posts:
                    embed = (
                        discord.Embed(
                            title=(post.text.splitlines()[0][:250] if post.text else None),
                            url=post.url,
                            color=discord.Color.from_str("#00a8fc"),
                            description=("\n".join(post.text.splitlines()[1:]) if post.text else None),
                            timestamp=datetime.fromtimestamp(post.timestamp),
                        )
                        .set_image(url=post.photo_urls[0] if post.photo_urls else None)
                        .set_thumbnail(url=cpost.author.photo_100)
                        .set_author(name=cpost.author.name, url=f"https://vk.com/public{cpost.author.id}")
                    )
                    await channel.send(embed=embed)

                    # urls = "\n".join(post["photo_urls"])
                    # await channel.send(f"{post['text']}")
                    # await channel.send(urls)
                    await asyncio.sleep(2)

        await asyncio.sleep(60)


def load_settings() -> None:
    global channels_to_post
    global tracked_publics
    path = Path(".") / "config.json"
    if path.is_file():
        with path.open("r", encoding="utf-8") as file:
            setts = json.load(file)
            channels_to_post = setts["channels_to_post"]
            tracked_publics = setts["tracked_publics"]
    else:
        with path.open("w", encoding="utf-8") as file:
            j = {
                "channels_to_post": [],
                "tracked_publics": [],
            }
            json.dump(j, file, ensure_ascii=False, indent=4)


@bot.event
async def on_ready() -> None:
    """Вызывается когда бот готов к работе"""

    log.info(f"Logged in as {bot.user}")

    asyncio.get_event_loop().create_task(football_poster())


if __name__ == "__main__":
    if DISCORD_TOKEN is None:
        log.critical("No DISCORD_TOKEN, exiting...")
        sys.exit(1)

    load_settings()

    bot.run(str(DISCORD_TOKEN))
