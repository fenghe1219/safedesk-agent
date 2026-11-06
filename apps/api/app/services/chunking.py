import re
from dataclasses import dataclass


@dataclass(frozen=True)
class TextChunk:
    content: str
    page: int
    section: str
    offset_start: int
    offset_end: int
    ordinal: int


HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
MAX_CHUNK_CHARS = 700


def chunk_text(raw: str) -> list[TextChunk]:
    """Split Markdown/text while retaining exact source offsets and page hints."""
    pages = _split_pages(raw)
    chunks: list[TextChunk] = []
    ordinal = 0

    for page_number, page_text, page_offset in pages:
        blocks: list[tuple[str, str, int, int]] = []
        section = "正文"
        buffer: list[str] = []
        buffer_start: int | None = None
        buffer_end: int | None = None
        cursor = 0

        for line in page_text.splitlines(keepends=True):
            line_start = cursor
            line_end = cursor + len(line)
            cursor = line_end
            stripped = line.strip()

            heading = HEADING_RE.match(stripped)
            if heading:
                block = _make_block(buffer, section, buffer_start, buffer_end)
                if block is not None:
                    blocks.append(block)
                buffer, buffer_start, buffer_end = [], None, None
                section = heading.group(2).strip() or section
                continue
            if not stripped:
                block = _make_block(buffer, section, buffer_start, buffer_end)
                if block is not None:
                    blocks.append(block)
                buffer, buffer_start, buffer_end = [], None, None
                continue

            if buffer_start is None:
                buffer_start = line_start
            buffer.append(line.rstrip("\r\n"))
            buffer_end = line_end - len(line) + len(line.rstrip("\r\n"))

        block = _make_block(buffer, section, buffer_start, buffer_end)
        if block is not None:
            blocks.append(block)

        current: list[tuple[str, str, int, int]] = []
        current_length = 0
        for block in blocks:
            body, _block_section, _start, _end = block
            if current and current_length + len(body) + 2 > MAX_CHUNK_CHARS:
                chunks.append(
                    _make_chunk(current, page_text, page_number, page_offset, ordinal)
                )
                ordinal += 1
                current = []
                current_length = 0
            if len(body) > MAX_CHUNK_CHARS:
                if current:
                    chunks.append(
                        _make_chunk(current, page_text, page_number, page_offset, ordinal)
                    )
                    ordinal += 1
                    current = []
                    current_length = 0
                for piece in _split_long_block(block):
                    chunks.append(
                        _make_chunk([piece], page_text, page_number, page_offset, ordinal)
                    )
                    ordinal += 1
                continue
            current.append(block)
            current_length += len(body) + 2

        if current:
            chunks.append(_make_chunk(current, page_text, page_number, page_offset, ordinal))
            ordinal += 1

    return chunks


def _split_pages(raw: str) -> list[tuple[int, str, int]]:
    pages: list[tuple[int, str, int]] = []
    cursor = 0
    for index, part in enumerate(raw.split("\f"), start=1):
        pages.append((index, part, cursor))
        cursor += len(part) + 1
    return pages


def _make_chunk(
    blocks: list[tuple[str, str, int, int]],
    page_text: str,
    page: int,
    page_offset: int,
    ordinal: int,
) -> TextChunk:
    content = page_text[blocks[0][2] : blocks[-1][3]]
    section = next((item[1] for item in blocks if item[1]), "正文")
    start = page_offset + blocks[0][2]
    end = page_offset + blocks[-1][3]
    return TextChunk(
        content=content,
        page=page,
        section=section,
        offset_start=start,
        offset_end=end,
        ordinal=ordinal,
    )


def _make_block(
    buffer: list[str], section: str, start: int | None, end: int | None
) -> tuple[str, str, int, int] | None:
    if not buffer or start is None or end is None:
        return None
    joined = "\n".join(buffer)
    body = joined.strip()
    if not body:
        return None
    lead = len(joined) - len(joined.lstrip())
    return (body, section, start + lead, end)


def _split_long_block(
    block: tuple[str, str, int, int]
) -> list[tuple[str, str, int, int]]:
    body, section, start, end = block
    pieces: list[tuple[str, str, int, int]] = []
    cursor = 0
    while cursor < len(body):
        limit = min(cursor + MAX_CHUNK_CHARS, len(body))
        if limit < len(body):
            boundary = max(body.rfind("\n", cursor, limit), body.rfind("。", cursor, limit))
            if boundary > cursor + 200:
                limit = boundary + 1
        text = body[cursor:limit].strip()
        if text:
            lead = len(body[cursor:limit]) - len(body[cursor:limit].lstrip())
            piece_start = start + cursor + lead
            piece_end = start + cursor + len(body[cursor:limit].rstrip())
            pieces.append((text, section, piece_start, piece_end))
        cursor = max(limit, cursor + 1)
    return pieces
