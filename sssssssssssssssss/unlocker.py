import random
import traceback
from typing import List, Optional
import threading
import re

import dotenv

from .utils import fetch_latest_chrome_version, chunkify
from .client import TwitterSession

dotenv.load_dotenv()

with open("proxies.txt", "r", encoding="utf-8") as file:
    proxies = file.read().splitlines()
chrome_version = fetch_latest_chrome_version()

twitter_client = TwitterSession(proxies, chrome_version)

authenticity_token_re = re.compile(r'authenticity_token" value="(\w*)')
assignment_token_re = re.compile(r'assignment_token" value="(-?\w*)')

def unlock_token(token: str, solvers) -> Optional[str]:
    try:
        session = twitter_client.init_basic_session(token)
        authenticity_token_res = session.get(
            "https://twitter.com/account/access", follow_redirects=True
        )

        if authenticity_token_res.status_code == 302:
            return token

        if (
            authenticity_token_res.url
            == "https://twitter.com/login?redirect_after_login=%2Faccount%2Faccess"
        ):
            return None
        authenticity_token = authenticity_token_re.findall(authenticity_token_res.text)[
            0
        ]
        assignment_token = assignment_token_re.findall(authenticity_token_res.text)[0]

        params = {
            "lang": "en",
            "authenticity_token": authenticity_token,
            "assignment_token": assignment_token,
            "flow": "",
            "ui_metrics": "",
            "language_code": "en",
        }
        res = session.post(
            "https://twitter.com/account/access", params=params, follow_redirects=True
        )

        authenticity_token_res = session.get(
            "https://twitter.com/account/access", follow_redirects=True
        )

        if authenticity_token_res.url in [
            "https://twitter.com/?lang=en",
            "https://twitter.com/login?redirect_after_login=%2Faccount%2Faccess",
        ]:
            return None
        check = authenticity_token_res.text
        authenticity_token_res = authenticity_token_res.text
        while "Thank you for addressing this issue." not in check:
            try:
                if "Something went wrong." in authenticity_token_res:
                    authenticity_token_res = session.get(
                        "https://twitter.com/account/access", follow_redirects=True
                    ).text
                authenticity_token = authenticity_token_re.findall(
                    authenticity_token_res
                )[0]
                assignment_token = assignment_token_re.findall(authenticity_token_res)[
                    0
                ]

                while True:
                    solver = random.choice(solvers)
                    captcha = solver.solve_captcha()
                    if captcha:
                        break
                twitter_client.logger.info(f"Solved captcha: [{captcha[:32]}...] - Solver used: {solver.name}")
                res = session.post(
                    "https://twitter.com/account/access",
                    params={
                        **params,
                        "authenticity_token": authenticity_token,
                        "assignment_token": assignment_token,
                        "verification_string": captcha,
                    },
                )

                check = res.text
                authenticity_token_res = res.text
            except IndexError:
                print(authenticity_token_res)
                exit(1)
            except:
                print(traceback.format_exc())

        authenticity_token_res = session.get("https://twitter.com/account/access").text
        authenticity_token = authenticity_token_re.findall(authenticity_token_res)[0]
        assignment_token = assignment_token_re.findall(authenticity_token_res)[0]

        res = session.post(
            "https://twitter.com/account/access",
            params={
                **params,
                "authenticity_token": authenticity_token,
                "assignment_token": assignment_token,
            },
            follow_redirects=True,
        )

        if res.url == "https://twitter.com/?lang=en":
            return token

    except IndexError:
        if 'change your password' in authenticity_token_res.text:
            twitter_client.logger.warn(f'Token {token} is password locked and cannot be unlocked')
        return None


def unlock_tokens(tokens: List[str], threads_amount: int, solvers) -> List[str]:
    unlocked_tokens = []
    threads = []

    def unlock_tokens_chunk(chunk, solvers):
        for token in chunk:
            unlocked = unlock_token(token, solvers)
            if unlocked:
                twitter_client.logger.info(f"Successfully Unlocked token [{unlocked}]")
                unlocked_tokens.append(unlocked)

    token_chunks = chunkify(tokens, threads_amount)

    for chunk in token_chunks:
        thread = threading.Thread(target=unlock_tokens_chunk, args=(chunk, solvers,))
        thread.start()
        threads.append(thread)

    for thread in threads:
        thread.join()
    return unlocked_tokens

