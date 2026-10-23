#!/usr/bin/env python3
"""Turn an explicitly opted-in, merged PR into a review-only LinkedIn draft."""
import argparse
import json
import os
import re
from pathlib import Path

from buffer_drafts import CHANNEL_QUERY, DRAFT_MUTATION, ORG_QUERY, request

FIELDS = ("Problem", "Change", "Evidence", "Limits")
REPO = "DavidBenitoCampo/baremetal-platform-lab"


def sections(body):
    found = {}
    for key in FIELDS:
        pattern = rf"(?im)^### Social {key}\s*$\n(.*?)(?=^### |\Z)"
        match = re.search(pattern, body or "", flags=re.DOTALL)
        if not match:
            raise ValueError(f"Missing '### Social {key}' in PR description")
        value = match.group(1).strip()
        if not value or value in ("None", "N/A", "-"):
            raise ValueError(f"Empty social evidence: {key}")
        if len(value) > 600 or any(c in value for c in ("<", ">")):
            raise ValueError(f"Social {key} needs plain text below 600 characters")
        found[key] = " ".join(value.split())
    return found


def compose(pr):
    if not pr.get("merged") or pr.get("base", {}).get("ref") != "main":
        raise ValueError("Expected a merged PR targeting main")
    if not any(label.get("name") == "social-ready" for label in pr.get("labels", [])):
        raise ValueError("PR is not opted in for social publishing")
    s = sections(pr.get("body"))
    number = pr["number"]
    url = f"https://github.com/{REPO}/pull/{number}"
    post = (
        f"{s['Problem']}\n\n"
        f"What I changed:\n{s['Change']}\n\n"
        f"What I observed:\n{s['Evidence']}\n\n"
        f"What still needs work:\n{s['Limits']}\n\n"
        f"I'm documenting the design and operating trade-offs in my Raspberry Pi 5 "
        f"Kubernetes homelab. Feedback from people working with Linux, DevOps, "
        f"SRE or platform engineering is welcome.\n\n"
        f"Technical details: {url}"
    )
    if len(post) > 2700:
        raise ValueError("Draft too long: shorten PR social fields")
    return post


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--create-draft", action="store_true")
    args = parser.parse_args()
    event = json.loads(Path(os.environ["GITHUB_EVENT_PATH"]).read_text())
    post = compose(event["pull_request"])
    print("LinkedIn social draft preview:\n" + post)
    if not args.create_draft:
        print("Preview only; nothing sent.")
        return
    key = os.environ.get("BUFFER_API_KEY", "").strip()
    if not key:
        raise RuntimeError("Missing BUFFER_API_KEY")
    orgs = request(key, ORG_QUERY)["account"]["organizations"]
    if len(orgs) != 1:
        raise RuntimeError("Expected exactly one Buffer organization")
    channels = request(key, CHANNEL_QUERY, {"id": orgs[0]["id"]})["channels"]
    linkedin = [c for c in channels if str(c["service"]).lower() == "linkedin"]
    if len(linkedin) != 1:
        raise RuntimeError("Expected exactly one LinkedIn channel")
    response = request(key, DRAFT_MUTATION, {"input": {
        "text": post,
        "channelId": linkedin[0]["id"],
        "schedulingType": "automatic",
        "mode": "addToQueue",
        "assets": [],
        "needsApproval": False,
        "saveToDraft": True,
    }})["createPost"]
    if response.get("message") or not (response.get("post") or {}).get("id"):
        raise RuntimeError(response.get("message", "Buffer did not confirm the draft"))
    print("Created LinkedIn draft for manual review in Buffer.")


if __name__ == "__main__":
    main()
