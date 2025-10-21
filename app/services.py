import requests
from .constants import DISCORD_WEBHOOK_URL, DEBUG_MODE


def send_discord_payload(content=None, embeds=None):
    payload = {}
    if content is not None:
        payload["content"] = content
    if embeds is not None:
        payload["embeds"] = embeds

    resp = requests.post(DISCORD_WEBHOOK_URL, json=payload)
    if DEBUG_MODE:
        try:
            print(f"[DEBUG] Discord response: {resp.status_code}")
            if resp.status_code != 204:
                print(f"[DEBUG] Response content: {resp.text}")
        except Exception:
            pass
    return resp
