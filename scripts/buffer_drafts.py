#!/usr/bin/env python3
"""Preview or create unscheduled Buffer drafts for the homelab introduction."""
import argparse
import json
import os
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
FILES = {
    "linkedin": ROOT / "posts/social/intro-linkedin.txt",
    "bluesky": ROOT / "posts/social/intro-bluesky.txt",
}
ORG_QUERY = "query { account { organizations { id name } } }"
CHANNEL_QUERY = """
query Channels($id: OrganizationId!) {
  channels(input: {organizationId: $id}) { id name service }
}"""
DRAFT_MUTATION = """
mutation Draft($input: CreatePostInput!) {
  createPost(input: $input) {
    ... on PostActionSuccess { post { id } }
    ... on MutationError { message }
  }
}"""


def request(api_key, query, variables=None):
    body = json.dumps({"query": query, "variables": variables or {}}).encode()
    req = Request("https://api.buffer.com", data=body, method="POST",
                  headers={"Authorization": "Bearer " + api_key,
                           "Content-Type": "application/json"})
    try:
        with urlopen(req, timeout=20) as response:
            result = json.load(response)
    except HTTPError as exc:
        raise RuntimeError("Buffer returned HTTP " + str(exc.code)) from exc
    except URLError as exc:
        raise RuntimeError("Buffer connection error") from exc
    if result.get("errors"):
        raise RuntimeError(result["errors"][0].get("message", "Buffer API error"))
    return result["data"]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--channel", choices=["linkedin", "bluesky", "both"], required=True)
    parser.add_argument("--create-draft", action="store_true")
    args = parser.parse_args()
    selected = list(FILES) if args.channel == "both" else [args.channel]
    posts = {p: FILES[p].read_text(encoding="utf-8").strip() for p in selected}
    for platform, text in posts.items():
        if not text or (platform == "bluesky" and len(text) > 300):
            raise ValueError("Invalid post length for " + platform)
        print("\n=== " + platform.upper() + " ===\n" + text + "\n")
    if not args.create_draft:
        print("Preview only. Nothing sent to Buffer.")
        return

    key = os.getenv("BUFFER_API_KEY", "").strip()
    if not key:
        raise RuntimeError("BUFFER_API_KEY secret missing")

    organizations = request(key, ORG_QUERY)["account"]["organizations"]
    if len(organizations) != 1:
        raise RuntimeError("Expected exactly one Buffer organization")
    channels = request(key, CHANNEL_QUERY, {"id": organizations[0]["id"]})["channels"]
    chosen = {}
    for platform in selected:
        matches = [c for c in channels if str(c["service"]).lower() == platform]
        if len(matches) != 1:
            raise RuntimeError("Expected exactly one connected " + platform + " channel")
        chosen[platform] = matches[0]["id"]
    # All channel checks happen before any drafts are created.
    for platform in selected:
        response = request(key, DRAFT_MUTATION, {"input": {
            "text": posts[platform],
            "channelId": chosen[platform],
            "schedulingType": "automatic",
            "mode": "addToQueue",
            "assets": [],
            "needsApproval": False,
            "saveToDraft": True,
        }})["createPost"]
        if response.get("message"):
            raise RuntimeError(response["message"])
        if not (response.get("post") or {}).get("id"):
            raise RuntimeError("Buffer did not confirm draft")
        print("Draft created for " + platform + ". Review it in Buffer.")


if __name__ == "__main__":
    main()
