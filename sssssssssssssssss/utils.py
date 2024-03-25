import threading
from math import inf
from typing import Dict, List, Optional, Tuple
import logging
from colorlog import ColoredFormatter
import requests
from datetime import datetime
from attr import dataclass


@dataclass
class Tweet:
    id: str
    author: str
    following: bool
    can_dm: bool
    text: str
    date: int
    media: Optional[List[str]] = []


logger = logging.getLogger(__name__)

colored_formatter = ColoredFormatter(
    "%(log_color)s%(asctime)s - %(levelname)s - %(message)s",
    log_colors={
        "DEBUG": "cyan",
        "INFO": "green",
        "WARNING": "yellow",
        "ERROR": "red",
        "CRITICAL": "bold_red",
    },
)

file_handler = logging.FileHandler("errors.log")
file_handler.setLevel(logging.CRITICAL)
file_handler.setFormatter(
    logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
)
logger.addHandler(file_handler)

console_handler = logging.StreamHandler()
console_handler.setFormatter(colored_formatter)
logger.addHandler(console_handler)
logger.setLevel(logging.DEBUG)


def chunkify(old_list: List, amount: int) -> List[List]:
    """Split a list into chunks.

    Args:
        old_list (List): List to split.
        amount (int): Amount of chunks.

    Returns:
        List[List]: A list of chunks.
    """
    chunk_size = len(old_list) // amount
    remainder = len(old_list) % amount
    start = 0
    chunks = []
    for _ in range(amount):
        end = start + chunk_size + (1 if _ < remainder else 0)
        chunks.append(old_list[start:end])
        start = end
    return chunks


def fetch_latest_chrome_version() -> str:
    """Fetches the latest chrome version.

    Returns:
        str: The chrome version.
    """
    response = requests.get(
        "https://versionhistory.googleapis.com/v1/chrome/platforms/win64/channels/stable/versions",
        timeout=30,
    )
    if response and response.status_code == 200:
        return response.json()["versions"][0]["version"]
    return "120"


def extract_info(response: Dict) -> Optional[Tuple[str]]:
    """Extracts the user information from the response.

    Args:
        response (Dict): The sssssssssssssssss API response.

    Returns:
        Optional[Tuple[str]]: A tuple containing the user name and the user id.
    """
    try:
        user = response["content"]["itemContent"]["tweet_results"]["result"]["core"][
            "user_results"
        ]["result"]
        return user["legacy"]["screen_name"], user["rest_id"]
    except KeyError:
        return None


def date_to_epoch(date: str) -> int:
    date_ = datetime.strptime(date, "%a %b %d %H:%M:%S %z %Y")
    epoch_time = int(date_.timestamp())
    return epoch_time


def parse_tweets(entries_, only_tweets: Optional[bool] = None) -> List[Tweet]:
    if only_tweets is None or only_tweets is True:
        entries = [entry for entry in entries_ if entry["entryId"].startswith("tweet")]
    else:
        entries = entries_
    tweets = []
    for tweet in entries:
        result = tweet.get("content")
        if result:
            result = result["itemContent"]["tweet_results"]["result"]
        else:
            result = tweet["item"]["itemContent"]["tweet_results"]["result"]
        legacy = (
            result["tweet"]["core"]["user_results"]["result"]["legacy"]
            if "tweet" in result
            else result["core"]["user_results"]["result"]["legacy"]
        )
        tweet_data = (
            result["legacy"] if "legacy" in result else result["tweet"]["legacy"]
        )
        media = []
        if "entities" in tweet_data:
            if "media" in tweet_data["entities"]:
                for m in tweet_data["entities"]["media"]:
                    media.append(m["media_url_https"])
        if "rest_id" not in result:
            continue
        tweets.append(
            Tweet(
                result["rest_id"],
                legacy["screen_name"],
                legacy.get("following", False),
                legacy.get("can_dm", False),
                tweet_data["full_text"].split(" https://t.co/")[0],
                date_to_epoch(tweet_data["created_at"]),
                media,
            )
        )
    return tweets


def parse_profile_tweets(entries_) -> List[Tweet]:
    entries__ = [
        entry for entry in entries_ if not entry["entryId"].startswith("cursor")
    ]
    entries = []
    for entry in entries__:
        if "content" in entry and "items" in entry["content"]:
            for subentry in entry["content"]["items"]:
                entries.append(subentry)
    entries.extend(entries__)
    return parse_tweets(entries, True)


def chunkify(old_list: List[str], amount: int) -> List[List[str]]:
    chunk_size = len(old_list) // amount
    remainder = len(old_list) % amount
    start = 0
    chunks = []
    for _ in range(amount):
        end = start + chunk_size + (1 if _ < remainder else 0)
        chunks.append(old_list[start:end])
        start = end
    return chunks


class Counter:
    def __init__(self, limit):
        if isinstance(limit, str):
            if limit.lower() in ["inf", "infinity", "infinite"]:
                limit = inf
            else:
                limit = int(limit)
        self.value = 0
        self.limit = limit
        self.people = {}
        self.lock = threading.Lock()

    def increment(self) -> int:
        with self.lock:
            self.value += 1
            return self.value

    def increment_person(self, person: str) -> int:
        if person not in self.people:
            with self.lock:
                self.people[person] = 1
                return self.people[person]
        with self.lock:
            self.people[person] += 1
        return self.people[person]
