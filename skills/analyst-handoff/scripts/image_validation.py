"""Проверка локальных изображений без дополнительных зависимостей."""

from __future__ import annotations

import struct
import zlib
from pathlib import Path

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def local_image_error(path: Path) -> str | None:
    """Возвращает причину отказа или None. У PNG проверяется структура блоков."""
    if not path.is_file():
        return "нет файла картинки"
    try:
        data = path.read_bytes()
    except OSError as error:
        return f"не удалось прочитать картинку ({error})"
    if not data:
        return "пустой файл картинки"
    if path.suffix.lower() == ".png":
        return png_error(data)
    return None


def png_error(data: bytes) -> str | None:
    """Проверяет подпись PNG, размеры, границы и CRC блоков, наличие IDAT/IEND."""
    if not data.startswith(PNG_SIGNATURE):
        return "повреждён PNG: неверная подпись"
    offset = len(PNG_SIGNATURE)
    header_found = False
    image_data_found = False
    while offset < len(data):
        if len(data) - offset < 12:
            return "повреждён PNG: обрезан блок"
        length, kind = struct.unpack_from(">I4s", data, offset)
        end = offset + 12 + length
        if end > len(data):
            return "повреждён PNG: обрезаны данные блока"
        payload = data[offset + 8:end - 4]
        crc = struct.unpack_from(">I", data, end - 4)[0]
        if zlib.crc32(kind + payload) != crc:
            return "повреждён PNG: неверная CRC блока"
        if not header_found:
            if kind != b"IHDR" or length != 13:
                return "повреждён PNG: нет корректного заголовка IHDR"
            width, height = struct.unpack_from(">II", payload)
            if width == 0 or height == 0:
                return "повреждён PNG: нулевые размеры изображения"
            header_found = True
        elif kind == b"IHDR":
            return "повреждён PNG: повторный заголовок IHDR"
        if kind == b"IDAT" and length:
            image_data_found = True
        if kind == b"IEND":
            if length or end != len(data):
                return "повреждён PNG: некорректный завершающий блок IEND"
            if not image_data_found:
                return "повреждён PNG: нет данных изображения IDAT"
            return None
        offset = end
    return "повреждён PNG: нет завершающего блока IEND"
