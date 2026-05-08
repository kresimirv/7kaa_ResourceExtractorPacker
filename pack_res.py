import struct
import os
import sys

def load_bmp(filename):
    with open(filename, 'rb') as f:
        header = f.read(14)
        if header[:2] != b'BM':
            raise ValueError(f"Not a BMP file: {filename}")
        pixel_offset = struct.unpack('<I', header[10:14])[0]
        dib_header = f.read(40)
        width, height = struct.unpack('<ii', dib_header[4:12])
        bpp = struct.unpack('<H', dib_header[14:16])[0]
        if bpp != 8:
            raise ValueError(f"Only 8-bit BMPs are supported: {filename} is {bpp}-bit")
        f.seek(pixel_offset)
        raw_pixels = f.read()
        row_size = (width + 3) & ~3
        padding_size = row_size - width
        h_abs = abs(height)
        pixels = bytearray()
        for y in range(h_abs):
            row_idx = (h_abs - 1 - y) * row_size
            row = raw_pixels[row_idx : row_idx + width]
            pixels.extend(row)
        return width, h_abs, bytes(pixels)

def print_help():
    print("Pack files back into a named-format Seven Kingdoms resource (.RES) file.")
    print()
    print("Usage:")
    print("  python pack_res.py --inputdir <input directory> --outputres <output RES file>")
    print()
    print("Options:")
    print("  --inputdir   Directory containing .bmp and .wav files to pack")
    print("  --outputres  Path for the output .RES file")
    print()
    print("Examples:")
    print("  python pack_res.py --inputdir extracted --outputres I_IF.RES")

def main():
    input_dir = None
    output_res = None

    args = sys.argv[1:]
    i = 0
    while i < len(args):
        if args[i] == '--inputdir' and i + 1 < len(args):
            input_dir = args[i + 1]
            i += 2
        elif args[i] == '--outputres' and i + 1 < len(args):
            output_res = args[i + 1]
            i += 2
        elif args[i] == '--help' or args[i] == '-h':
            print_help()
            return
        else:
            print(f"Unknown option: {args[i]}")
            print_help()
            return

    if not input_dir or not output_res:
        print_help()
        return

    if not os.path.exists(input_dir):
        print(f"Error: Directory '{input_dir}' not found.")
        return

    files = os.listdir(input_dir)
    bmp_files = {}
    wav_files = {}
    for f in files:
        name_no_ext = os.path.splitext(f)[0]
        if f.lower().endswith('.bmp'):
            bmp_files[name_no_ext] = os.path.join(input_dir, f)
        elif f.lower().endswith('.wav'):
            wav_files[name_no_ext] = os.path.join(input_dir, f)

    all_names = sorted(set(bmp_files.keys()) | set(wav_files.keys()))
    if not all_names:
        print("No .bmp or .wav files found in input directory.")
        return

    print(f"Packing {len(all_names)} files into {output_res}...")

    packed_blocks = []
    for name in all_names:
        if name in bmp_files:
            try:
                w, h, pixels = load_bmp(bmp_files[name])
                block = struct.pack('<HH', w, h) + pixels
                packed_blocks.append(block)
                print(f"  {name}.bmp ({w}x{h})")
            except Exception as e:
                print(f"  Error loading {name}.bmp: {e}")
                return
        elif name in wav_files:
            try:
                with open(wav_files[name], 'rb') as f:
                    data = f.read()
                packed_blocks.append(data)
                print(f"  {name}.wav ({len(data)} bytes)")
            except Exception as e:
                print(f"  Error loading {name}.wav: {e}")
                return

    count = len(all_names)
    index_table_size = (count + 1) * 13
    current_offset = 2 + index_table_size

    pointers = []
    for block in packed_blocks:
        pointers.append(current_offset)
        current_offset += len(block)
    pointers.append(current_offset)

    with open(output_res, 'wb') as f:
        f.write(struct.pack('<H', count))
        for i in range(count):
            name_bytes = all_names[i].encode('ascii')[:8]
            name_padded = name_bytes.ljust(9, b'\x00')
            f.write(name_padded)
            f.write(struct.pack('<I', pointers[i]))
        f.write(b'\x00' * 9)
        f.write(struct.pack('<I', pointers[count]))
        for block in packed_blocks:
            f.write(block)

    print(f"\nSuccessfully created {output_res}")
    print(f"Size: {os.path.getsize(output_res)} bytes")

if __name__ == '__main__':
    main()
