# Seven Kingdoms Resource File Tools

Scripts for extracting and packing Seven Kingdoms resource (`.RES`) files.

Place both scripts in `data/RESOURCE/` and run them from that directory so they can find `PAL_STD.RES` and other resource files automatically.

## extract_res.py

Extract images and audio from `.RES` files.

```
python extract_res.py --resfile <file.RES> --outputdir <directory>
```

**Options:**

| Option | Description |
|--------|-------------|
| `--resfile` | Path to the `.RES` file |
| `--outputdir` | Directory to write extracted files |
| `--palette` | Palette `.RES` file (default: `PAL_STD.RES`) |
| `--no-decompress` | Save compressed data as `.bin` instead of decompressing |
| `--identify` | Only identify the RES file contents (no extraction) |

**Examples:**

Extract images:
```
python extract_res.py --resfile I_MENU.RES --outputdir menu_extract
```

Extract audio:
```
python extract_res.py --resfile A_WAVE1.RES --outputdir wav_extract
```

Identify a file without extracting:
```
python extract_res.py --resfile I_IF.RES --identify
python extract_res.py I_IF.RES --identify
```

## pack_res.py

Pack extracted `.bmp` and `.wav` files back into a named-format `.RES` file.

```
python pack_res.py --inputdir <directory> --outputres <file.RES>
```

**Options:**

| Option | Description |
|--------|-------------|
| `--inputdir` | Directory containing `.bmp` and `.wav` files |
| `--outputres` | Path for the output `.RES` file |

**Example:**

```
python pack_res.py --inputdir menu_extract --outputres I_MENU.RES
```

## Round-trip Example

```
# Extract
python extract_res.py --resfile I_MENU.RES --outputdir extracted

# Modify files in extracted/ as needed

# Pack back
python pack_res.py --inputdir extracted --outputres I_MENU_new.RES
```

## Supported Formats

| Format | Extraction | Packing |
|--------|------------|---------|
| Named-format RES with BMP images | Yes | Yes |
| Named-format RES with WAV audio | Yes | Yes |
| Raw sequential block RES | Yes | No |
| DBF database RES | No | No |
| Font (FNT_*) RES | No | No |
| Palette RES | No | No |
