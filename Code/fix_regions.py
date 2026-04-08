"""
Fix Arnis region files for Paper 1.21 compatibility.

Arnis writes chunks in pre-1.18 format:
  Root -> Level -> {sections, xPos, zPos, ...}
  No DataVersion per chunk

Paper 1.21 expects:
  Root -> {DataVersion, sections, xPos, zPos, ...}
  DataVersion required

This script:
1. Reads each chunk from .mca files
2. Unwraps the Level compound (moves contents to root)
3. Adds DataVersion = 4189 (1.21.4)
4. Rewrites the region file
"""
import struct, zlib, io, os, sys, glob, time

# Minimal NBT reader/writer for chunk patching
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

def read_tag_name(data, pos):
    """Read tag type and name, return (tag_type, name, new_pos)"""
    tag_type = data[pos]
    pos += 1
    if tag_type == TAG_END:
        return TAG_END, "", pos
    name_len = struct.unpack_from('>H', data, pos)[0]
    pos += 2
    name = data[pos:pos+name_len].decode('utf-8')
    pos += name_len
    return tag_type, name, pos

def skip_payload(data, pos, tag_type):
    """Skip over a tag's payload, return new position"""
    if tag_type == TAG_BYTE:
        return pos + 1
    elif tag_type == TAG_SHORT:
        return pos + 2
    elif tag_type == TAG_INT:
        return pos + 4
    elif tag_type == TAG_LONG:
        return pos + 8
    elif tag_type == TAG_FLOAT:
        return pos + 4
    elif tag_type == TAG_DOUBLE:
        return pos + 8
    elif tag_type == TAG_BYTE_ARRAY:
        length = struct.unpack_from('>i', data, pos)[0]
        return pos + 4 + length
    elif tag_type == TAG_STRING:
        length = struct.unpack_from('>H', data, pos)[0]
        return pos + 2 + length
    elif tag_type == TAG_LIST:
        list_type = data[pos]
        pos += 1
        count = struct.unpack_from('>i', data, pos)[0]
        pos += 4
        for _ in range(count):
            pos = skip_payload(data, pos, list_type)
        return pos
    elif tag_type == TAG_COMPOUND:
        while True:
            inner_type = data[pos]
            if inner_type == TAG_END:
                return pos + 1
            pos += 1
            name_len = struct.unpack_from('>H', data, pos)[0]
            pos += 2 + name_len
            pos = skip_payload(data, pos, inner_type)
    elif tag_type == TAG_INT_ARRAY:
        length = struct.unpack_from('>i', data, pos)[0]
        return pos + 4 + length * 4
    elif tag_type == TAG_LONG_ARRAY:
        length = struct.unpack_from('>i', data, pos)[0]
        return pos + 4 + length * 8
    else:
        raise ValueError(f"Unknown tag type {tag_type} at pos {pos}")

def patch_chunk(data):
    """
    Transform chunk from old format to new format.
    Old: TAG_Compound("") -> TAG_Compound("Level") -> {children...}
    New: TAG_Compound("") -> {DataVersion: 4189, children...}
    """
    # Verify root is a compound with empty name
    if data[0] != TAG_COMPOUND:
        return data  # Not a compound, skip
    
    pos = 1
    # Read root name (should be empty)
    root_name_len = struct.unpack_from('>H', data, pos)[0]
    pos += 2
    pos += root_name_len  # skip root name
    
    # Now we're inside the root compound
    # Look for "Level" compound and collect non-Level children
    level_start = None
    level_end = None
    level_content = None
    other_children = bytearray()
    has_data_version = False
    
    scan_pos = pos
    while True:
        if scan_pos >= len(data):
            break
        tag_type = data[scan_pos]
        if tag_type == TAG_END:
            break
        
        tag_start = scan_pos
        tag_type_val, tag_name, after_name = read_tag_name(data, scan_pos)
        payload_end = skip_payload(data, after_name, tag_type_val)
        
        if tag_name == "Level" and tag_type_val == TAG_COMPOUND:
            level_start = after_name
            level_end = payload_end
            # Extract Level's inner children (everything between after_name and the TAG_END)
            level_content = data[after_name:payload_end - 1]  # -1 to exclude the TAG_END
        elif tag_name == "DataVersion":
            has_data_version = True
            other_children.extend(data[tag_start:payload_end])
        else:
            other_children.extend(data[tag_start:payload_end])
        
        scan_pos = payload_end
    
    if level_content is None:
        # No Level tag found - might already be new format, just add DataVersion + Status if missing
        if not has_data_version:
            # Insert DataVersion + Status right after root compound header
            result = bytearray()
            result.append(TAG_COMPOUND)  # root type
            result.extend(struct.pack('>H', root_name_len))
            result.extend(data[3:3+root_name_len])  # root name
            # Add DataVersion
            result.append(TAG_INT)
            result.extend(struct.pack('>H', 11))
            result.extend(b'DataVersion')
            result.extend(struct.pack('>i', 4189))
            # Add Status
            status_val = b'minecraft:full'
            result.append(TAG_STRING)
            result.extend(struct.pack('>H', 6))
            result.extend(b'Status')
            result.extend(struct.pack('>H', len(status_val)))
            result.extend(status_val)
            # Rest of original content
            result.extend(data[pos:])
            return bytes(result)
        return data
    
    # Build new chunk: root compound with DataVersion + Status + Level's children
    result = bytearray()
    result.append(TAG_COMPOUND)  # root type
    result.extend(struct.pack('>H', 0))  # empty root name
    
    # Add DataVersion: 4189
    if not has_data_version:
        result.append(TAG_INT)
        result.extend(struct.pack('>H', 11))
        result.extend(b'DataVersion')
        result.extend(struct.pack('>i', 4189))
    
    # Add Status: "minecraft:full" so Paper treats chunk as complete
    status_val = b'minecraft:full'
    result.append(TAG_STRING)
    result.extend(struct.pack('>H', 6))
    result.extend(b'Status')
    result.extend(struct.pack('>H', len(status_val)))
    result.extend(status_val)
    
    # Add Level's inner children (unwrapped)
    result.extend(level_content)
    
    # Add any other root-level children (non-Level)
    result.extend(other_children)
    
    # Close root compound
    result.append(TAG_END)
    
    return bytes(result)


def fix_region_file(path):
    """Fix all chunks in a region file"""
    with open(path, 'rb') as f:
        header = f.read(8192)  # locations + timestamps
        file_data = f.read()
    
    locations = header[:4096]
    timestamps = header[4096:8192]
    
    # Collect all chunks
    chunks = {}  # (offset, size) -> (chunk_x_in_region, chunk_z_in_region, compressed_data)
    patched = 0
    
    for i in range(1024):
        offset_bytes = locations[i*4:i*4+3]
        sector_count = locations[i*4+3]
        offset = int.from_bytes(offset_bytes, 'big')
        
        if offset == 0 and sector_count == 0:
            continue
        
        # Read chunk from file
        file_offset = offset * 4096 - 8192  # subtract header
        if file_offset < 0 or file_offset >= len(file_data):
            continue
            
        length = struct.unpack_from('>I', file_data, file_offset)[0]
        compression = file_data[file_offset + 4]
        compressed = file_data[file_offset + 5:file_offset + 4 + length]
        
        if compression == 2:
            raw = zlib.decompress(compressed)
        else:
            continue  # skip unknown compression
        
        # Patch the chunk
        patched_raw = patch_chunk(raw)
        patched_compressed = zlib.compress(patched_raw)
        
        chunks[i] = (patched_compressed, compression)
        patched += 1
    
    # Rebuild region file
    # Calculate sector layout
    new_file = bytearray(8192)  # header space
    current_sector = 2  # first 2 sectors are header
    
    new_locations = bytearray(4096)
    
    for i in range(1024):
        if i not in chunks:
            continue
        
        compressed_data, comp_type = chunks[i]
        chunk_header = struct.pack('>I', len(compressed_data) + 1) + bytes([comp_type])
        chunk_bytes = chunk_header + compressed_data
        
        # Pad to 4096-byte sectors
        sectors_needed = (len(chunk_bytes) + 4095) // 4096
        padded = chunk_bytes + b'\x00' * (sectors_needed * 4096 - len(chunk_bytes))
        
        # Record location
        offset_bytes = current_sector.to_bytes(3, 'big')
        new_locations[i*4:i*4+3] = offset_bytes
        new_locations[i*4+3] = sectors_needed
        
        new_file.extend(padded)
        current_sector += sectors_needed
    
    # Write header
    new_file[0:4096] = new_locations
    new_file[4096:8192] = timestamps
    
    with open(path, 'wb') as f:
        f.write(new_file)
    
    return patched


def main():
    region_dir = sys.argv[1] if len(sys.argv) > 1 else r'server\BuildDavis\region'
    files = glob.glob(os.path.join(region_dir, 'r.*.mca'))
    
    print(f"Found {len(files)} region files to patch")
    total = 0
    
    for f in sorted(files):
        name = os.path.basename(f)
        count = fix_region_file(f)
        total += count
        print(f"  {name}: patched {count} chunks")
    
    print(f"\nDone! Patched {total} chunks across {len(files)} files")

if __name__ == '__main__':
    main()
