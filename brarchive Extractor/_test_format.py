from brarchive_format import serialize, deserialize

def test_brarchive():
    initial_data = {
        "textures/blocks/dirt.png": b"\\x89PNG\\r\\n\\x1a\\n\\x00\\x00\\x00rIHDRfake_image_data",
        "texts/en_US.lang": "pack.name=Test Pack\npack.description=A test pack"
    }

    # Serialize
    try:
        binary_data = serialize(initial_data)
        print(f"Serialized to {len(binary_data)} bytes")
    except Exception as e:
        print(f"Serialization failed: {e}")
        return

    # Deserialize
    try:
        recovered = deserialize(binary_data)
        print(f"Deserialized {len(recovered)} entries")
    except Exception as e:
        print(f"Deserialization failed: {e}")
        return

    # Verify
    for k, v in initial_data.items():
        if k not in recovered:
            print(f"Error: {k} missing from recovered data")
            continue

        expected_bytes = v if isinstance(v, bytes) else v.encode('utf-8')
        if recovered[k] != expected_bytes:
            print(f"Error: Data mismatch for {k}")
        else:
            print(f"Success: {k} matches original!")

if __name__ == "__main__":
    test_brarchive()
