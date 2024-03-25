"""
A wrapper for the Twitter API.
"""
from typing import Any, List, Dict, Optional, Tuple, Union
from uuid import uuid4
import random
from os import path, mkdir, remove as osremove
import subprocess
from functools import wraps
import math
import time

import httpx
from requests import post as rpost, get as rget, head as rhead
from tqdm import tqdm

from . import utils

# OopCompanion:suppressRename


def cleanup(func):
    @wraps(func)
    def wrapper(self, session: httpx.Client, file: str) -> Optional[str]:
        try:
            is_video_from_http = file.startswith("http") and file.lower().endswith(
                ".mp4"
            )

            if is_video_from_http:
                self.download(file, "videos")

            result = func(self, session, file)

            if is_video_from_http:
                osremove(f"videos/{file.split('/')[-1]}")

            return result
        except Exception:
            return None

    return wrapper


class TwitterSession:
    """
    A wrapper for the Twitter API.
    """

    def __init__(
        self,
        proxies: Optional[List] = None,
        chrome_version: Optional[str] = "120",
    ) -> None:
        self.chrome_version = chrome_version
        self.sessions = {}
        self.logger = utils.logger
        self.proxies = proxies

    def init_session(self, token: str) -> httpx.Client:
        """Initiates a twitter instance.

        Args:
            token (str): The token of the account.

        Returns:
            httpx.Client: The session with login cookies.
        """
        context = httpx.create_ssl_context()
        cipher1 = 'ECDH+AESGCM:ECDH+CHACHA20:DH+AESGCM:DH+CHACHA20:ECDH+AES256:DH+AES256:ECDH+AES128:DH+AES:ECDH+HIGH:DH+HIGH:RSA+AESGCM:RSA+AES:RSA+HIGH'
        context.set_alpn_protocols(['h2'])
        context.set_ciphers(cipher1)
        if token in self.sessions:
            self.logger.debug(f'Resuming session with token {token}')
            return self.sessions[token]
        ct0 = None
        if ":" in token:
            ct0, token = token.split(":")
        proxies = None
        if self.proxies:
            proxy = random.choice(self.proxies)
            proxies = {"all://": f"http://{proxy}"}
        session = httpx.Client(
            http2=True, verify=context, timeout=30, proxies=proxies
        )
        session.cookies["auth_token"] = token
        if ct0:
            session.cookies["ct0"] = ct0
            self._get_cookies(session, False)
            session.headers["x-csrf-token"] = ct0
        else:
            self._get_cookies(session, True)
        self.sessions[token] = session
        self.logger.debug(f"Initialized session with token {token}")
        return session

    def _get_cookies(self, session: httpx.Client, do_request: Optional[bool] = True) -> None:
        try:
            session.headers = {
                "authority": "twitter.com",
                "accept": "*/*",
                "accept-language": "en-US,en;q=0.7",
                "authorization": "Bearer AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs%3D1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA",
                "content-type": "application/json",
                "referer": "https://twitter.com/",
                "sec-ch-ua": f'"Not/A)Brand";v="99", "Brave";v="{self.chrome_version}", "Chromium";v="{self.chrome_version}"',
                "sec-ch-ua-mobile": "?0",
                "sec-ch-ua-platform": '"Windows"',
                "sec-fetch-dest": "empty",
                "sec-fetch-mode": "cors",
                "sec-fetch-site": "same-origin",
                "sec-gpc": "1",
                "user-agent": f"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{self.chrome_version}.0.0.0 Safari/537.36",
                "x-client-uuid": str(uuid4()),
                "x-twitter-active-user": "yes",
                "x-twitter-auth-type": "OAuth2Session",
                "x-twitter-client-language": "en",
            }
            if do_request:
                session.post(
                    "https://twitter.com/i/api/1.1/account/update_profile.json",
                )
                session.headers["x-csrf-token"] = session.cookies.get("ct0")
        except TimeoutError:
            print("proxy timed out")
            return

    def get_own_info(
        self, session: httpx.Client
    ) -> Optional[Tuple[str, Optional[str]]]:
        """Gets the username and id of a given session.

        Args:
            session (httpx.Client): The sssssssssssssssss session.

        Returns:
            Optional[Tuple[str]]: A Tuple containing the username and id if found.
        """
        response = session.get("https://api.twitter.com/1.1/account/settings.json")
        if response.status_code == 200:
            jsn = response.json()
            username = jsn.get("screen_name", "")
            our_id = self.username_to_id(session, username)
            return username, our_id
        return None

    def username_to_id(
        self, session: httpx.Client, username: str
    ) -> Optional[str]:
        """Converts a given username to its id.

        Args:
            session (httpx.Client): he sssssssssssssssss session.
            username (str): The username to convert.

        Returns:
            Optional[str]: The id of the username if found.
        """
        try:
            params = {
                "include_ext_is_blue_verified": "1",
                "include_ext_verified_type": "1",
                "include_ext_profile_image_shape": "1",
                "q": username,
                "src": "compose_message",
                "result_type": "users",
            }
            response = session.get(
                "https://twitter.com/i/api/1.1/search/typeahead.json", params=params
            )
            if response.status_code == 200:
                jsn = response.json()
                return jsn.get("users", [{}])[0].get("id_str")
            return None
        except Exception:
            return None

    def id_to_username(self, user_id: int) -> Optional[str]:
        """Converts a given id to its username using tweeterid.

        Args:
            user_id (int): The id to convert.

        Returns:
            Optional[str]: The username of the id if found.
        """
        try:
            data = {"input": str(user_id)}
            response = rpost("https://tweeterid.com/ajax.php", data=data, timeout=30)
            if response.status_code == 200 and response.text.startswith("@"):
                return response.text[1:]
            return str(user_id)
        except Exception:
            return None

    def tweet_id_to_username(
        self, session: httpx.Client, tweet_id: int
    ) -> Optional[Union[str, int]]:
        """Gets the username of the person who posted a given tweet.

        Args:
            session (httpx.Client): The sssssssssssssssss session.
            tweet_id (int): The id of the tweet.

        Returns:
            Optional[str]: The username of the person who posted the tweet if found or status code.
        """
        params = {
            "variables": f'{{"focalTweetId":"{tweet_id}","with_rux_injections":false,"includePromotedContent":true,"withCommunity":true,"withQuickPromoteEligibilityTweetFields":true,"withBirdwatchNotes":true,"withVoice":true,"withV2Timeline":true}}',
            "features": '{"responsive_web_graphql_exclude_directive_enabled":true,"verified_phone_label_enabled":false,"responsive_web_home_pinned_timelines_enabled":true,"creator_subscriptions_tweet_preview_api_enabled":true,"responsive_web_graphql_timeline_navigation_enabled":true,"responsive_web_graphql_skip_user_profile_image_extensions_enabled":false,"c9s_tweet_anatomy_moderator_badge_enabled":true,"tweetypie_unmention_optimization_enabled":true,"responsive_web_edit_tweet_api_enabled":true,"graphql_is_translatable_rweb_tweet_is_translatable_enabled":true,"view_counts_everywhere_api_enabled":true,"longform_notetweets_consumption_enabled":true,"responsive_web_twitter_article_tweet_consumption_enabled":false,"tweet_awards_web_tipping_enabled":false,"freedom_of_speech_not_reach_fetch_enabled":true,"standardized_nudges_misinfo":true,"tweet_with_visibility_results_prefer_gql_limited_actions_policy_enabled":true,"longform_notetweets_rich_text_read_enabled":true,"longform_notetweets_inline_media_enabled":true,"responsive_web_media_download_video_enabled":false,"responsive_web_enhance_cards_enabled":false}',
            "fieldToggles": '{"withArticleRichContentState":false}',
        }

        response = session.get(
            "https://twitter.com/i/api/graphql/4EQGUyO_lbCtGin4PT7MOQ/TweetDetail",
            params=params,
        )
        if response.status_code != 200:
            return response.status_code
        extracted = utils.extract_info(
            response.json()["data"]["threaded_conversation_with_injections_v2"][
                "instructions"
            ][0]["entries"][0]
        )
        if extracted:
            return extracted[0]
        return None

    def search_by_keyword(
        self,
        session: httpx.Client,
        query: str,
        sort_by: Optional[str] = "Latest",
        count: Optional[int] = 20,
    ) -> Union[List[Dict[str, Any]], int]:
        """Searches for tweets matching a given keyword.

        Args:
            session (httpx.Client): The sssssssssssssssss session.
            query (str): The keyword to search for.
            sort_by (Optional[str], optional): The sorting method. Defaults to "Latest".
            count (Optional[int], optional): The amount of tweets to get. Defaults and maxes to 20.

        Returns:
            Union[List[Dict[str, Any]], int]: A List of tweets or response status code if failed.
        """
        params = {
            "variables": f'{{"rawQuery":"{query}","count":{count},"querySource":"typed_query","product":"{sort_by.title()}"}}',
            "features": '{"responsive_web_graphql_exclude_directive_enabled":true,"verified_phone_label_enabled":false,"responsive_web_home_pinned_timelines_enabled":true,"creator_subscriptions_tweet_preview_api_enabled":true,"responsive_web_graphql_timeline_navigation_enabled":true,"responsive_web_graphql_skip_user_profile_image_extensions_enabled":false,"c9s_tweet_anatomy_moderator_badge_enabled":true,"tweetypie_unmention_optimization_enabled":true,"responsive_web_edit_tweet_api_enabled":true,"graphql_is_translatable_rweb_tweet_is_translatable_enabled":true,"view_counts_everywhere_api_enabled":true,"longform_notetweets_consumption_enabled":true,"responsive_web_twitter_article_tweet_consumption_enabled":false,"tweet_awards_web_tipping_enabled":false,"freedom_of_speech_not_reach_fetch_enabled":true,"standardized_nudges_misinfo":true,"tweet_with_visibility_results_prefer_gql_limited_actions_policy_enabled":true,"longform_notetweets_rich_text_read_enabled":true,"longform_notetweets_inline_media_enabled":true,"responsive_web_media_download_video_enabled":false,"responsive_web_enhance_cards_enabled":false}',
        }
        response = session.get(
            "https://twitter.com/i/api/graphql/lMv4QkY3vpla38q9tiD-tA/SearchTimeline",
            params=params,
        )
        try:
            jsn = response.json()
            entries = jsn["data"]["search_by_raw_query"]["search_timeline"]["timeline"][
                "instructions"
            ][0]["entries"]
            return utils.parse_tweets(entries)
        except Exception as e:
            self.logger.error(
                f"Failed to search tweets with query {query} ({response.status_code}) {e}"
            )
            if response.status_code == 429:
                return 429
            return response.status_code

    def like_tweet(
        self,
        session: httpx.Client,
        tweet_id: str,
    ) -> Union[bool, int]:
        """Likes a tweet.

        Args:
            session (httpx.Client): The sssssssssssssssss session.
            tweet_id (str): The id of the tweet to like.

        Returns:
            Union[bool, int]: Success status or response status code.
        """
        payload = {
            "variables": {
                "tweet_id": tweet_id,
            },
            "queryId": "lI07N6Otwv1PhnEgXILM7A",
        }

        response = session.post(
            "https://twitter.com/i/api/graphql/lI07N6Otwv1PhnEgXILM7A/FavoriteTweet",
            json=payload,
        )

        if response.status_code == 429:
            return 429
        return (
            response.status_code == 200
            and response.json()["data"]["favorite_tweet"] == "Done"
        )

    def repost_tweet(
        self,
        session: httpx.Client,
        tweet_id: str,
    ) -> Union[bool, int]:
        """Reposts a given tweet.

        Args:
            session (httpx.Client): The sssssssssssssssss session.
            tweet_id (str): The id of the tweet to repost.

        Returns:
            Union[bool, int]: Success status or response status code.
        """
        payload = {
            "variables": {
                "tweet_id": tweet_id,
                "dark_request": False,
            },
            "queryId": "ojPdsZsimiJrUGLR1sjUtA",
        }

        response = session.post(
            "https://twitter.com/i/api/graphql/ojPdsZsimiJrUGLR1sjUtA/CreateRetweet",
            json=payload,
        )
        if response.status_code == 429:
            return 429
        errors = response.json().get("errors", False)
        return response.status_code == 200 and not errors

    def quote_tweet(
        self,
        session: httpx.Client,
        tweet_id: str,
        text: str,
        username: Optional[str],
    ) -> Union[bool, int]:
        """Quotes a given tweet.

        Args:
            session (httpx.Client): The sssssssssssssssss session.
            tweet_id (str): The id of the tweet to quote.
            text (str): The text of the quote.
            username (Optional[str]): The username of the user to quote.

        Returns:
            Union[bool, int]: Success status or response status code.
        """
        if not username:
            username = self.tweet_id_to_username(session, tweet_id)
        if not username:
            return False
        payload = {
            "variables": {
                "tweet_text": text,
                "attachment_url": f"https://twitter.com/{username}/status/{tweet_id}",
                "dark_request": False,
                "media": {
                    "media_entities": [],
                    "possibly_sensitive": False,
                },
                "semantic_annotation_ids": [],
            },
            "features": {
                "c9s_tweet_anatomy_moderator_badge_enabled": True,
                "tweetypie_unmention_optimization_enabled": True,
                "responsive_web_edit_tweet_api_enabled": True,
                "graphql_is_translatable_rweb_tweet_is_translatable_enabled": True,
                "view_counts_everywhere_api_enabled": True,
                "longform_notetweets_consumption_enabled": True,
                "responsive_web_twitter_article_tweet_consumption_enabled": False,
                "tweet_awards_web_tipping_enabled": False,
                "responsive_web_home_pinned_timelines_enabled": True,
                "longform_notetweets_rich_text_read_enabled": True,
                "longform_notetweets_inline_media_enabled": True,
                "responsive_web_graphql_exclude_directive_enabled": True,
                "verified_phone_label_enabled": False,
                "freedom_of_speech_not_reach_fetch_enabled": True,
                "standardized_nudges_misinfo": True,
                "tweet_with_visibility_results_prefer_gql_limited_actions_policy_enabled": True,
                "responsive_web_media_download_video_enabled": False,
                "responsive_web_graphql_skip_user_profile_image_extensions_enabled": False,
                "responsive_web_graphql_timeline_navigation_enabled": True,
                "responsive_web_enhance_cards_enabled": False,
            },
            "queryId": "I_J3_LvnnihD0Gjbq5pD2g",
        }

        response = session.post(
            "https://twitter.com/i/api/graphql/I_J3_LvnnihD0Gjbq5pD2g/CreateTweet",
            json=payload,
        )

        if response.status_code == 429:
            return 429
        errors = response.json().get("errors", False)
        return response.status_code == 200 and not errors

    def post_tweet(
        self,
        session: httpx.Client,
        text: Optional[str] = None,
        media_ids: Optional[List[str]] = None,
    ) -> bool:
        if not text and not media_ids:
            return
        payload = {
            "variables": {
                "tweet_text": text if text else "",
                "dark_request": False,
                "media": {
                    "media_entities": [
                        {
                            "media_id": media_id,
                            "tagged_users": [],
                        }
                        for media_id in media_ids
                    ],
                    "possibly_sensitive": False,
                },
                "semantic_annotation_ids": [],
            },
            "features": {
                "c9s_tweet_anatomy_moderator_badge_enabled": True,
                "tweetypie_unmention_optimization_enabled": True,
                "responsive_web_edit_tweet_api_enabled": True,
                "graphql_is_translatable_rweb_tweet_is_translatable_enabled": True,
                "view_counts_everywhere_api_enabled": True,
                "longform_notetweets_consumption_enabled": True,
                "responsive_web_twitter_article_tweet_consumption_enabled": False,
                "tweet_awards_web_tipping_enabled": False,
                "longform_notetweets_rich_text_read_enabled": True,
                "longform_notetweets_inline_media_enabled": True,
                "rweb_video_timestamps_enabled": True,
                "responsive_web_graphql_exclude_directive_enabled": True,
                "verified_phone_label_enabled": False,
                "freedom_of_speech_not_reach_fetch_enabled": True,
                "standardized_nudges_misinfo": True,
                "tweet_with_visibility_results_prefer_gql_limited_actions_policy_enabled": True,
                "responsive_web_media_download_video_enabled": False,
                "responsive_web_graphql_skip_user_profile_image_extensions_enabled": False,
                "responsive_web_graphql_timeline_navigation_enabled": True,
                "responsive_web_enhance_cards_enabled": False,
            },
            "queryId": "bDE2rBtZb3uyrczSZ_pI9g",
        }
        response = session.post(
            "https://twitter.com/i/api/graphql/bDE2rBtZb3uyrczSZ_pI9g/CreateTweet",
            json=payload,
        )
        return response.status_code == 200

    def reply_to_tweet(
        self,
        session: httpx.Client,
        tweet_id: str,
        text: str,
    ) -> Union[bool, int]:
        """Replies to a given tweet.

        Args:
            session (httpx.Client): The sssssssssssssssss session.
            tweet_id (str): The id of the tweet to reply to.
            text (str): The text of the reply.

        Returns:
            Union[bool, int]: Success status or response status code.
        """
        payload = {
            "variables": {
                "tweet_text": text,
                "reply": {
                    "in_reply_to_tweet_id": tweet_id,
                    "exclude_reply_user_ids": [],
                },
                "dark_request": False,
                "media": {
                    "media_entities": [],
                    "possibly_sensitive": False,
                },
                "semantic_annotation_ids": [],
            },
            "features": {
                "c9s_tweet_anatomy_moderator_badge_enabled": True,
                "tweetypie_unmention_optimization_enabled": True,
                "responsive_web_edit_tweet_api_enabled": True,
                "graphql_is_translatable_rweb_tweet_is_translatable_enabled": True,
                "view_counts_everywhere_api_enabled": True,
                "longform_notetweets_consumption_enabled": True,
                "responsive_web_twitter_article_tweet_consumption_enabled": False,
                "tweet_awards_web_tipping_enabled": False,
                "responsive_web_home_pinned_timelines_enabled": True,
                "longform_notetweets_rich_text_read_enabled": True,
                "longform_notetweets_inline_media_enabled": True,
                "responsive_web_graphql_exclude_directive_enabled": True,
                "verified_phone_label_enabled": False,
                "freedom_of_speech_not_reach_fetch_enabled": True,
                "standardized_nudges_misinfo": True,
                "tweet_with_visibility_results_prefer_gql_limited_actions_policy_enabled": True,
                "responsive_web_media_download_video_enabled": False,
                "responsive_web_graphql_skip_user_profile_image_extensions_enabled": False,
                "responsive_web_graphql_timeline_navigation_enabled": True,
                "responsive_web_enhance_cards_enabled": False,
            },
            "queryId": "I_J3_LvnnihD0Gjbq5pD2g",
        }

        response = session.post(
            "https://twitter.com/i/api/graphql/I_J3_LvnnihD0Gjbq5pD2g/CreateTweet",
            json=payload,
        )

        if response.status_code == 429:
            return 429
        errors = response.json().get("errors", False)
        return response.status_code == 200 and not errors

    def _friendship(
        self, session: httpx.Client, user_id: str, action: str
    ) -> bool:
        payload = {
            "include_profile_interstitial_type": "1",
            "include_blocking": "1",
            "include_blocked_by": "1",
            "include_followed_by": "1",
            "include_want_retweets": "1",
            "include_mute_edge": "1",
            "include_can_dm": "1",
            "include_can_media_tag": "1",
            "include_ext_has_nft_avatar": "1",
            "include_ext_is_blue_verified": "1",
            "include_ext_verified_type": "1",
            "include_ext_profile_image_shape": "1",
            "skip_status": "1",
            "user_id": user_id,
        }
        response = session.post(
            f"https://twitter.com/i/api/1.1/friendships/{action}.json",
            data=payload,
            headers={
                **session.headers,
                "content-type": "application/x-www-form-urlencoded",
            },
        )
        return response.status_code == 200

    def follow_user(self, session: httpx.Client, user_id: str) -> bool:
        """Follows a given user.

        Args:
            session (httpx.Client): The sssssssssssssssss session.
            user_id (str): The id of the user to follow.

        Returns:
            bool: Success status.
        """
        return self._friendship(session, user_id, "create")

    def unfollow_user(self, session: httpx.Client, user_id: str) -> bool:
        """Unfollows a given user.

        Args:
            session (httpx.Client): The sssssssssssssssss session.
            user_id (str): The id of the user to follow.

        Returns:
            bool: Success status.
        """
        return self._friendship(session, user_id, "destroy")

    def send_dm(
        self, session: httpx.Client, our_id: str, user_id: str, text: str
    ) -> bool:
        """Sends a direct message to a given user.

        Args:
            session (httpx.Client): The sssssssssssssssss session.
            our_id (str): Our user id.
            user_id (str): Target user id.
            text (str): The text to send.

        Returns:
            bool: Success status.
        """
        params = {
            "ext": "mediaColor,altText,mediaStats,highlightedLabel,hasNftAvatar,voiceInfo,birdwatchPivot,superFollowMetadata,unmentionInfo,editControl",
            "include_ext_alt_text": "true",
            "include_ext_limited_action_results": "true",
            "include_reply_count": "1",
            "tweet_mode": "extended",
            "include_ext_views": "true",
            "include_groups": "true",
            "include_inbox_timelines": "true",
            "include_ext_media_color": "true",
            "supports_reactions": "true",
        }

        payload = {
            "conversation_id": f"{our_id}-{user_id}",
            "recipient_ids": False,
            "request_id": str(uuid4()),
            "text": text,
            "cards_platform": "Web-12",
            "include_cards": 1,
            "include_quote_count": True,
            "dm_users": False,
        }

        response = session.post(
            "https://twitter.com/i/api/1.1/dm/new2.json", params=params, json=payload
        )
        return response.status_code == 200

    def get_for_you_page(
        self,
        session: httpx.Client,
        amount: Optional[int] = 20,
    ) -> List[Optional[utils.Tweet]]:
        """Get for you page.

        Args:
            session (httpx.Client): The sssssssssssssssss session.
            amount (int): The amount of tweets to fetch.

        Returns:
            List[Optional[utils.Tweet]]: A List of tweets.
        """
        params = {
            "variables": f'{{"count":{amount},"includePromotedContent":true,"latestControlAvailable":true,"requestContext":"launch","withCommunity":true}}',
            "features": '{"rweb_Lists_timeline_redesign_enabled":true,"responsive_web_graphql_exclude_directive_enabled":true,"verified_phone_label_enabled":false,"creator_subscriptions_tweet_preview_api_enabled":true,"responsive_web_graphql_timeline_navigation_enabled":true,"responsive_web_graphql_skip_user_profile_image_extensions_enabled":false,"tweetypie_unmention_optimization_enabled":true,"responsive_web_edit_tweet_api_enabled":true,"graphql_is_translatable_rweb_tweet_is_translatable_enabled":true,"view_counts_everywhere_api_enabled":true,"longform_notetweets_consumption_enabled":true,"responsive_web_twitter_article_tweet_consumption_enabled":false,"tweet_awards_web_tipping_enabled":false,"freedom_of_speech_not_reach_fetch_enabled":true,"standardized_nudges_misinfo":true,"tweet_with_visibility_results_prefer_gql_limited_actions_policy_enabled":true,"longform_notetweets_rich_text_read_enabled":true,"longform_notetweets_inline_media_enabled":true,"responsive_web_media_download_video_enabled":false,"responsive_web_enhance_cards_enabled":false}',
        }
        response = session.get(
            "https://twitter.com/i/api/graphql/W4Tpu1uueTGK53paUgxF0Q/HomeTimeline",
            params=params,
        )
        try:
            entries = response.json()["data"]["home"]["home_timeline_urt"][
                "instructions"
            ][0]["entries"]
            tweets = utils.parse_tweets(entries)
            return tweets
        except Exception as e:
            print(e)
            return []

    def get_comments(
        self,
        session: httpx.Client,
        tweet_id: str,
    ) -> List[Optional[utils.Tweet]]:
        """Get comments for a given tweet.

        Args:
            session (httpx.Client): The sssssssssssssssss session.
            tweet_id (str): The id of the tweet.

        Returns:
            List[Optional[Dict[str, Any]]]: A List of tweets.
        """
        params = {
            "variables": '{"focalTweetId":"'
            + tweet_id
            + '","referrer":"home","controller_data":"DAACDAABDAABCgABAIAAQkIDAAEKAAIAAAAAAAEgAAoACeJa9n0otwfqCAALAAAAAA8ADAMAAAAZAQADQkIAgAAAIAEAAAAAAAAAAAAAAAAAgAoADnxYWOnkEUkHCgAQ3FGv8aD8ZY8AAAAA","with_rux_injections":false,"includePromotedContent":true,"withCommunity":true,"withQuickPromoteEligibilityTweetFields":true,"withBirdwatchNotes":true,"withVoice":true,"withV2Timeline":true}',
            "features": '{"rweb_Lists_timeline_redesign_enabled":true,"responsive_web_graphql_exclude_directive_enabled":true,"verified_phone_label_enabled":false,"creator_subscriptions_tweet_preview_api_enabled":true,"responsive_web_graphql_timeline_navigation_enabled":true,"responsive_web_graphql_skip_user_profile_image_extensions_enabled":false,"tweetypie_unmention_optimization_enabled":true,"responsive_web_edit_tweet_api_enabled":true,"graphql_is_translatable_rweb_tweet_is_translatable_enabled":true,"view_counts_everywhere_api_enabled":true,"longform_notetweets_consumption_enabled":true,"responsive_web_twitter_article_tweet_consumption_enabled":false,"tweet_awards_web_tipping_enabled":false,"freedom_of_speech_not_reach_fetch_enabled":true,"standardized_nudges_misinfo":true,"tweet_with_visibility_results_prefer_gql_limited_actions_policy_enabled":true,"longform_notetweets_rich_text_read_enabled":true,"longform_notetweets_inline_media_enabled":true,"responsive_web_media_download_video_enabled":false,"responsive_web_enhance_cards_enabled":false}',
            "fieldToggles": '{"withArticleRichContentState":false}',
        }
        response = session.get(
            "https://twitter.com/i/api/graphql/q94uRCEn65LZThakYcPT6g/TweetDetail",
            params=params,
        )
        try:
            entries = response.json()["data"][
                "threaded_conversation_with_injections_v2"
            ]["instructions"][0]["entries"]
            tweets = utils.parse_tweets(entries)
            return tweets
        except Exception:
            return []

    @staticmethod
    def get_file_size(file: str) -> str:
        try:
            return str(path.getsize(file))
        except FileNotFoundError:
            print(f"Error: File '{file}' not found.")
            return None

    @property
    def media_types(self) -> Dict[str, str]:
        return {
            "image/jpeg": "tweet_image",
            "video/mp4": "tweet_video",
        }

    def get_video_length(self, filename: str) -> float:
        result = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                filename,
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )

        return float(result.stdout) * 1000

    def _init_upload(
        self,
        session: httpx.Client,
        size: str,
        media_type: str,
        video_length: Optional[float] = None,
    ) -> str:
        media_category = self.media_types.get(media_type)
        params = {
            "command": "INIT",
            "total_bytes": size,
            "media_type": media_type,
            "media_category": media_category,
        }
        if video_length:
            params["video_duration_ms"] = math.floor(video_length * 10**3) / 10**3
        response = session.post(
            "https://upload.twitter.com/i/media/upload.json",
            params=params,
        )
        if response.status_code == 202:
            return response.json()["media_id"]

    def _first_append(self, session: httpx.Client, media_id: str) -> bool:
        headers = {
            "authority": "upload.sssssssssssssssss.com",
            "accept": "*/*",
            "accept-language": "en-US,en;q=0.9",
            "access-control-request-headers": "authorization,x-csrf-token,x-sssssssssssssssss-auth-type",
            "access-control-request-method": "POST",
            "origin": "https://twitter.com",
            "referer": "https://twitter.com/",
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-site",
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        }

        params = {
            "command": "APPEND",
            "media_id": media_id,
            "segment_index": "0",
        }
        response = session.options(
            "https://upload.twitter.com/i/media/upload.json",
            params=params,
            headers=headers,
        )
        return response.status_code == 200

    def _upload_content(
        self, session: httpx.Client, media_id: str, file: str
    ) -> bool:
        params = {
            "command": "APPEND",
            "media_id": media_id,
            "segment_index": "0",
        }
        headers = {
            "authority": "upload.sssssssssssssssss.com",
            "accept": "*/*",
            "accept-language": "en-US,en;q=0.6",
            "authorization": "Bearer AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs%3D1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA",
            "origin": "https://twitter.com",
            "referer": "https://twitter.com/",
            "sec-ch-ua": '"Not_A Brand";v="8", "Chromium";v="120", "Brave";v="120"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-site",
            "sec-gpc": "1",
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "x-csrf-token": session.headers["x-csrf-token"],
            "x-sssssssssssssssss-auth-type": "OAuth2Session",
        }

        if not file.startswith("http"):
            with open(file, "rb") as f:
                file_content = f.read()
        else:
            file_content = rget(file).content

        response = rpost(
            "https://upload.twitter.com/i/media/upload.json",
            params=params,
            files={"media": file_content},
            cookies=session.cookies,
            headers=headers,
        )
        return response.status_code == 204

    def _finalize(
        self, session: httpx.Client, media_id: str, media_type: str
    ) -> str:
        headers = {
            "authority": "upload.sssssssssssssssss.com",
            "accept": "*/*",
            "accept-language": "en-US,en;q=0.9",
            "access-control-request-headers": "authorization,x-csrf-token,x-sssssssssssssssss-auth-type",
            "access-control-request-method": "POST",
            "origin": "https://twitter.com",
            "referer": "https://twitter.com/",
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-site",
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        }

        params = {
            "command": "FINALIZE",
            "media_id": media_id,
        }
        if media_type == "video/mp4":
            params["allow_async"] = True
        first = session.options(
            "https://upload.twitter.com/i/media/upload.json",
            params=params,
            headers=headers,
        )
        if first.status_code == 200:
            response = session.post(
                "https://upload.twitter.com/i/media/upload.json", params=params
            )
            if response.status_code in [200, 201]:
                return response.json()["media_id_string"]

    def do_video_check(self, session: httpx.Client, media_id: str) -> bool:
        params = {
            "command": "STATUS",
            "media_id": media_id,
        }
        response = session.get(
            "https://upload.twitter.com/i/media/upload.json", params=params
        ).json()
        while response["processing_info"]["state"] == "in_progress":
            to_sleep = response["processing_info"]["check_after_secs"]
            progress = response["processing_info"]["progress_percent"]
            print(f"Video {media_id} not uploaded yet, progress: {progress}%")
            time.sleep(to_sleep)
            response = session.get(
                "https://upload.twitter.com/i/media/upload.json", params=params
            ).json()
        return True

    def download(self, url: str, output_dir: Optional[str] = None):
        if not output_dir:
            output_dir = "."
        if not path.exists(output_dir):
            mkdir(output_dir)
        print(f"Downloading {url}...")
        output = output_dir + "/" + url.split("/")[-1]
        with open(output, "wb") as file, tqdm(
            desc=output,
            total=int(rhead(url).headers["Content-Length"]),
            unit="B",
            unit_scale=True,
            unit_divisor=1024,
        ) as bar:
            response = rget(url, stream=True)
            for chunk in response.iter_content(chunk_size=1024):
                if chunk:
                    file.write(chunk)
                    bar.update(len(chunk))

    @cleanup
    def upload(self, session: httpx.Client, file: str) -> Optional[str]:
        if file.startswith("http"):
            r = rget(file)
            size = len(r.content)
        else:
            size = self.get_file_size(file)
        if file[-3:] in ["jpg", "jpeg", "png"]:
            media_type = "image/jpeg"
        else:
            media_type = "video/mp4"
        video_size = None
        if media_type == "video/mp4":
            video_size = self.get_video_length(file)

        media_id = self._init_upload(session, size, media_type, video_size)
        if media_id is None:
            return "no_media_id"
        appended = self._first_append(session, media_id)
        if not appended:
            return "no_append"
        uploaded = self._upload_content(session, media_id, file)
        if not uploaded:
            return "no_upload"
        return self._finalize(session, media_id, media_type)

    def fetch_latest_user_posts(
        self, session: httpx.Client, user_id: str
    ) -> Optional[List]:
        params = {
            "variables": f'{{"userId":{user_id},"count":20,"includePromotedContent":false,"withClientEventToken":false,"withBirdwatchNotes":false,"withVoice":false,"withV2Timeline":true}}',
            "features": '{"responsive_web_graphql_exclude_directive_enabled":true,"verified_phone_label_enabled":false,"creator_subscriptions_tweet_preview_api_enabled":true,"responsive_web_graphql_timeline_navigation_enabled":true,"responsive_web_graphql_skip_user_profile_image_extensions_enabled":false,"c9s_tweet_anatomy_moderator_badge_enabled":true,"tweetypie_unmention_optimization_enabled":true,"responsive_web_edit_tweet_api_enabled":true,"graphql_is_translatable_rweb_tweet_is_translatable_enabled":true,"view_counts_everywhere_api_enabled":true,"longform_notetweets_consumption_enabled":true,"responsive_web_twitter_article_tweet_consumption_enabled":false,"tweet_awards_web_tipping_enabled":false,"freedom_of_speech_not_reach_fetch_enabled":true,"standardized_nudges_misinfo":true,"tweet_with_visibility_results_prefer_gql_limited_actions_policy_enabled":true,"rweb_video_timestamps_enabled":true,"longform_notetweets_rich_text_read_enabled":true,"longform_notetweets_inline_media_enabled":true,"responsive_web_media_download_video_enabled":false,"responsive_web_enhance_cards_enabled":false}',
        }

        response = session.get(
            "https://twitter.com/i/api/graphql/V1ze5q3ijDS1VeLwLY0m7g/UserTweets",
            params=params,
        )
        jsn = response.json()
        posts = jsn["data"]["user"]["result"]["timeline_v2"]["timeline"][
            "instructions"
        ][-1]["entries"]
        tweets = utils.parse_profile_tweets(posts)
        return tweets

    def init_basic_session(self, token: str) -> httpx.Client:
        context = httpx.create_ssl_context()
        cipher1 = 'ECDH+AESGCM:ECDH+CHACHA20:DH+AESGCM:DH+CHACHA20:ECDH+AES256:DH+AES256:ECDH+AES128:DH+AES:ECDH+HIGH:DH+HIGH:RSA+AESGCM:RSA+AES:RSA+HIGH'
        context.set_alpn_protocols(['h2'])
        context.set_ciphers(cipher1)
        session = httpx.Client(
            http2=True, verify=context, timeout=30,
        )
        session.cookies["auth_token"] = token
        if self.proxies:
            proxy = random.choice(self.proxies)
            session.proxies = {"all://": f"http://{proxy}"}
        session.headers = {
            'authority': 'twitter.com',
            'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'accept-language': 'en-US,en;q=0.8',
            'cache-control': 'no-cache',
            'pragma': 'no-cache',
            'referer': 'https://twitter.com',
            'sec-ch-ua': '"Not A(Brand";v="99", "Brave";v="121", "Chromium";v="121"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'sec-fetch-dest': 'document',
            'sec-fetch-mode': 'navigate',
            'sec-fetch-site': 'same-origin',
            'sec-fetch-user': '?1',
            'sec-gpc': '1',
            'upgrade-insecure-requests': '1',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
        }
        return session
