"""Fluxer-specific utility functions."""

import re


def parse_quoted_args(input_text: str) -> list[str]:
    """Parse arguments from input, handling quoted strings.

    Args:
        input_text: The raw command input text.

    Returns:
        List of parsed arguments, with quoted strings as single
        arguments. (g.g. '30m' 'Start DnD session' -> ['30m',
        'Start DnD session'])
    """
    # Pattern to match quoted strings or non-quoted words
    pattern = r'"([^"]*)"|(\S+)'
    matches = re.findall(pattern, input_text)

    # Extract the actual matched content (quoted or unquoted)
    args = []
    for quoted, unquoted in matches:
        args.append(quoted or unquoted)

    return args
