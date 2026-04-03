"""Shared reference and knowledge retrieval logic."""

import datetime
import json
import urllib.parse
from typing import Any

import requests
from googletrans import Translator

HEADERS = {"User-Agent": "SpaceCatBot/1.0 (https://github.com/your-repo-here)"}
HTTP_OK = 200


def currency(amount: float, base_currency: str, target_currency: str) -> dict[str, Any]:
    """
    Convert an amount from one currency to another.

    Args:
        amount: The amount of money to convert from.
        base_currency: The currency converting from.
        target_currency: The currency converting to.

    Returns:
        A dictionary containing the conversion result.
    """
    amount = float(amount)
    base, target = base_currency.upper(), target_currency.upper()

    try:
        # Get Current Rate from ER-API
        er_url = f"https://open.er-api.com/v6/latest/{base}"
        er_res = requests.get(er_url, timeout=10)
        er_data = er_res.json()

        if er_res.status_code != HTTP_OK or er_data.get("result") != "success":
            return {"success": False, "error": "Current rate service unavailable."}

        current_rate = er_data["rates"].get(target)
        if not current_rate:
            return {"success": False, "error": f"Target currency {target} not supported."}

        # Get 1-Year History from Frankfurter
        end_date = datetime.datetime.now(tz=datetime.UTC).date()
        start_date = end_date - datetime.timedelta(days=365)
        hist_url = (
            f"https://api.frankfurter.dev/v1/{start_date}..{end_date}?base={base}&symbols={target}"
        )

        hist_res = requests.get(hist_url, timeout=10)
        graph_url = None

        if hist_res.status_code == HTTP_OK:
            hist_data = hist_res.json().get("rates", {})
            sorted_dates = sorted(hist_data.keys())
            # Sample every 7th day to keep the URL length safe
            sparse_dates = sorted_dates[::7]
            values = [hist_data[date][target] for date in sparse_dates]

            # Generate QuickChart Config
            chart_config = {
                "type": "line",
                "data": {
                    "labels": [d.split("-")[1] for d in sparse_dates],  # Month numbers
                    "datasets": [
                        {
                            "label": f"{base}/{target} (1 Year)",
                            "data": values,
                            "fill": True,
                            "backgroundColor": "rgba(46, 204, 113, 0.1)",
                            "borderColor": "rgb(46, 204, 113)",
                            "borderWidth": 2,
                            "pointRadius": 0,
                        }
                    ],
                },
                "options": {"scales": {"yAxes": [{"ticks": {"beginAtZero": False}}]}},
            }
            encoded_config = urllib.parse.quote(json.dumps(chart_config))
            graph_url = (
                f"https://quickchart.io/chart?c={encoded_config}&width=500&height=250&bkg=white"
            )

        return {
            "success": True,
            "amount": amount,
            "base": base,
            "target": target,
            "result": round(amount * current_rate, 2),
            "rate": current_rate,
            "graph_url": graph_url,
        }
    except requests.RequestException:
        return {"success": False, "error": "Connection error."}


def define(word: str) -> dict[str, Any]:
    """
    Fetch the dictionary definition of a word.

    Args:
        word: The word to define.

    Returns:
        A dictionary containing the word, phonetic, and definition.
    """
    url = f"https://api.dictionaryapi.dev/api/v2/entries/en/{word}"
    try:
        response = requests.get(url, timeout=5)
        if response.status_code == HTTP_OK:
            data = response.json()[0]
            # Extract first definition
            meaning = data["meanings"][0]["definitions"][0]["definition"]
            return {
                "word": data["word"],
                "phonetic": data.get("phonetic", ""),
                "definition": meaning,
            }
    except requests.RequestException:
        return {"error": "Could not reach dictionary service."}
    else:
        return {"error": "Word not found."}


def thesaurus(word: str) -> dict[str, Any]:
    """
    Find synonyms and antonyms for a given word.

    Args:
        word: The word to look up.

    Returns:
        A dictionary containing the word and its synonyms and antonyms.
    """
    url = f"https://api.dictionaryapi.dev/api/v2/entries/en/{word}"
    try:
        response = requests.get(url, headers=HEADERS, timeout=5)
        if response.status_code == HTTP_OK:
            data = response.json()[0]
            synonyms = set()
            antonyms = set()

            for meaning in data.get("meanings", []):
                # 1. Grab synonyms/antonyms at the 'meaning' level
                for syn in meaning.get("synonyms", []):
                    synonyms.add(syn)
                for ant in meaning.get("antonyms", []):
                    antonyms.add(ant)

                # 2. Grab them from inside specific 'definitions'
                for definition in meaning.get("definitions", []):
                    for syn in definition.get("synonyms", []):
                        synonyms.add(syn)
                    for ant in definition.get("antonyms", []):
                        antonyms.add(ant)

            return {
                "word": word,
                "synonyms": list(synonyms)[:10],  # Top 10 unique
                "antonyms": list(antonyms)[:10],  # Top 10 unique
            }
    except requests.RequestException:
        return {"error": "Could not reach thesaurus service."}
    else:
        return {"error": "Word not found."}


async def translate(text: str, target_lang: str = "en") -> str:
    """
    Translate text to a target language.

    Args:
        text: The text to translate.
        target_lang: The target language code

    Returns:
        str: The translated text.
    """
    # Implementation depends on your preferred translation API
    # Example using a free MyMemory API
    try:
        async with Translator() as translator:
            result = await translator.translate(text, dest=target_lang)
            return result.text
    except (RuntimeError, ConnectionError, ValueError):
        return "Google Translate service is currently unavailable."


def wikipedia(query: str) -> dict[str, Any]:
    """
    Search Wikipedia and return a summary and URL.

    Returns:
        A dictionary containing the title, summary, and link.
    """
    # Using the Wikipedia REST API for clean summaries
    url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{query.replace(' ', '_')}"
    try:
        response = requests.get(url, headers=HEADERS, timeout=5)
        if response.status_code == HTTP_OK:
            data = response.json()
            return {
                "title": data.get("title"),
                "content": data.get("extract"),
                "url": data.get("content_urls", {}).get("desktop", {}).get("page"),
            }
    except requests.RequestException:
        return {"error": "Connection failed: Could not reach Wikipedia."}
    else:
        return {"error": "Page not found."}
