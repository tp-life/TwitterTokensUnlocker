import json
from typing import List

from attr import dataclass

@dataclass
class Config:
    threads: int
    capsolver_key: str
    allowed_captcha_solvers: List[str]


with open("config.json", "r", encoding="utf-8") as config_file:
    config = json.load(config_file)
    config = Config(**config)
