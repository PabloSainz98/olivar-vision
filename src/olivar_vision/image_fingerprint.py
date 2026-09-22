"""Decode images safely enough to validate them and compute a stable dHash."""

import binascii
import re
import shutil
import struct
import subprocess
import tempfile
import zlib
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Sequence, Tuple


class ImageDecodeError(ValueError):
    """Raised when an image cannot be decoded completely."""


@dataclass(frozen=True)
class DecodedImage:
    image_format: str
    width: int
    height: int
    orientation: Optional[int]
    orientation_verified: bool
    decoder: str
    luma: Tuple[int, ...]
    luma_width: int
    luma_height: int


def decode_image(path: Path) -> DecodedImage:
    """Decode an image without modifying it.

    PNG, BMP and Netpbm fixtures use the standard library. Other formats use
    macOS sips, which is available on the project's target development host.
    """

    data = path.read_bytes()
    if not data:
        raise ImageDecodeError("empty file")
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return _decode_png(data)
    if data.startswith(b"BM"):
        return _decode_bmp(data)
    if data.startswith((b"P2", b"P3", b"P5", b"P6")):
        return _decode_pnm(data)
    return _decode_with_sips(path)


def dhash64(image: DecodedImage) -> str:
    """Return a 64-bit horizontal difference hash over a 9x8 luma sample."""

    sampled = _nearest_resize(
        image.luma,
        image.luma_width,
        image.luma_height,
        target_width=9,
        target_height=8,
    )
    value = 0
    for y in range(8):
        for x in range(8):
            value <<= 1
            if sampled[y * 9 + x] > sampled[y * 9 + x + 1]:
                value |= 1
    return f"{value:016x}"


def hamming_distance(left: str, right: str) -> int:
    return bin(int(left, 16) ^ int(right, 16)).count("1")


def _decode_png(data: bytes) -> DecodedImage:
    offset = 8
    ihdr = None
    idat = bytearray()
    has_exif = False
    seen_iend = False

    while offset < len(data):
        if offset + 12 > len(data):
            raise ImageDecodeError("truncated PNG chunk")
        length = struct.unpack(">I", data[offset : offset + 4])[0]
        chunk_type = data[offset + 4 : offset + 8]
        end = offset + 12 + length
        if end > len(data):
            raise ImageDecodeError("truncated PNG payload")
        payload = data[offset + 8 : offset + 8 + length]
        expected_crc = struct.unpack(">I", data[offset + 8 + length : end])[0]
        actual_crc = binascii.crc32(chunk_type + payload) & 0xFFFFFFFF
        if actual_crc != expected_crc:
            raise ImageDecodeError("PNG CRC mismatch")
        if chunk_type == b"IHDR":
            ihdr = payload
        elif chunk_type == b"IDAT":
            idat.extend(payload)
        elif chunk_type == b"eXIf":
            has_exif = True
        elif chunk_type == b"IEND":
            seen_iend = True
            offset = end
            break
        offset = end

    if ihdr is None or len(ihdr) != 13 or not idat or not seen_iend:
        raise ImageDecodeError("PNG lacks IHDR, IDAT or IEND")
    width, height, bit_depth, color_type, compression, filtering, interlace = struct.unpack(
        ">IIBBBBB", ihdr
    )
    if width <= 0 or height <= 0:
        raise ImageDecodeError("PNG has invalid dimensions")
    if bit_depth != 8 or color_type not in {0, 2, 4, 6}:
        raise ImageDecodeError("PNG decoder supports 8-bit grayscale/RGB only")
    if compression != 0 or filtering != 0 or interlace != 0:
        raise ImageDecodeError("PNG compression/filter/interlace method is unsupported")

    channels = {0: 1, 2: 3, 4: 2, 6: 4}[color_type]
    stride = width * channels
    try:
        raw = zlib.decompress(bytes(idat))
    except zlib.error as exc:
        raise ImageDecodeError(f"PNG decompression failed: {exc}") from exc
    expected_length = height * (stride + 1)
    if len(raw) != expected_length:
        raise ImageDecodeError("PNG decompressed size is inconsistent")

    rows: List[bytearray] = []
    position = 0
    previous = bytearray(stride)
    for _ in range(height):
        filter_type = raw[position]
        position += 1
        encoded = raw[position : position + stride]
        position += stride
        row = _unfilter_png_row(filter_type, encoded, previous, channels)
        rows.append(row)
        previous = row

    luma: List[int] = []
    for row in rows:
        for x in range(width):
            base = x * channels
            if color_type in {0, 4}:
                luma.append(row[base])
            else:
                luma.append(_rgb_to_luma(row[base], row[base + 1], row[base + 2]))

    return DecodedImage(
        image_format="PNG",
        width=width,
        height=height,
        orientation=None if has_exif else 1,
        orientation_verified=not has_exif,
        decoder="python-stdlib-png-v1",
        luma=tuple(luma),
        luma_width=width,
        luma_height=height,
    )


def _unfilter_png_row(
    filter_type: int,
    encoded: Sequence[int],
    previous: Sequence[int],
    bytes_per_pixel: int,
) -> bytearray:
    row = bytearray(len(encoded))
    for index, value in enumerate(encoded):
        left = row[index - bytes_per_pixel] if index >= bytes_per_pixel else 0
        above = previous[index]
        upper_left = previous[index - bytes_per_pixel] if index >= bytes_per_pixel else 0
        if filter_type == 0:
            predictor = 0
        elif filter_type == 1:
            predictor = left
        elif filter_type == 2:
            predictor = above
        elif filter_type == 3:
            predictor = (left + above) // 2
        elif filter_type == 4:
            predictor = _paeth(left, above, upper_left)
        else:
            raise ImageDecodeError(f"unsupported PNG filter type: {filter_type}")
        row[index] = (value + predictor) & 0xFF
    return row


def _paeth(left: int, above: int, upper_left: int) -> int:
    estimate = left + above - upper_left
    distances = (
        (abs(estimate - left), left),
        (abs(estimate - above), above),
        (abs(estimate - upper_left), upper_left),
    )
    return min(distances, key=lambda item: item[0])[1]


def _decode_bmp(data: bytes) -> DecodedImage:
    if len(data) < 54:
        raise ImageDecodeError("truncated BMP header")
    pixel_offset = struct.unpack_from("<I", data, 10)[0]
    dib_size = struct.unpack_from("<I", data, 14)[0]
    if dib_size < 40:
        raise ImageDecodeError("unsupported BMP DIB header")
    width = struct.unpack_from("<i", data, 18)[0]
    raw_height = struct.unpack_from("<i", data, 22)[0]
    planes, bits_per_pixel = struct.unpack_from("<HH", data, 26)
    compression = struct.unpack_from("<I", data, 30)[0]
    if width <= 0 or raw_height == 0 or planes != 1:
        raise ImageDecodeError("BMP has invalid dimensions or planes")
    if bits_per_pixel not in {24, 32} or compression != 0:
        raise ImageDecodeError("BMP decoder supports uncompressed 24/32-bit images only")

    height = abs(raw_height)
    bytes_per_pixel = bits_per_pixel // 8
    row_stride = ((width * bits_per_pixel + 31) // 32) * 4
    required = pixel_offset + row_stride * height
    if required > len(data):
        raise ImageDecodeError("truncated BMP pixels")

    rows: List[List[int]] = []
    for stored_row in range(height):
        start = pixel_offset + stored_row * row_stride
        row: List[int] = []
        for x in range(width):
            base = start + x * bytes_per_pixel
            blue, green, red = data[base : base + 3]
            row.append(_rgb_to_luma(red, green, blue))
        rows.append(row)
    if raw_height > 0:
        rows.reverse()

    return DecodedImage(
        image_format="BMP",
        width=width,
        height=height,
        orientation=1,
        orientation_verified=True,
        decoder="python-stdlib-bmp-v1",
        luma=tuple(value for row in rows for value in row),
        luma_width=width,
        luma_height=height,
    )


def _decode_pnm(data: bytes) -> DecodedImage:
    tokens, pixel_start = _pnm_header_tokens(data, 4)
    magic = tokens[0]
    try:
        width, height, maximum = (int(value) for value in tokens[1:4])
    except ValueError as exc:
        raise ImageDecodeError("invalid Netpbm header") from exc
    if width <= 0 or height <= 0 or maximum <= 0 or maximum > 255:
        raise ImageDecodeError("unsupported Netpbm dimensions or max value")
    channels = 3 if magic in {b"P3", b"P6"} else 1
    sample_count = width * height * channels

    if magic in {b"P2", b"P3"}:
        samples = _pnm_ascii_samples(data[pixel_start:])
    else:
        samples = list(data[pixel_start : pixel_start + sample_count])
        if len(data[pixel_start:]) != sample_count:
            raise ImageDecodeError("Netpbm pixel count is inconsistent")
    if len(samples) != sample_count or any(value < 0 or value > maximum for value in samples):
        raise ImageDecodeError("Netpbm pixel count or value is invalid")
    scaled = [(value * 255 + maximum // 2) // maximum for value in samples]

    luma: List[int] = []
    for index in range(width * height):
        base = index * channels
        if channels == 1:
            luma.append(scaled[base])
        else:
            luma.append(_rgb_to_luma(*scaled[base : base + 3]))
    return DecodedImage(
        image_format="PPM" if channels == 3 else "PGM",
        width=width,
        height=height,
        orientation=1,
        orientation_verified=True,
        decoder="python-stdlib-netpbm-v1",
        luma=tuple(luma),
        luma_width=width,
        luma_height=height,
    )


def _pnm_header_tokens(data: bytes, count: int) -> Tuple[List[bytes], int]:
    tokens: List[bytes] = []
    index = 0
    while len(tokens) < count:
        while index < len(data) and chr(data[index]).isspace():
            index += 1
        if index < len(data) and data[index] == ord("#"):
            while index < len(data) and data[index] not in {10, 13}:
                index += 1
            continue
        start = index
        while index < len(data) and not chr(data[index]).isspace() and data[index] != ord("#"):
            index += 1
        if start == index:
            raise ImageDecodeError("truncated Netpbm header")
        tokens.append(data[start:index])
    if index >= len(data) or not chr(data[index]).isspace():
        raise ImageDecodeError("Netpbm header lacks pixel delimiter")
    if data[index : index + 2] == b"\r\n":
        index += 2
    else:
        index += 1
    return tokens, index


def _pnm_ascii_samples(data: bytes) -> List[int]:
    without_comments = re.sub(rb"#[^\r\n]*", b" ", data)
    try:
        return [int(token) for token in without_comments.split()]
    except ValueError as exc:
        raise ImageDecodeError("invalid Netpbm ASCII sample") from exc


def _decode_with_sips(path: Path) -> DecodedImage:
    sips = shutil.which("sips")
    if sips is None:
        raise ImageDecodeError("no decoder available for this image format; macOS sips is missing")
    metadata = subprocess.run(
        [sips, "-g", "pixelWidth", "-g", "pixelHeight", "-g", "format", "-g", "orientation", str(path)],
        check=False,
        capture_output=True,
        text=True,
    )
    if metadata.returncode != 0:
        detail = (metadata.stderr or metadata.stdout).strip().splitlines()
        raise ImageDecodeError(detail[-1] if detail else "sips could not decode image")
    values = {}
    for line in metadata.stdout.splitlines():
        match = re.match(r"\s*([A-Za-z]+):\s*(.+?)\s*$", line)
        if match:
            values[match.group(1)] = match.group(2)
    try:
        width = int(values["pixelWidth"])
        height = int(values["pixelHeight"])
    except (KeyError, ValueError) as exc:
        raise ImageDecodeError("sips did not report valid dimensions") from exc
    image_format = values.get("format", "unknown").upper()
    orientation_value = values.get("orientation")
    try:
        orientation = int(orientation_value) if orientation_value not in {None, "<nil>"} else None
    except ValueError:
        orientation = None

    with tempfile.TemporaryDirectory(prefix="olivar-vision-sips-") as temp_dir:
        output = Path(temp_dir) / "sample.bmp"
        converted = subprocess.run(
            [
                sips,
                "-s",
                "format",
                "bmp",
                "--resampleHeightWidth",
                "8",
                "9",
                str(path),
                "--out",
                str(output),
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        if converted.returncode != 0 or not output.exists():
            detail = (converted.stderr or converted.stdout).strip().splitlines()
            raise ImageDecodeError(detail[-1] if detail else "sips conversion failed")
        sample = _decode_bmp(output.read_bytes())

    return DecodedImage(
        image_format=image_format,
        width=width,
        height=height,
        orientation=orientation,
        orientation_verified=orientation is not None,
        decoder="macos-sips-v1",
        luma=sample.luma,
        luma_width=sample.luma_width,
        luma_height=sample.luma_height,
    )


def _nearest_resize(
    values: Sequence[int],
    width: int,
    height: int,
    target_width: int,
    target_height: int,
) -> List[int]:
    resized = []
    for y in range(target_height):
        source_y = min(height - 1, (y * height) // target_height)
        for x in range(target_width):
            source_x = min(width - 1, (x * width) // target_width)
            resized.append(values[source_y * width + source_x])
    return resized


def _rgb_to_luma(red: int, green: int, blue: int) -> int:
    return (299 * red + 587 * green + 114 * blue + 500) // 1000
