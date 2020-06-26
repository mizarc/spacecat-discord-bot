def number_to_emoji(num: int):
    emoji = f"{num}\u20e3"
    return emoji


def emoji_to_number(emoji: str):
    number = int(emoji[0])
    return number
