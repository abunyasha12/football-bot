import asyncio
import json
import logging
import logging.handlers
import sys
from pathlib import Path
from typing import Self

import discord
from discord.ext import commands
from starlette.config import Config
from starlette.datastructures import Secret

from vkmodule import VK

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
channels_to_post = []
tracked_publics = []


async def football_poster() -> None:
    if not VK_TOKEN:
        log.critical("No VK_TOKEN, exiting...")
        sys.exit(1)

    vk = VK(str(VK_TOKEN))
    channels = [bot.get_channel(i) for i in channels_to_post]

    while True:
        posts = []
        try:
            for pub in tracked_publics:
                posts += await vk.check_for_updates(-pub)
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

            for post in posts:
                urls = "\n".join(post["photo_urls"])
                await channel.send(f"{post['text']}")
                await channel.send(urls)
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
