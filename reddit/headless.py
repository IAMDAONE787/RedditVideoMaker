"""
Fetch Reddit posts via the public .json listing endpoint — no OAuth, no PRAW.

Returns the same ``reddit_object`` dict shape that ``reddit.subreddit.get_subreddit_threads``
produces, so the rest of the pipeline (TTS, screenshots / imagemaker, final video) works
unchanged.

Reference: https://github.com/vitgruib/apiless-reddit-tiktok-video-bot/blob/main/docs/REPLICATING_API_CALLS.md
"""

import html
import json
import random
from os.path import exists

import requests

from utils import settings
from utils.console import print_step, print_substep
from utils.voice import sanitize_text

USER_AGENT = "RedditVideoBot/1.0 (educational; no OAuth)"


def get_subreddit_threads_headless(POST_ID: str = None) -> dict:
    """Scrape a subreddit listing (or a specific post) and return a reddit_object dict."""

    print_step("Getting subreddit threads (headless, no API key)...")

    subreddit = settings.config["reddit"]["thread"]["subreddit"]
    if str(subreddit).casefold().startswith("r/"):
        subreddit = subreddit[2:]

    headers = {"User-Agent": USER_AGENT}

    # --- specific post by ID ---------------------------------------------------
    if POST_ID:
        url = f"https://www.reddit.com/comments/{POST_ID}.json?raw_json=1"
        resp = requests.get(url, headers=headers, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        post_data = data[0]["data"]["children"][0]["data"]
        comments_listing = data[1] if len(data) > 1 else None
        return _build_content(post_data, comments_listing)

    # --- subreddit listing -----------------------------------------------------
    url = f"https://www.reddit.com/r/{subreddit}/hot.json?raw_json=1&limit=25"
    print_substep(f"Fetching {url}")
    resp = requests.get(url, headers=headers, timeout=30)
    resp.raise_for_status()
    listing = resp.json()

    done_ids = _load_done_ids()
    storymode = settings.config["settings"]["storymode"]

    candidates = []
    for child in listing["data"]["children"]:
        if child.get("kind") != "t3":
            continue
        ld = child["data"]
        if ld.get("stickied") or ld.get("promoted"):
            continue
        if not ld.get("title"):
            continue
        if ld["id"] in done_ids:
            continue
        if ld.get("over_18") and not settings.config["settings"]["allow_nsfw"]:
            print_substep("NSFW post skipped.", style="dim")
            continue
        if storymode:
            if not ld.get("selftext") or not ld.get("is_self"):
                continue
            max_len = settings.config["settings"].get("storymode_max_length") or 2000
            if len(ld["selftext"]) > max_len or len(ld["selftext"]) < 30:
                continue
        else:
            min_comments = int(settings.config["reddit"]["thread"].get("min_comments", 20))
            if ld.get("num_comments", 0) < min_comments:
                continue
        candidates.append(ld)

    if not candidates:
        print_substep("No suitable posts found via headless scraping!", style="bold red")
        raise RuntimeError(
            "No suitable Reddit posts found. Try a different subreddit or loosen filters."
        )

    post_data = random.choice(candidates) if settings.config["reddit"]["thread"].get("random") else candidates[0]

    # For non-storymode we need comments from the individual post endpoint.
    comments_listing = None
    if not storymode:
        permalink = post_data.get("permalink", "")
        comments_url = f"https://www.reddit.com{permalink}.json?raw_json=1&limit=100"
        print_substep(f"Fetching comments from {comments_url}")
        cresp = requests.get(comments_url, headers=headers, timeout=30)
        cresp.raise_for_status()
        cdata = cresp.json()
        if len(cdata) > 1:
            comments_listing = cdata[1]

    return _build_content(post_data, comments_listing)


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _load_done_ids() -> set:
    path = "./video_creation/data/videos.json"
    if not exists(path):
        return set()
    with open(path, "r", encoding="utf-8") as f:
        return {v["id"] for v in json.load(f)}


def _build_content(post_data: dict, comments_listing=None) -> dict:
    """Transform raw Reddit JSON into the reddit_object dict the pipeline expects."""

    title = html.unescape(post_data.get("title", ""))
    selftext = html.unescape(post_data.get("selftext", "") or "")
    permalink = post_data.get("permalink", "")
    thread_url = (
        f"https://www.reddit.com{permalink}" if permalink.startswith("/") else permalink
    )
    thread_id = post_data.get("id", "")

    print_substep(f"Video will be: {title}", style="bold green")
    print_substep(f"Thread url is: {thread_url}", style="bold green")
    print_substep(f"Thread has {post_data.get('score', 0)} upvotes", style="bold blue")
    print_substep(
        f"Thread has {post_data.get('num_comments', 0)} comments", style="bold blue"
    )

    content: dict = {
        "thread_url": thread_url,
        "thread_title": title,
        "thread_id": thread_id,
        "is_nsfw": post_data.get("over_18", False),
        "thread_upvotes": post_data.get("score", 0),
        "thread_comments": post_data.get("num_comments", 0),
        "comments": [],
    }

    if settings.config["settings"]["storymode"]:
        if settings.config["settings"]["storymodemethod"] == 1:
            from utils.posttextparser import posttextparser
            content["thread_post"] = posttextparser(selftext)
        else:
            content["thread_post"] = selftext
    elif comments_listing:
        _parse_comments(content, comments_listing)

    print_substep("Received subreddit threads successfully (headless).", style="bold green")
    return content


def _parse_comments(content: dict, comments_listing: dict) -> None:
    max_len = int(settings.config["reddit"]["thread"]["max_comment_length"])
    min_len = int(settings.config["reddit"]["thread"].get("min_comment_length", 1))

    for child in comments_listing["data"]["children"]:
        if child.get("kind") != "t1":
            continue
        cd = child["data"]
        body = cd.get("body", "")
        if body in ("[removed]", "[deleted]"):
            continue
        if cd.get("stickied"):
            continue
        sanitised = sanitize_text(body)
        if not sanitised or sanitised == " ":
            continue
        if not (min_len <= len(body) <= max_len):
            continue
        if cd.get("author") is None:
            continue
        content["comments"].append(
            {
                "comment_body": body,
                "comment_url": cd.get("permalink", ""),
                "comment_id": cd.get("id", ""),
            }
        )
