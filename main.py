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
from pydantic import BaseModel, parse_obj_as
from pydantic.json import pydantic_encoder
from starlette.config import Config
from starlette.datastructures import Secret

from vkmodule import VK, groupVK, groupVKBase, wallPost

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
poster_config = Path(".") / "config.json"

DISCORD_TOKEN = config("DISCORD_TOKEN", cast=Secret, default="")
VK_TOKEN = config("VK_TOKEN", cast=Secret, default="")


class Bot(commands.Bot):
    """Базовый класс бота"""

    def __init__(self: Self) -> None:
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(command_prefix="!", intents=intents)


bot = Bot()
# error_announcement_channels: list[int] = []
# tracked_publics: list[groupVKBase] = []


class leConfig(BaseModel):
    error_announcement_channels: list[int] = []
    tracked_publics: list[groupVKBase] = []


class groupData(BaseModel):
    id: int
    author: groupVK
    posts: list[wallPost]
    post_subscribers: list[int]


le_config = leConfig()


async def football_poster() -> None:
    if not VK_TOKEN:
        log.critical("No VK_TOKEN, exiting...")
        sys.exit(1)

    groups_datas: list[groupData] = []
    refresh_counter = 0

    async def refresh_groups() -> list[groupData]:
        retlist = []
        for group in le_config.tracked_publics:
            retlist.append(
                groupData(
                    id=group.id,
                    author=await vk.get_author_data(abs(group.id)),
                    posts=await vk.check_for_updates(group.id),
                    post_subscribers=group.post_subscribers,
                )
            )
            await asyncio.sleep(0.3)
        return retlist

    while True:
        if len(groups_datas) != len(le_config.tracked_publics):
            groups_datas = await refresh_groups()

        if refresh_counter > 59:
            refresh_counter = 0
            groups_datas = await refresh_groups()

        try:
            for group in groups_datas:
                group.posts = await vk.check_for_updates(group.id)

        except Exception as e:
            for channel in le_config.error_announcement_channels:
                if not isinstance(channel, discord.TextChannel):
                    continue
                await channel.send(f"Oops... {e}")
                log.error(f"Oops... {e}")

                await asyncio.sleep(60)
                continue

        for group in groups_datas:
            if not group.posts:
                continue

            channels = [await bot.fetch_channel(i) for i in group.post_subscribers]

            for post in group.posts:
                embed = (
                    discord.Embed(
                        title=(post.text.splitlines()[0][:250] if post.text else None),
                        url=post.url,
                        color=discord.Color.from_str("#00a8fc"),
                        description=("\n".join(post.text.splitlines()[1:]) if post.text else None),
                        timestamp=datetime.fromtimestamp(post.timestamp),
                    )
                    .set_image(url=post.photo_urls[0] if post.photo_urls else None)
                    .set_thumbnail(url=group.author.photo_100)
                    .set_author(name=group.author.name, url=f"https://vk.com/public{group.author.id}")
                )

                for channel in channels:
                    if not isinstance(channel, discord.TextChannel):
                        continue
                    await channel.send(embed=embed)
                    await asyncio.sleep(0.3)

        # for channel in channels:
        #     if not isinstance(channel, discord.TextChannel):
        #         continue

        #     for cpost in posts_list:
        #         if not cpost.posts:
        #             continue

        #         for post in cpost.posts:
        #             embed = (
        #                 discord.Embed(
        #                     title=(post.text.splitlines()[0][:250] if post.text else None),
        #                     url=post.url,
        #                     color=discord.Color.from_str("#00a8fc"),
        #                     description=("\n".join(post.text.splitlines()[1:]) if post.text else None),
        #                     timestamp=datetime.fromtimestamp(post.timestamp),
        #                 )
        #                 .set_image(url=post.photo_urls[0] if post.photo_urls else None)
        #                 .set_thumbnail(url=cpost.author.photo_100)
        #                 .set_author(name=cpost.author.name, url=f"https://vk.com/public{cpost.author.id}")
        #             )
        #             await channel.send(embed=embed)

        #             # urls = "\n".join(post["photo_urls"])
        #             # await channel.send(f"{post['text']}")
        #             # await channel.send(urls)
        #             await asyncio.sleep(2)
        refresh_counter += 1
        await asyncio.sleep(60)


def load_settings() -> None:
    global le_config
    if poster_config.is_file():
        with poster_config.open("r", encoding="utf-8") as file:
            le_config = parse_obj_as(leConfig, json.load(file))

    else:
        with poster_config.open("w", encoding="utf-8") as file:
            j = {
                "tracked_publics": [],
                "error_announcement_channels": [1093947782546608148],
            }
            json.dump(j, file, ensure_ascii=False, indent=4)


def save_settings():
    with poster_config.open("w", encoding="utf-8") as f:
        json.dump(le_config, f, ensure_ascii=False, indent=4, default=pydantic_encoder)


@bot.event
async def on_ready() -> None:
    """Вызывается когда бот готов к работе"""

    log.info(f"Logged in as {bot.user}")

    asyncio.get_event_loop().create_task(football_poster())


@bot.tree.command()
# @app_commands.describe(image="Image", factor="Upscale factor 1x-4x", upscaler="Upscaler")
# @app_commands.guilds(*guilds_ids)
# @app_commands.checks.cooldown(1, 60, key=lambda i: (i.guild_id, i.user.id))
async def add_to_track(ctx: discord.Interaction, public_id: int):
    if not ctx.channel:
        return

    await ctx.response.defer(ephemeral=True)

    log.info(f"[ {ctx.user.id} : {ctx.user.display_name} ] requested to add [ {public_id} ] to tracking")

    if not await vk.check_if_exists(public_id):
        await ctx.followup.send(f"Public [ {public_id} ] not found")
        return

    for group in le_config.tracked_publics:
        if (-abs(public_id)) == group.id:
            if ctx.channel.id in group.post_subscribers:
                await ctx.followup.send(f"[ {public_id} ] is already tracking")
                return
            group.post_subscribers.append(ctx.channel.id)

            await ctx.followup.send(f"Added [ {public_id} ] to tracking")

            if ctx.channel.id not in le_config.error_announcement_channels:
                le_config.error_announcement_channels.append(ctx.channel.id)

            save_settings()
            return

    le_config.tracked_publics.append(groupVKBase(id=(-abs(public_id)), post_subscribers=[ctx.channel.id]))
    if ctx.channel.id not in le_config.error_announcement_channels:
        le_config.error_announcement_channels.append(ctx.channel.id)

    save_settings()
    log.info(f"Added [ {public_id} ] to tracking")
    await ctx.followup.send(f"Added [ {public_id} ] to tracking")


@bot.command(hidden=True)
async def synchronise(ctx: commands.Context, glbl: str | None = None) -> None:
    """
    sync commands
    """
    log.info(f"sync requested in {ctx.guild}")
    await ctx.defer()
    if glbl == "CLEAR":
        comms = await bot.tree.sync(guild=ctx.guild)
        await ctx.author.send(f"SYNCED {len(comms)} COMMANDS")
    elif glbl:
        comms = await bot.tree.sync()
        await ctx.author.send(f"SYNCED GLOBAL {len(comms)} COMMANDS")
    else:
        bot.tree.copy_global_to(guild=ctx.guild)  # type: ignore
        comms = await bot.tree.sync(guild=ctx.guild)
        await ctx.author.send(f"SYNCED {len(comms)} COMMANDS")


if __name__ == "__main__":
    if DISCORD_TOKEN is None:
        log.critical("No DISCORD_TOKEN, exiting...")
        sys.exit(1)

    load_settings()
    vk = VK(str(VK_TOKEN))

    bot.run(str(DISCORD_TOKEN))
