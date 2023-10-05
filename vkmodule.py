import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Self

from dotenv import load_dotenv
from pydantic import BaseModel
from vkbottle import API, BotPolling


class wallPost(BaseModel):
    author_id: int
    text: str | None = None
    photo_urls: list[str] | None = None
    url: str
    timestamp: int


class groupVKBase(BaseModel):
    id: int
    post_subscribers: list[int]


class groupVK(groupVKBase):
    post_subscribers: list[int] | None = None
    name: str
    photo_100: str


class VK:
    def __init__(self: Self, token: str):
        self.token = token
        self.api = API(self.token)
        self.seen_path = Path(".") / "seen_vk_posts.json"
        self.seen_posts: dict[str, list[int]] = self.load_seen_vk_posts()

    def load_seen_vk_posts(self: Self) -> dict[str, list[int]]:
        if not self.seen_path.is_file():
            with self.seen_path.open("w") as file:
                return {}

        with self.seen_path.open("r", encoding="utf-8") as file:
            return json.load(file)

        # with self.seen_path.open("r", encoding="utf-8") as file:
        #     lines = file.readlines()
        # lines = [line.strip() for line in lines]
        # lines.sort()
        # del lines[-100::-1]

        # return lines

    async def write_seen_vk_posts(self: Self) -> None:
        with self.seen_path.open("w", encoding="utf-8") as file:
            json.dump(self.seen_posts, file, ensure_ascii=False, indent=4)

    async def get_raw_messages(self: Self, target_id: int = -199045714, count: int = 4) -> dict:
        try:
            response = (await self.api.wall.get(target_id, count=count)).dict()
            # with open("test.json", "w", encoding="utf-8") as file:
            #     json.dump(response, file, indent=4, ensure_ascii=False, default=lambda x: x.value)
        except Exception as e:
            raise e

        return response

    async def get_author_data(self: Self, target_id: int) -> groupVK:
        try:
            return groupVK(**(await self.api.groups.get_by_id(group_id=target_id, fields=["name", "photo_100"]))[0].dict(exclude_none=True))
        except Exception:
            raise

    async def poller(self, target_id: int = 199045714):
        return BotPolling(self.api, target_id, 25).listen()

    async def check_for_updates(self: Self, target_id: int, count: int = 4) -> list[wallPost]:
        # print("str(target_id) not in self.seen_posts", str(target_id) not in self.seen_posts)
        if str(target_id) not in self.seen_posts:
            self.seen_posts[str(target_id)] = []

        try:
            posts = (await self.get_raw_messages(target_id, count))["items"]
        except Exception:
            raise

        return_list: list[wallPost] = []
        for post in posts:
            # helper = {}
            helper = wallPost(author_id=1, url="", timestamp=0)
            # helper = {"author_id": int, "text": "", "photo_urls": [], "timestamp": int, "url": str}
            # print("post['id'] in self.seen_posts[str(target_id)]", post["id"] in self.seen_posts[str(target_id)])
            if post["id"] in self.seen_posts[str(target_id)]:
                continue

            self.seen_posts[str(target_id)].append(post["id"])

            if post["text"]:
                helper.text = post["text"]
            if post["attachments"]:
                helper.photo_urls = []
                for att in post["attachments"]:
                    if att["photo"]:
                        helper.photo_urls.append(att["photo"]["sizes"][-1]["url"])
                        # break  # если нужно взять только первую попавшуюся картинку
                    if att["video"]:
                        helper.photo_urls.append(att["video"]["image"][-1]["url"])
                        # break  # если нужно взять только первую попавшуюся картинку
            helper.author_id = abs(post["from_id"])
            helper.timestamp = post["date"]
            helper.url = f"https://vk.com/wall{post['from_id']}_{post['id']}"  # https://vk.com/wall-199045714_204811

            return_list.append(helper)

        # print(repr(return_list))

        await self.write_seen_vk_posts()

        return return_list

    async def check_if_exists(self, public_id: int) -> bool:
        try:
            await self.get_raw_messages(-abs(public_id), 1)
            return True
        except Exception:
            return False


async def le_main() -> None:
    load_dotenv()
    token = os.environ.get("VK_TOKEN")
    if not token:
        sys.exit(1)

    # vk = VK(token)

    # response = (await vk.api.groups.get_by_id(group_id=199045714, fields=["name", "photo_100"]))[0].dict(exclude_none=True)
    # with open("test.json", "w", encoding="utf-8") as file:
    #     json.dump(response, file, indent=4, ensure_ascii=False, default=lambda x: x.value)

    # await vk.get_raw_messages(target_id=-202125781)
    # # print(json.dumps(await vk.check_for_updates(-199045714, 4), indent=4, ensure_ascii=False))
    # print(await vk.check_if_exists(-555773757))


if __name__ == "__main__":
    import logging

    logging.getLogger("vkbottle").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)

    asyncio.run(le_main())
