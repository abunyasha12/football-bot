import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Self

from dotenv import load_dotenv
from vkbottle import API, BotPolling


class VK:
    def __init__(self: Self, token: str):
        self.token = token
        self.api = API(self.token)
        self.path = Path(".") / "seen_vk_posts.txt"
        self.seen_posts = self.load_seen_vk_posts()

    def load_seen_vk_posts(self: Self) -> list[str]:
        if not self.path.is_file():
            with self.path.open("w") as file:
                return []

        with self.path.open("r", encoding="utf-8") as file:
            lines = file.readlines()
        lines = [line.strip() for line in lines]
        lines.sort()
        del lines[-20::-1]

        return lines

    async def write_seen_vk_posts(self: Self, lines: list[str]) -> list[str]:
        lines.sort()
        with self.path.open("w", encoding="utf-8") as file:
            file.writelines([line + "\n" if "\n" not in line else line for line in lines])

        return lines

    async def get_raw_messages(self: Self, target_id: int = -199045714, count: int = 4) -> dict:
        try:
            response = (await self.api.wall.get(target_id, count=count)).dict()
        except Exception as e:
            raise e

        return response

    async def poller(self: Self, target_id: int = 199045714):
        return BotPolling(self.api, target_id, 25).listen()

    async def check_for_updates(self: Self, target_id: int, count: int = 4) -> list[dict]:
        try:
            posts = (await self.get_raw_messages(target_id, count))["items"]
        except Exception:
            raise

        return_list = []
        for post in posts:
            # helper = {}
            helper = {"text": "", "photo_urls": []}
            if f"{post['from_id']}_{post['id']}" in self.seen_posts:
                continue

            self.seen_posts.append(f"{post['from_id']}_{post['id']}")

            if post["text"]:
                helper["text"] = post["text"]
            if post["attachments"]:
                for att in post["attachments"]:
                    if att["photo"]:
                        helper["photo_urls"].append(att["photo"]["sizes"][-1]["url"])
                    if att["video"]:
                        helper["photo_urls"].append(att["video"]["image"][-1]["url"])
            return_list.append(helper)

        await self.write_seen_vk_posts(self.seen_posts)
        return return_list


async def le_main() -> None:
    load_dotenv()
    token = os.environ.get("VK_TOKEN")
    if not token:
        sys.exit(1)

    vk = VK(token)

    print(json.dumps(await vk.check_for_updates(-199045714, 4), indent=4, ensure_ascii=False))


if __name__ == "__main__":
    import logging

    logging.getLogger("vkbottle").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)

    asyncio.run(le_main())
