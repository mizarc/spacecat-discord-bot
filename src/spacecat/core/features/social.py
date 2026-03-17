"""Shared fun command logic."""

import io
import os
import random
from typing import Union, List, Tuple

from PIL import Image, ImageDraw, ImageSequence, ImageOps


def coinflip() -> str:
    """Flip a coin and return the result.

    Returns:
        The word 'Heads' or 'Tails' depending on the random result.
    """
    return "Heads" if random.randint(0, 1) else "Tails"


def diceroll(sides: int = 6) -> str:
    """Roll a die and return the result.

    Args:
        sides: Number of sides on the dice. Defaults to 6.

    Returns:
        A formatted message with the roll result.
    """
    result = random.randint(1, sides)
    return f"You rolled a {result}!"


def slap(profile_image: Union[Image.Image, bytes], frames: int = 60) -> bytes:
    """Create a slap animation by interposing a profile picture into a preset GIF.

    The function loads a preset slap GIF template and replaces the face area in each frame
    with the user's profile picture using manually defined tracking points.

    Args:
        profile_image: The user's profile picture as PIL Image or bytes.
        frames: Number of frames to process from the template GIF. Defaults to 30.

    Returns:
        The modified animated GIF as bytes.
    """
    # Convert bytes to PIL Image if needed
    if isinstance(profile_image, bytes):
        profile_image = Image.open(io.BytesIO(profile_image))

    # Ensure image is in RGBA mode
    if profile_image.mode != 'RGBA':
        profile_image = profile_image.convert('RGBA')
    profile_image = _crop_to_circle(profile_image)

    # Get the path to the template GIF
    current_dir = os.path.dirname(os.path.abspath(__file__))
    template_path = os.path.join(current_dir, '../..', 'assets', 'slap.gif')

    template_gif = Image.open(template_path)
    target_size = (60, 60)
    profile_image = profile_image.resize(target_size, Image.Resampling.LANCZOS)

    modified_frames = []

    # Use ImageSequence to safely iterate over frames
    # This automatically handles some of the seek complexity
    for i, frame in enumerate(ImageSequence.Iterator(template_gif)):
        if i >= frames:
            break

        # Ensure we are working with an RGBA canvas for each frame
        # We need a fresh copy to composite onto
        current_frame = frame.convert('RGBA')

        # Get your tracking point for this frame
        tracking_points = _get_manual_tracking_points(template_gif.n_frames)
        if i < len(tracking_points):
            x, y = tracking_points[i]
            paste_x = x - target_size[0] // 2
            paste_y = y - target_size[1] // 2

            # Use the profile_image as the mask to preserve transparency
            current_frame.paste(profile_image, (paste_x, paste_y), profile_image)

        # Convert back to P mode (palette) for better GIF saving if needed
        # Or keep as RGBA if your requirements allow
        modified_frames.append(current_frame.convert('RGB').convert('P', palette=Image.ADAPTIVE))

    # Save logic
    gif_bytes = io.BytesIO()
    modified_frames[0].save(
        gif_bytes,
        format='GIF',
        save_all=True,
        append_images=modified_frames[1:],
        duration=template_gif.info.get('duration', 100),
        loop=0
    )
    return gif_bytes.getvalue()


def _get_manual_tracking_points(num_frames: int) -> List[Tuple[int, int]]:
    # Define your "Control Points" (frame_index, x, y)
    # The animation will smoothly move from one point to the next
    keyframes = [
        (0, 20, 140),
        (10, 30, 150),
        (25, 35, 150),
        (32, 44, 141),
        (40, 40, 150),
        (50, 38, 160),
        (60, 37, 164)
    ]

    points = []

    for i in range(num_frames):
        # 1. Find the segment: the two keyframes surrounding the current frame i
        start_kf = next(kf for kf in reversed(keyframes) if kf[0] <= i)
        end_kf = next(kf for kf in keyframes if kf[0] >= i)

        # 2. If we are exactly on a keyframe, or past the last one, just use the endpoint
        if start_kf == end_kf:
            points.append((start_kf[1], start_kf[2]))
            continue

        # 3. Calculate progress (0.0 to 1.0) within this specific segment
        segment_len = end_kf[0] - start_kf[0]
        progress = (i - start_kf[0]) / segment_len

        # 4. Interpolate (lerp)
        x = start_kf[1] + (end_kf[1] - start_kf[1]) * progress
        y = start_kf[2] + (end_kf[2] - start_kf[2]) * progress

        points.append((int(x), int(y)))

    return points


def _crop_to_circle(profile_image: Image.Image) -> Image.Image:
    # 1. Ensure image is square for a perfect circle
    size = min(profile_image.size)
    profile_image = ImageOps.fit(profile_image, (size, size), centering=(0.5, 0.5))

    # 2. Create a mask: a transparent image with a white circle in the center
    mask = Image.new('L', (size, size), 0)
    draw = ImageDraw.Draw(mask)
    draw.ellipse((0, 0, size, size), fill=255)

    # 3. Apply the mask to the image
    output = profile_image.copy()
    output.putalpha(mask)

    return output
