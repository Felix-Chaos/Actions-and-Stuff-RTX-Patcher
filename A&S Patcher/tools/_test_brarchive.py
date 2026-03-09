import struct
import os
import sys

def extract_brarchive(br_path, dest_dir):
    with open(br_path, 'rb') as f:
        # Read header (16 bytes)
        magic = f.read(8)
        # 7d2725b1a0527026 is the documented magic, but let's check it
        print(f"Magic: {magic.hex()}")
        
        num_entries, version = struct.unpack('<II', f.read(8))
        print(f"Entries: {num_entries}, Version: {version}")
        
        # Read entries
        entries = []
        for _ in range(num_entries):
            entry_data = f.read(256)
            name_len = entry_data[0]
            name = entry_data[1:1+name_len].decode('utf-8', errors='ignore')
            offset, length = struct.unpack('<II', entry_data[248:256])
            entries.append((name, offset, length))
            
        # Extract files
        os.makedirs(dest_dir, exist_ok=True)
        for name, offset, length in entries:
            f.seek(offset)
            data = f.read(length)
            
            out_path = os.path.join(dest_dir, name)
            os.makedirs(os.path.dirname(out_path), exist_ok=True)
            with open(out_path, 'wb') as out_f:
                out_f.write(data)
            print(f"Extracted: {name} ({length} bytes)")

if __name__ == '__main__':
    br_path = sys.argv[1]
    dest_dir = sys.argv[2]
    extract_brarchive(br_path, dest_dir)
