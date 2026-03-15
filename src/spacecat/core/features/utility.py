"""Shared utility command logic."""
import colorsys
import io
import time
from typing import TypedDict
import qrcode as qr_code
from PIL import Image
import simpleeval
from dateutil import parser


class EmbedField(TypedDict):
    """A field within a universal embed."""

    name: str
    value: str
    inline: bool


class UniversalEmbed(TypedDict):
    """Container to store universal embed data."""

    title: str
    fields: list[EmbedField]
    color: int


def avatar(avatar_url: str | None) -> str:
    """Display the user's avatar.

    Args:
        avatar_url: URL of the user's avatar.

    Returns:
        A string containing the avatar URL or a message indicating no
        avatar exists.
    """
    if avatar_url:
        return f"Avatar URL: {avatar_url}"
    return "This user does not have an avatar."


def calc(expression: str) -> str:
    """Core logic to calculate a math equation."""
    try:
        return str(simpleeval.simple_eval(expression))
    except Exception as e:
        return f"Could not calculate that. {e}"


def color(hex_code: str) -> tuple[io.BytesIO, dict[str, str]]:
    """Core logic to generate a color preview image buffer."""
    # Ensure the format is clean
    hex_code = hex_code.lstrip('#')

    # Convert HEX string to RGB tuple
    rgb = tuple(int(hex_code[i:i + 2], 16) for i in (0, 2, 4))

    # Calculate RGB, HSL, and CMYK
    r, g, b = [x / 255.0 for x in rgb]
    h, l, s = colorsys.rgb_to_hls(r, g, b)

    # CMYK Conversion
    k = 1 - max(r, g, b)
    c = (1 - r - k) / (1 - k) if k != 1 else 0
    m = (1 - g - k) / (1 - k) if k != 1 else 0
    y = (1 - b - k) / (1 - k) if k != 1 else 0

    # Create the square image (100x100 pixels)
    img = Image.new("RGB", (100, 100), color=rgb)

    # Save to memory buffer
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)

    return buffer, {
        "rgb": f"{rgb[0]}, {rgb[1]}, {rgb[2]}",
        "hsl": f"{round(h * 360)}°, {round(s * 100)}%, {round(l * 100)}%",
        "cmyk": f"{round(c * 100)}%, {round(m * 100)}%, {round(y * 100)}%, {round(k * 100)}%"
    }


def echo(message: str) -> str:
    """Repeat a message back.

    Args:
        message: The message to echo.

    Returns:
        The same message.
    """
    return message


async def ping(send_func, edit_func) -> str:
    """Return a ping response.

    Returns:
        A simple ping response string.
    """
    start_time = time.perf_counter()

    # 1. Use the injected 'send_func'
    msg = await send_func("Calculating latency...")

    end_time = time.perf_counter()
    latency_ms = round((end_time - start_time) * 1000)

    # 2. Use the injected 'edit_func'
    response = f"Pong! Bot latency is: {latency_ms}ms"
    await edit_func(msg, response)


def qrcode(data: str) -> io.BytesIO:
    """Core logic to generate a QR code image buffer."""
    qr = qr_code.QRCode(version=1, box_size=10, border=5)
    qr.add_data(data)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")

    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)
    return buffer


def timestamp(time: str) -> str:
    """Core logic to generate a timestamp."""
    try:
        # Parse the string into a datetime object
        dt = parser.parse(time)

        # Convert to a Unix timestamp
        unix_time = int(dt.timestamp())

        formats = [
            ("Short Time", f"<t:{unix_time}:t>"),
            ("Long Time", f"<t:{unix_time}:T>"),
            ("Short Date", f"<t:{unix_time}:d>"),
            ("Long Date", f"<t:{unix_time}:D>"),
            ("Short Date/Time", f"<t:{unix_time}:f>"),
            ("Long Date/Time", f"<t:{unix_time}:F>"),
            ("Relative Time", f"<t:{unix_time}:R>")
        ]

        # Respond with the formatted strings
        return "\n".join([f"**{name}:** `{code}` -> {code}" for name, code in formats])
    except Exception:
        return "Sorry, I couldn't understand that time format."


def uptime(start_timestamp: float) -> str:
    """Format bot uptime into a human-readable string.

    Args:
        start_timestamp: Unix timestamp when the bot started.

    Returns:
        Formatted uptime string or UptimeInfo object if return_raw is True.
    """
    # Calculate uptime in hours, minutes, and seconds.
    uptime_seconds = int(time.time() - start_timestamp)
    hours, remainder = divmod(uptime_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)

    # Build the uptime string.
    parts = []
    if hours > 0:
        parts.append(f"{hours} hour{'s' if hours != 1 else ''}")
    if minutes > 0:
        parts.append(f"{minutes} minute{'s' if minutes != 1 else ''}")
    if seconds > 0 or not parts:
        parts.append(f"{seconds} second{'s' if seconds != 1 else ''}")

    return f"Bot Uptime: {' '.join(parts)}."
