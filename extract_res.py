import struct
import os
import sys

TRANSPARENT_CODE = 255
MANY_TRANSPARENT_CODE = 0xF8

def print_help():
    print("Extract images from Seven Kingdoms resource (.RES) files to BMP format.")
    print()
    print("Usage:")
    print("  python extract_res.py --resfile <resource file> --outputdir <output directory>")
    print()
    print("Options:")
    print("  --resfile    Path to the .RES file")
    print("  --outputdir  Directory to write extracted files")
    print("  --palette    Palette .RES file (default: PAL_STD.RES in current dir)")
    print("  --no-decompress  Save compressed data as .bin instead of decompressing")
    print("  --identify   Only identify the RES file format (no extraction)")
    print()
    print("Examples:")
    print("  python extract_res.py --resfile I_IF.RES --outputdir extracted")
    print("  python extract_res.py I_IF.RES --identify")

def decompress(width, height, compressed_data):
    output = bytearray(width * height)
    for i in range(width * height):
        output[i] = TRANSPARENT_CODE
    pos = 0
    idx = 0
    while idx < len(compressed_data):
        b = compressed_data[idx]
        idx += 1
        if b == MANY_TRANSPARENT_CODE:
            count = compressed_data[idx]
            idx += 1
            pos += count
        elif b >= MANY_TRANSPARENT_CODE + 1:
            count = 256 - b
            pos += count
        else:
            if pos < len(output):
                output[pos] = b
            pos += 1
    return bytes(output)

def save_bmp(filename, width, height, pixels, palette_data):
    row_size = (width + 3) & ~3
    padding_size = row_size - width
    padding = b'\x00' * padding_size
    bmp_pixels = []
    for y in range(height - 1, -1, -1):
        row = pixels[y * width : (y + 1) * width]
        bmp_pixels.append(row + padding)
    pixel_data = b''.join(bmp_pixels)
    palette_offset = 14 + 40 + 1024
    file_size = palette_offset + len(pixel_data)
    file_header = struct.pack('<2sIHHI', b'BM', file_size, 0, 0, palette_offset)
    info_header = struct.pack('<IiiHHIIiiII',
        40, width, height, 1, 8, 0, len(pixel_data), 0, 0, 256, 0)
    with open(filename, 'wb') as f:
        f.write(file_header)
        f.write(info_header)
        f.write(palette_data)
        f.write(pixel_data)

def load_palette(pal_file):
    if not os.path.exists(pal_file):
        return None
    with open(pal_file, 'rb') as f:
        f.seek(8)
        pal_raw = f.read(256 * 3)
        palette = b''
        for i in range(256):
            r, g, b = pal_raw[i*3 : i*3+3]
            palette += struct.pack('BBBB', b, g, r, 0)
    return palette

def is_named_format(f, file_size):
    f.seek(0)
    count_data = f.read(2)
    if len(count_data) < 2:
        return False
    count = struct.unpack('<H', count_data)[0]
    if count < 1 or count > 50000:
        return False
    f.seek(2)
    for i in range(min(count, 5)):
        name_raw = f.read(9)
        if len(name_raw) < 9:
            return False
        for c in name_raw:
            if c != 0 and (c < 32 or c > 126):
                return False
        ptr = struct.unpack('<I', f.read(4))[0]
        if ptr < 2 + 13 * count or ptr >= file_size:
            return False
    return True

def extract_as_wav(data, name, output_dir):
    os.makedirs(output_dir, exist_ok=True)
    path = os.path.join(output_dir, f"{name}.wav")
    with open(path, 'wb') as f:
        f.write(data)
    print(f"  {name}.wav ({len(data)} bytes)")
    return True

def extract_as_bmp(data, name, output_dir, palette):
    if len(data) < 4:
        return False
    os.makedirs(output_dir, exist_ok=True)
    width, height = struct.unpack('<HH', data[:4])
    if width < 1 or height < 1 or width > 10000 or height > 10000:
        return False
    pixels_data = data[4:]
    if width * height == len(pixels_data):
        pixels = pixels_data
    else:
        pixels = decompress(width, height, pixels_data)
    path = os.path.join(output_dir, f"{name}.bmp")
    save_bmp(path, width, height, pixels, palette)
    print(f"  {name}.bmp ({width}x{height})")
    return True

def extract_named(f, res_file, output_dir, palette, decompress_flag, file_size):
    f.seek(0)
    count = struct.unpack('<H', f.read(2))[0]

    entries = []
    for i in range(count + 1):
        name_raw = f.read(9)
        name = name_raw.split(b'\x00')[0].decode('ascii', errors='replace')
        ptr = struct.unpack('<I', f.read(4))[0]
        entries.append((name, ptr))

    extracted = 0
    wav_count = 0
    for i in range(count):
        name, offset = entries[i]
        next_offset = entries[i+1][1]
        size = next_offset - offset
        if not name:
            name = f"unnamed_{i:03d}"
        if size < 4:
            continue
        f.seek(offset)
        data = f.read(size)

        if data[:4] == b'RIFF' and data[8:12] == b'WAVE':
            extract_as_wav(data, name, output_dir)
            wav_count += 1
            extracted += 1
        elif extract_as_bmp(data, name, output_dir, palette):
            extracted += 1

    if extracted > 0:
        types = []
        if wav_count > 0:
            types.append(f"{wav_count} audio")
        if extracted - wav_count > 0:
            types.append(f"{extracted - wav_count} images")
        print(f"{res_file}: {', '.join(types)}")
    else:
        print(f"{os.path.basename(res_file)}: named resource (no extractable data)")

def extract_numeric(f, res_file, output_dir, palette, decompress_flag, file_size):
    f.seek(0)
    count = struct.unpack('<H', f.read(2))[0]
    offsets = []
    for i in range(count + 1):
        ptr = struct.unpack('<I', f.read(4))[0]
        offsets.append(ptr)
    extracted = 0
    for i in range(count):
        offset = offsets[i]
        next_offset = offsets[i+1]
        size = next_offset - offset
        name = f"record_{i:04d}"
        if size < 4:
            continue
        f.seek(offset)
        data = f.read(size)
        if extract_as_bmp(data, name, output_dir, palette):
            extracted += 1
    if extracted > 0:
        print(f"{res_file}: {extracted} images")
    else:
        print(f"{os.path.basename(res_file)}: numeric resource (no valid image data)")

def try_raw_blocks(f, res_file, output_dir, palette, decompress_flag, file_size):
    f.seek(0)
    index = 0
    extracted = 0
    tried = 0
    while f.tell() < file_size:
        offset = f.tell()
        if file_size - offset < 8:
            break
        block_size = struct.unpack('<I', f.read(4))[0]
        if block_size < 4 or block_size > file_size:
            break
        if offset + 4 + block_size > file_size:
            break
        data = f.read(block_size)
        width, height = struct.unpack('<HH', data[:4])
        if width < 1 or height < 1 or width > 10000 or height > 10000:
            tried += 1
            if tried > 10:
                break
            continue
        tried = 0
        name = f"record_{index:04d}"
        if extract_as_bmp(data, name, output_dir, palette):
            extracted += 1
        index += 1

    if extracted > 0:
        print(f"{res_file}: {extracted} images")
    else:
        print(f"{os.path.basename(res_file)}: unknown format")

RES_DESCRIPTIONS = {
    "A_WAVE1.RES": "Sound effects (wave audio)",
    "A_WAVE2.RES": "Sound effects (wave audio)",
    "CURSOR.RES": "Cursor animation sprite database",
    "FNT_BARD.RES": "Bard font",
    "FNT_CASA.RES": "Casa font",
    "FNT_CASA_88592.RES": "Casa font (ISO-8859-2)",
    "FNT_CASA_88593.RES": "Casa font (ISO-8859-3)",
    "FNT_CASA_88595.RES": "Casa font (ISO-8859-5)",
    "FNT_HITP.RES": "Hitpoint number font",
    "FNT_MID.RES": "Middle-size font",
    "FNT_MID_88592.RES": "Middle-size font (ISO-8859-2)",
    "FNT_MID_88593.RES": "Middle-size font (ISO-8859-3)",
    "FNT_MID_88595.RES": "Middle-size font (ISO-8859-5)",
    "FNT_NEWS.RES": "News/headline font",
    "FNT_NEWS_88592.RES": "News/headline font (ISO-8859-2)",
    "FNT_NEWS_88593.RES": "News/headline font (ISO-8859-3)",
    "FNT_NEWS_88595.RES": "News/headline font (ISO-8859-5)",
    "FNT_SAN.RES": "Sans-serif font",
    "FNT_SAN_88592.RES": "Sans-serif font (ISO-8859-2)",
    "FNT_SAN_88593.RES": "Sans-serif font (ISO-8859-3)",
    "FNT_SAN_88595.RES": "Sans-serif font (ISO-8859-5)",
    "FNT_SMAL.RES": "Small font",
    "FNT_SMAL_88592.RES": "Small font (ISO-8859-2)",
    "FNT_SMAL_88593.RES": "Small font (ISO-8859-3)",
    "FNT_SMAL_88595.RES": "Small font (ISO-8859-5)",
    "FNT_STD.RES": "Standard font",
    "FNT_STD_88592.RES": "Standard font (ISO-8859-2)",
    "FNT_STD_88593.RES": "Standard font (ISO-8859-3)",
    "FNT_STD_88595.RES": "Standard font (ISO-8859-5)",
    "HELP.RES": "Context-sensitive help text",
    "HILL1.RES": "Hill definitions (terrain set 1)",
    "HILL2.RES": "Hill definitions (terrain set 2)",
    "HILL3.RES": "Hill definitions (terrain set 3)",
    "I_BUTTON.RES": "Button images",
    "I_CURSOR.RES": "Cursor sprite bitmaps (raw format)",
    "I_ENCYC.RES": "Encyclopedia images",
    "I_FIRM.RES": "Firm building bitmaps",
    "I_FIRMDI.RES": "Firm destruction/damage bitmaps",
    "I_HILL1.RES": "Hill bitmap sprites (terrain set 1)",
    "I_HILL2.RES": "Hill bitmap sprites (terrain set 2)",
    "I_HILL3.RES": "Hill bitmap sprites (terrain set 3)",
    "I_ICON.RES": "Icon images",
    "I_IF.RES": "Main game interface screen",
    "I_IF_3840_2160.RES": "Main game interface (high resolution)",
    "I_MENU.RES": "Main menu images",
    "I_MENU2.RES": "Additional menu images",
    "I_PLANT1.RES": "Plant bitmap sprites (terrain set 1)",
    "I_PLANT2.RES": "Plant bitmap sprites (terrain set 2)",
    "I_PLANT3.RES": "Plant bitmap sprites (terrain set 3)",
    "I_RACE.RES": "Race emblem/icon bitmaps",
    "I_RAW.RES": "Raw material (resource) icons",
    "I_ROCK1.RES": "Rock obstacle sprites (terrain set 1)",
    "I_ROCK2.RES": "Rock obstacle sprites (terrain set 2)",
    "I_ROCK3.RES": "Rock obstacle sprites (terrain set 3)",
    "I_SNOW.RES": "Snow ground bitmaps",
    "I_SPICT.RES": "Small pictures/sprites",
    "I_TECH.RES": "Technology tree bitmaps",
    "I_TERA1.RES": "Terrain animation bitmaps (terrain set 1)",
    "I_TERA2.RES": "Terrain animation bitmaps (terrain set 2)",
    "I_TERA3.RES": "Terrain animation bitmaps (terrain set 3)",
    "I_TERN1.RES": "Terrain bitmaps (terrain set 1)",
    "I_TERN2.RES": "Terrain bitmaps (terrain set 2)",
    "I_TERN3.RES": "Terrain bitmaps (terrain set 3)",
    "I_TOWN.RES": "Town building bitmaps",
    "I_TPICT1.RES": "Terrain tile sprites (terrain set 1)",
    "I_TPICT2.RES": "Terrain tile sprites (terrain set 2)",
    "I_TPICT3.RES": "Terrain tile sprites (terrain set 3)",
    "I_UNITGI.RES": "Unit general icons",
    "I_UNITKI.RES": "Unit king icons",
    "I_UNITLI.RES": "Unit large icons",
    "I_UNITSI.RES": "Unit small icons",
    "I_UNITTI.RES": "Unit general small icons",
    "I_UNITUI.RES": "Unit king small icons",
    "I_WALL.RES": "Wall material bitmaps",
    "LOCALE.RES": "Locale/localization database",
    "PAL_ENC.RES": "Encyclopedia palette",
    "PAL_MENU.RES": "Menu palette",
    "PAL_STD.RES": "Standard game palette",
    "PAL_WIN.RES": "Window/dialog palette",
    "PLANT1.RES": "Plant definitions (terrain set 1)",
    "PLANT2.RES": "Plant definitions (terrain set 2)",
    "PLANT3.RES": "Plant definitions (terrain set 3)",
    "PLANTBM1.RES": "Plant bitmap database (terrain set 1)",
    "PLANTBM2.RES": "Plant bitmap database (terrain set 2)",
    "PLANTBM3.RES": "Plant bitmap database (terrain set 3)",
    "ROCK1.RES": "Rock definitions (terrain set 1)",
    "ROCK2.RES": "Rock definitions (terrain set 2)",
    "ROCK3.RES": "Rock definitions (terrain set 3)",
    "ROCKANI1.RES": "Rock animation database (terrain set 1)",
    "ROCKANI2.RES": "Rock animation database (terrain set 2)",
    "ROCKANI3.RES": "Rock animation database (terrain set 3)",
    "ROCKBLK1.RES": "Rock block database (terrain set 1)",
    "ROCKBLK2.RES": "Rock block database (terrain set 2)",
    "ROCKBLK3.RES": "Rock block database (terrain set 3)",
    "ROCKBMP1.RES": "Rock bitmap database (terrain set 1)",
    "ROCKBMP2.RES": "Rock bitmap database (terrain set 2)",
    "ROCKBMP3.RES": "Rock bitmap database (terrain set 3)",
    "TERANM1.RES": "Terrain animation database (terrain set 1)",
    "TERANM2.RES": "Terrain animation database (terrain set 2)",
    "TERANM3.RES": "Terrain animation database (terrain set 3)",
    "TERRAIN1.RES": "Terrain database (terrain set 1)",
    "TERRAIN2.RES": "Terrain database (terrain set 2)",
    "TERRAIN3.RES": "Terrain database (terrain set 3)",
    "TERSUB.RES": "Terrain substitution/underlay database",
    "TUT_INTR.RES": "Tutorial introduction text",
    "TUT_LIST.RES": "Tutorial scenario list",
    "TUT_PICT.RES": "Tutorial pictures",
    "TUT_TEXT.RES": "Tutorial text content",
}

def main():
    res_file = None
    output_dir = None
    pal_file = 'PAL_STD.RES'
    decompress_flag = True
    identify_flag = False

    args = sys.argv[1:]
    i = 0
    while i < len(args):
        if args[i] == '--resfile' and i + 1 < len(args):
            res_file = args[i + 1]
            i += 2
        elif args[i] == '--outputdir' and i + 1 < len(args):
            output_dir = args[i + 1]
            i += 2
        elif args[i] == '--palette' and i + 1 < len(args):
            pal_file = args[i + 1]
            i += 2
        elif args[i] == '--no-decompress':
            decompress_flag = False
            i += 1
        elif args[i] == '--identify':
            identify_flag = True
            i += 1
        elif args[i] == '--help' or args[i] == '-h':
            print_help()
            return
        elif not args[i].startswith('--'):
            if res_file is None:
                res_file = args[i]
                i += 1
            else:
                print(f"Unknown option: {args[i]}")
                print_help()
                return
        else:
            print(f"Unknown option: {args[i]}")
            print_help()
            return

    if not res_file:
        print_help()
        return
    if not identify_flag and not output_dir:
        print_help()
        return
    if not os.path.exists(res_file):
        print(f"Error: {res_file} not found.")
        return

    basename = os.path.basename(res_file)
    desc = RES_DESCRIPTIONS.get(basename)
    if desc is None:
        desc = RES_DESCRIPTIONS.get(basename + ".RES")

    if identify_flag:
        print(f"Contents: {desc if desc else 'no description available'}")
        return

    file_size = os.path.getsize(res_file)

    palette = load_palette(pal_file)
    if palette:
        print(f"Loaded palette from {pal_file}.")
    else:
        palette = b''
        for i in range(256):
            palette += struct.pack('BBBB', i, i, i, 0)

    print(f"Files written to: {output_dir}")
    if desc:
        print(f"File contents: {desc}")

    with open(res_file, 'rb') as f:
        sig = f.read(1)
        if sig == b'\x03':
            print(f"{os.path.basename(res_file)}: unsupported format (DBF)")
            return

        if is_named_format(f, file_size):
            extract_named(f, os.path.basename(res_file), output_dir, palette, decompress_flag, file_size)
        else:
            try_raw_blocks(f, os.path.basename(res_file), output_dir, palette, decompress_flag, file_size)

    print("\nExtraction complete.")

if __name__ == '__main__':
    main()
