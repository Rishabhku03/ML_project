"""Synthetic HTTP traffic generator for ChatSentry endpoints.

Sustained stream dispatch at ~15-20 RPS using asyncio + aiohttp.
Per D-01: Sustained stream dispatch at ~15-20 RPS.
Per D-02: Async concurrency model using asyncio + aiohttp.
Per D-03: Mixed data source — CSV rows AND synthetic HF messages.
Per D-04: Script location: src/data/synthetic_traffic_generator.py.
"""

import argparse
import asyncio
import csv
import logging
import random
import uuid
from typing import Any, Optional

import aiohttp
from huggingface_hub import InferenceClient

from src.data.prompts import LABEL_DISTRIBUTION, PROMPTS_BY_LABEL, LabelType
from src.data.synthetic_generator import _call_hf_api
from src.utils.config import config

logger = logging.getLogger(__name__)

TARGET_RPS = 15


async def load_csv_messages(filepath: str) -> list[str]:
    """Load message texts from the combined dataset CSV.

    Args:
        filepath: Path to the combined_dataset.csv file.

    Returns:
        List of text strings from the CSV's text column.
    """
    messages: list[str] = []
    with open(filepath, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            text = row.get("text", "").strip()
            if text:
                messages.append(text)
    logger.info("Loaded %d messages from %s", len(messages), filepath)
    return messages


def _pick_label() -> LabelType:
    """Pick a label type according to the label distribution.

    Returns:
        A LabelType string.
    """
    labels = list(LABEL_DISTRIBUTION.keys())
    weights = list(LABEL_DISTRIBUTION.values())
    return random.choices(labels, weights=weights, k=1)[0]


async def generate_synthetic_message() -> Optional[dict[str, Any]]:
    """Generate a synthetic message via HuggingFace API.

    Returns:
        Payload dict with text, user_id, source keys, or None on failure.
    """
    label = _pick_label()
    prompt = PROMPTS_BY_LABEL[label]

    client = InferenceClient(
        provider="featherless-ai",
        api_key=config.HF_TOKEN,
    )

    # _call_hf_api is sync, so run in executor to avoid blocking
    loop = asyncio.get_event_loop()
    raw_text = await loop.run_in_executor(None, _call_hf_api, client, prompt)

    if raw_text is None:
        logger.warning("HF API returned None for label %s", label)
        return None

    # Extract first line of generated text
    lines = raw_text.strip().split("\n")
    text = lines[0].strip()
    # Remove numbering prefix if present
    if text and text[0].isdigit():
        dot_pos = text.find(".")
        if dot_pos > 0:
            text = text[dot_pos + 1 :].strip()

    if not text:
        return None

    return {
        "text": text,
        "user_id": str(uuid.uuid4()),
        "source": "synthetic_hf",
    }


async def send_message(
    session: aiohttp.ClientSession, url: str, payload: dict[str, Any]
) -> Optional[dict[str, Any]]:
    """POST a payload to the given URL.

    Args:
        session: aiohttp ClientSession.
        url: Target URL.
        payload: JSON payload dict.

    Returns:
        Response JSON dict or None on error.
    """
    try:
        async with session.post(url, json=payload) as resp:
            if resp.status == 200:
                return await resp.json()
            else:
                body = await resp.text()
                logger.warning(
                    "Non-200 response from %s: %d — %s", url, resp.status, body
                )
                return None
    except aiohttp.ClientError as e:
        logger.error("Connection error posting to %s: %s", url, e)
        return None


def _build_message_payload(csv_messages: list[str]) -> dict[str, Any]:
    """Build a /messages payload from a random CSV row.

    Args:
        csv_messages: List of CSV text strings.

    Returns:
        Payload dict matching MessagePayload schema.
    """
    return {
        "text": random.choice(csv_messages),
        "user_id": str(uuid.uuid4()),
        "source": "real",
    }


def _build_flag_payload() -> dict[str, Any]:
    """Build a /flags payload with random data.

    Returns:
        Payload dict matching FlagPayload schema.
    """
    reasons = ["spam", "harassment", "hate_speech", "self_harm", "other"]
    return {
        "message_id": str(uuid.uuid4()),
        "flagged_by": str(uuid.uuid4()),
        "reason": random.choice(reasons),
    }


async def run_traffic_generator(
    base_url: str = "http://localhost:8000",
    duration_seconds: int = 60,
    rps: int = TARGET_RPS,
    csv_path: str = "combined_dataset.csv",
) -> dict[str, int]:
    """Main loop that dispatches requests at the target RPS.

    Args:
        base_url: Base URL of the FastAPI server.
        duration_seconds: How long to run the generator.
        rps: Target requests per second.
        csv_path: Path to the combined_dataset.csv file.

    Returns:
        Dict with dispatch counters: total, messages, flags, errors.
    """
    csv_messages = await load_csv_messages(csv_path)
    if not csv_messages:
        logger.error("No CSV messages loaded — aborting")
        return {"total": 0, "messages": 0, "flags": 0, "errors": 0}

    interval = 1.0 / rps
    counters = {"total": 0, "messages": 0, "flags": 0, "errors": 0}
    message_url = f"{base_url}/messages"
    flag_url = f"{base_url}/flags"

    logger.info(
        "Starting traffic generator: %d RPS for %ds against %s",
        rps,
        duration_seconds,
        base_url,
    )

    async with aiohttp.ClientSession() as session:
        start_time = asyncio.get_event_loop().time()
        end_time = start_time + duration_seconds
        pending_tasks: list[asyncio.Task] = []

        while asyncio.get_event_loop().time() < end_time:
            dispatch_start = asyncio.get_event_loop().time()

            # 80% messages, 20% flags
            if random.random() < 0.80:
                # 80/20 split: CSV rows vs synthetic HF messages
                if random.random() < 0.80:
                    payload = _build_message_payload(csv_messages)
                else:
                    synth = await generate_synthetic_message()
                    if synth is None:
                        # Fallback to CSV if HF fails
                        payload = _build_message_payload(csv_messages)
                    else:
                        payload = synth

                pending_tasks.append(
                    asyncio.create_task(
                        _dispatch_and_count(
                            session, message_url, payload, "messages", counters
                        )
                    )
                )
            else:
                payload = _build_flag_payload()
                pending_tasks.append(
                    asyncio.create_task(
                        _dispatch_and_count(
                            session, flag_url, payload, "flags", counters
                        )
                    )
                )

            counters["total"] += 1

            if counters["total"] % 100 == 0:
                logger.info(
                    "Dispatched %d requests (messages=%d, flags=%d, errors=%d)",
                    counters["total"],
                    counters["messages"],
                    counters["flags"],
                    counters["errors"],
                )

            # Rate limiting
            elapsed = asyncio.get_event_loop().time() - dispatch_start
            sleep_time = interval - elapsed
            if sleep_time > 0:
                await asyncio.sleep(sleep_time)

        # Wait for all in-flight requests to complete before closing session
        if pending_tasks:
            await asyncio.gather(*pending_tasks, return_exceptions=True)

    logger.info(
        "Traffic generator finished: %d total (messages=%d, flags=%d, errors=%d)",
        counters["total"],
        counters["messages"],
        counters["flags"],
        counters["errors"],
    )
    return counters


async def _dispatch_and_count(
    session: aiohttp.ClientSession,
    url: str,
    payload: dict[str, Any],
    counter_key: str,
    counters: dict[str, int],
) -> None:
    """Dispatch a request and update counters.

    Args:
        session: aiohttp ClientSession.
        url: Target URL.
        payload: JSON payload.
        counter_key: Key in counters to increment on success.
        counters: Shared counter dict.
    """
    result = await send_message(session, url, payload)
    if result is not None:
        counters[counter_key] += 1
    else:
        counters["errors"] += 1


def main() -> None:
    """Parse CLI arguments and run the traffic generator."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    parser = argparse.ArgumentParser(
        description="Synthetic HTTP traffic generator for ChatSentry"
    )
    parser.add_argument(
        "--base-url",
        default="http://localhost:8000",
        help="Base URL of the FastAPI server (default: http://localhost:8000)",
    )
    parser.add_argument(
        "--duration",
        type=int,
        default=60,
        help="Duration in seconds (default: 60)",
    )
    parser.add_argument(
        "--rps",
        type=int,
        default=TARGET_RPS,
        help=f"Target requests per second (default: {TARGET_RPS})",
    )
    parser.add_argument(
        "--csv-path",
        default="combined_dataset.csv",
        help="Path to combined_dataset.csv (default: combined_dataset.csv)",
    )
    args = parser.parse_args()

    asyncio.run(
        run_traffic_generator(
            base_url=args.base_url,
            duration_seconds=args.duration,
            rps=args.rps,
            csv_path=args.csv_path,
        )
    )


if __name__ == "__main__":
    main()
