"""
Minimal NBT binary writer for Minecraft structure files (.nbt).

Writes the Java Edition structure NBT format:
  Root compound → DataVersion, size[], palette[], blocks[], entities[]

Output is GZip-compressed as required by the game.
"""

import gzip
import io
import struct
from typing import Any

# NBT tag type IDs
TAG_END = 0
TAG_BYTE = 1
TAG_SHORT = 2
TAG_INT = 3
TAG_LONG = 4
TAG_FLOAT = 5
TAG_DOUBLE = 6
TAG_BYTE_ARRAY = 7
TAG_STRING = 8
TAG_LIST = 9
TAG_COMPOUND = 10
TAG_INT_ARRAY = 11
TAG_LONG_ARRAY = 12


class NBTWriter:
    """Writes raw NBT binary data to a bytes buffer."""

    def __init__(self):
        self._buf = io.BytesIO()

    def _write(self, data: bytes):
        self._buf.write(data)

    # ── Primitives ──

    def write_byte(self, val: int):
        self._write(struct.pack(">b", val))

    def write_short(self, val: int):
        self._write(struct.pack(">h", val))

    def write_int(self, val: int):
        self._write(struct.pack(">i", val))

    def write_long(self, val: int):
        self._write(struct.pack(">q", val))

    def write_float(self, val: float):
        self._write(struct.pack(">f", val))

    def write_string(self, val: str):
        encoded = val.encode("utf-8")
        self.write_short(len(encoded))
        self._write(encoded)

    # ── Named tag headers ──

    def write_tag_header(self, tag_type: int, name: str):
        self.write_byte(tag_type)
        self.write_string(name)

    # ── Compound tags ──

    def begin_compound(self, name: str = ""):
        self.write_tag_header(TAG_COMPOUND, name)

    def end_compound(self):
        self.write_byte(TAG_END)

    # ── Named value writers ──

    def write_named_byte(self, name: str, val: int):
        self.write_tag_header(TAG_BYTE, name)
        self.write_byte(val)

    def write_named_short(self, name: str, val: int):
        self.write_tag_header(TAG_SHORT, name)
        self.write_short(val)

    def write_named_int(self, name: str, val: int):
        self.write_tag_header(TAG_INT, name)
        self.write_int(val)

    def write_named_long(self, name: str, val: int):
        self.write_tag_header(TAG_LONG, name)
        self.write_long(val)

    def write_named_float(self, name: str, val: float):
        self.write_tag_header(TAG_FLOAT, name)
        self.write_float(val)

    def write_named_string(self, name: str, val: str):
        self.write_tag_header(TAG_STRING, name)
        self.write_string(val)

    # ── List of ints (used for size / pos) ──

    def write_named_int_list(self, name: str, values: list[int]):
        self.write_tag_header(TAG_LIST, name)
        self.write_byte(TAG_INT)      # element type
        self.write_int(len(values))   # length
        for v in values:
            self.write_int(v)

    def get_bytes(self) -> bytes:
        return self._buf.getvalue()


def write_structure_nbt(
    blocks: list[dict],
    palette: list[dict],
    size: tuple[int, int, int],
    data_version: int = 3953,
    output_path: str = "structure.nbt",
):
    """
    Write a Minecraft Java Edition .nbt structure file.

    Args:
        blocks: List of {"state": int, "pos": [x, y, z]} dicts.
                state = index into palette. air blocks can be omitted.
        palette: List of {"Name": "minecraft:stone", "Properties": {}} dicts.
        size: (x_size, y_size, z_size) tuple.
        data_version: Minecraft data version (3953 = 1.21.x).
        output_path: Where to write the .nbt file.
    """
    w = NBTWriter()

    # Root compound (empty name for root)
    w.begin_compound("")

    # DataVersion
    w.write_named_int("DataVersion", data_version)

    # size: List of 3 ints
    w.write_named_int_list("size", list(size))

    # palette: List of Compound tags
    w.write_tag_header(TAG_LIST, "palette")
    w.write_byte(TAG_COMPOUND)       # element type
    w.write_int(len(palette))        # count
    for entry in palette:
        # Each palette entry is a compound
        w.write_named_string("Name", entry["Name"])
        if entry.get("Properties"):
            w.write_tag_header(TAG_COMPOUND, "Properties")
            for prop_name, prop_val in entry["Properties"].items():
                w.write_named_string(prop_name, str(prop_val))
            w.end_compound()
        w.end_compound()  # end palette entry

    # blocks: List of Compound tags
    w.write_tag_header(TAG_LIST, "blocks")
    w.write_byte(TAG_COMPOUND)       # element type
    w.write_int(len(blocks))         # count
    for block in blocks:
        w.write_named_int("state", block["state"])
        w.write_named_int_list("pos", block["pos"])
        # nbt field for block entities (signs, etc.) — optional
        if "nbt" in block:
            w.write_tag_header(TAG_COMPOUND, "nbt")
            _write_nbt_compound_contents(w, block["nbt"])
            w.end_compound()
        w.end_compound()  # end block entry

    # entities: empty list
    w.write_tag_header(TAG_LIST, "entities")
    w.write_byte(TAG_COMPOUND)       # element type = compound
    w.write_int(0)                   # count = 0

    # Close root compound
    w.end_compound()

    # GZip compress and write to file
    raw = w.get_bytes()
    with gzip.open(output_path, "wb") as f:
        f.write(raw)

    return output_path


def _write_nbt_compound_contents(w: NBTWriter, data: dict):
    """Recursively write compound contents (key-value pairs) for block entity NBT."""
    for key, val in data.items():
        if isinstance(val, str):
            w.write_named_string(key, val)
        elif isinstance(val, bool):
            w.write_named_byte(key, 1 if val else 0)
        elif isinstance(val, int):
            w.write_named_int(key, val)
        elif isinstance(val, float):
            w.write_named_float(key, val)
        elif isinstance(val, dict):
            w.write_tag_header(TAG_COMPOUND, key)
            _write_nbt_compound_contents(w, val)
            w.end_compound()
        elif isinstance(val, list):
            if all(isinstance(v, int) for v in val):
                w.write_named_int_list(key, val)
            elif all(isinstance(v, str) for v in val):
                w.write_tag_header(TAG_LIST, key)
                w.write_byte(TAG_STRING)
                w.write_int(len(val))
                for s in val:
                    w.write_string(s)


class StructureBuilder:
    """
    High-level builder that accumulates block placements and writes .nbt.

    Usage:
        sb = StructureBuilder(width=10, height=8, depth=6)
        sb.set_block(0, 0, 0, "minecraft:stone")
        sb.set_block(1, 0, 0, "minecraft:bricks")
        sb.save("my_structure.nbt")
    """

    def __init__(self, width: int, height: int, depth: int):
        self.width = width    # X
        self.height = height  # Y
        self.depth = depth    # Z
        # 3D grid: None = air (omitted from .nbt)
        self._grid: list[list[list[str | None]]] = [
            [[None for _ in range(depth)]
             for _ in range(height)]
            for _ in range(width)
        ]

    def set_block(self, x: int, y: int, z: int, block_id: str,
                  properties: dict | None = None,
                  nbt: dict | None = None):
        """Place a block at (x, y, z). block_id like 'minecraft:stone'."""
        if 0 <= x < self.width and 0 <= y < self.height and 0 <= z < self.depth:
            key = block_id
            if properties:
                key = f"{block_id}|{repr(sorted(properties.items()))}"
            self._grid[x][y][z] = block_id
            # Store properties/nbt separately if needed
            if not hasattr(self, "_props"):
                self._props = {}
                self._nbt = {}
            if properties:
                self._props[(x, y, z)] = properties
            if nbt:
                self._nbt[(x, y, z)] = nbt

    def fill(self, x1: int, y1: int, z1: int,
             x2: int, y2: int, z2: int, block_id: str):
        """Fill a rectangular region with a block."""
        for x in range(min(x1, x2), max(x1, x2) + 1):
            for y in range(min(y1, y2), max(y1, y2) + 1):
                for z in range(min(z1, z2), max(z1, z2) + 1):
                    self.set_block(x, y, z, block_id)

    def fill_hollow(self, x1: int, y1: int, z1: int,
                    x2: int, y2: int, z2: int, block_id: str):
        """Fill only the shell (walls, floor, ceiling) of a box."""
        for x in range(x1, x2 + 1):
            for y in range(y1, y2 + 1):
                for z in range(z1, z2 + 1):
                    is_edge = (x in (x1, x2) or y in (y1, y2) or
                               z in (z1, z2))
                    if is_edge:
                        self.set_block(x, y, z, block_id)

    def save(self, output_path: str, data_version: int = 3953) -> str:
        """Export the structure as a .nbt file."""
        # Build palette and block list
        palette_map: dict[str, int] = {}
        palette_list: list[dict] = []
        block_list: list[dict] = []

        if not hasattr(self, "_props"):
            self._props = {}
            self._nbt = {}

        for x in range(self.width):
            for y in range(self.height):
                for z in range(self.depth):
                    bid = self._grid[x][y][z]
                    if bid is None:
                        continue

                    props = self._props.get((x, y, z), {})
                    palette_key = bid + (repr(sorted(props.items()))
                                         if props else "")

                    if palette_key not in palette_map:
                        idx = len(palette_list)
                        palette_map[palette_key] = idx
                        entry = {"Name": bid}
                        if props:
                            entry["Properties"] = {
                                k: str(v) for k, v in props.items()
                            }
                        palette_list.append(entry)

                    block_entry = {
                        "state": palette_map[palette_key],
                        "pos": [x, y, z],
                    }
                    nbt_data = self._nbt.get((x, y, z))
                    if nbt_data:
                        block_entry["nbt"] = nbt_data

                    block_list.append(block_entry)

        return write_structure_nbt(
            blocks=block_list,
            palette=palette_list,
            size=(self.width, self.height, self.depth),
            data_version=data_version,
            output_path=output_path,
        )
