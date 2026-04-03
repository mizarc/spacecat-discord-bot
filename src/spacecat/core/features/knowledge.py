"""Shared reference and knowledge retrieval logic."""

import asyncio
from typing import Any

import requests
from googletrans import Translator

HEADERS = {"User-Agent": "SpaceCatBot/1.0 (https://github.com/your-repo-here)"}


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
        if response.status_code == 200:
            data = response.json()
            return {
                "title": data.get("title"),
                "content": data.get("extract"),
                "url": data.get("content_urls", {}).get("desktop", {}).get("page"),
            }
        return {"error": "Page not found."}
    except Exception as e:
        return {"error": f"Connection failed: {str(e)}"}


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
        if response.status_code == 200:
            data = response.json()[0]
            # Extract first definition
            meaning = data["meanings"][0]["definitions"][0]["definition"]
            return {
                "word": data["word"],
                "phonetic": data.get("phonetic", ""),
                "definition": meaning,
            }
        return {"error": "Word not found."}
    except Exception:
        return {"error": "Could not reach dictionary service."}


def thesaurus(word: str) -> dict[str, Any]:
    """
    Find synonyms and antonyms for a given word.
    """
    url = f"https://api.dictionaryapi.dev/api/v2/entries/en/{word}"
    try:
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
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
        return {"error": "Word not found."}
    except Exception:
        return {"error": "Could not reach thesaurus service."}


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
        # Using the async context manager as per the library documentation
        async with Translator() as translator:
            result = await translator.translate(text, dest=target_lang)
            return result.text
    except Exception as e:
        # Logging the error here is helpful for debugging
        print(f"Translation Error: {e}")
        return "Google Translate service is currently unavailable."
