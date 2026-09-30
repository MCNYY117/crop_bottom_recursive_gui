# crop_bottom_recursive_gui

**A small Tkinter tool that crops the bottom off a whole folder of images — recursively — in one pass.**

Point it at a directory, type a Y coordinate, and every image in that tree gets cut off below that row. Output keeps the same folder structure, or overwrites in place if you leave the output directory blank.

**English** · [中文](README.zh-CN.md)

---

## Why it exists

Renaming or re-exporting a batch of images is easy. Removing something that is *baked into the pixels* — a date stamp the camera burned in, a watermark strip, a caption bar the scanner added — is not: there is no metadata to edit, you have to cut the pixels off. Doing that to 400 photos across 30 folders by hand is the kind of chore this exists to delete.

---

## Features

| | |
|---|---|
| **GUI, no command line** | Plain `tkinter` — nothing to learn, nothing to configure |
| **Recursive** | Walks every subfolder of the input root |
| **Keeps the tree** | Rebuilds the same relative paths under the output root |
| **Copy or overwrite** | Choose an output folder, or leave it blank to overwrite in place (asks first) |
| **Multiple formats** | `.jpg .jpeg .png .bmp .tiff` by default; the extension list is editable |
| **Live log** | Per-file results as they happen |
| **Doesn't freeze** | Runs on a worker thread, so the window stays responsive |

---

## Requirements

- **Python 3.8+**
- **[Pillow](https://python-pillow.org/)** — the only third-party dependency

No ffmpeg, no ImageMagick; all the image work is done in-process.

---

## Install and run

```bash
git clone https://github.com/MCNYY117/crop_bottom_recursive_gui.git
cd crop_bottom_recursive_gui
pip install -r requirements.txt
python crop_bottom_recursive_gui.py
```

---

## The GUI

| Field | What it means |
|---|---|
| **Input root** | The top folder to process. Every subfolder is walked. |
| **Output root** | Where results go. **Leave it blank to overwrite the originals** — it asks for confirmation first. |
| **Crop start Y** | Keep rows `0 … Y-1`, discard everything from row `Y` down. |
| **Extensions** | Space-separated, default `.jpg .jpeg .png .bmp .tiff`. |

### Steps

1. Pick the **input root**.
2. Pick an **output root** — or leave it blank to overwrite (not recommended for a first run).
3. Type the **crop start Y**.
4. Check the **extension list**.
5. Press **开始裁剪 / Start cropping** and watch the log.

---

## How the crop works

The origin is the **top-left corner**, and Y grows downward, so `Y` is simply "how many rows to keep".

For a 1920×1080 image:

| `Y` | Result |
|---|---|
| `1000` | Keeps rows 0–999; the bottom 80 rows are gone |
| `500` | Keeps rows 0–499; the bottom 580 rows are gone |

### ⚠️ Two things to know before a batch run

**The height check only looks at the first image.** The program finds one image, checks that your `Y` fits inside it, and refuses to start if it doesn't. Images *later* in the walk are not checked — if one is shorter than `Y`, Pillow does not error, it **pads the missing rows** (black for JPEG, possibly transparent for PNG). Check that the smallest image in your set is at least `Y` tall.

**Cropping does not resample, but saving re-encodes.** The pixels you keep are the original pixels — no blurring from scaling. But the file is written out again, so:

- **JPEG is re-compressed** at Pillow's default quality. It is lossy, and running the tool twice compounds it.
- **PNG / BMP / TIFF** are lossless; the kept pixels are preserved exactly.
- **EXIF is not carried over.** Capture time, GPS, camera model and orientation are dropped.

**Keep your originals.** Run a test batch into a separate output folder before you touch anything you care about.

---

## Directory layout

```
input/                          output/
├── photo1.jpg          →       ├── photo1.jpg
├── 2023/                       ├── 2023/
│   ├── photo2.jpg      →       │   ├── photo2.jpg
│   └── photo3.jpg      →       │   └── photo3.jpg
└── 2024/                       └── 2024/
    ├── event/                      ├── event/
    │   └── photo4.jpg  →           │   └── photo4.jpg
    └── photo5.jpg      →           └── photo5.jpg
```

---

## Packaging a standalone .exe

For handing the tool to someone without Python:

```bash
pip install pyinstaller
pyinstaller -F -w crop_bottom_recursive_gui.py
```

The result lands in `dist/`. `-F` makes a single file; `-w` suppresses the console window (you want this for a GUI).

To keep the size down, build inside a virtualenv that has only Pillow and PyInstaller installed:

```bash
python -m venv venv
venv\Scripts\activate          # Windows
pip install Pillow pyinstaller
pyinstaller -F -w crop_bottom_recursive_gui.py
```

Optional icon: add `-i my_icon.ico`.

---

## FAQ

**Some images were skipped.**
Their extension isn't in the list. Defaults are `.jpg .jpeg .png .bmp .tiff`; add yours in the GUI field.

**Does the window freeze on large batches?**
It shouldn't — processing runs on a worker thread and the log updates as it goes.

**Did the quality drop?**
The kept pixels are untouched, but see the warning above: JPEG is re-encoded on save and EXIF is dropped. PNG/BMP/TIFF are lossless.

**"Crop Y exceeds image height" — why?**
Your `Y` is taller than the first image the program found. Lower it — and remember only that first image was checked.

**How do I avoid losing data when overwriting?**
Test with an output folder first, then overwrite once you're happy. Overwrite mode has no undo.

**Can it crop the sides, or the top?**
Not from the GUI. In the code, change the `crop()` arguments:

```python
img.crop((0, 0, crop_x, img.height))          # right
img.crop((0, crop_y, img.width, img.height))  # top
img.crop((crop_x, 0, img.width, img.height))  # left
```

**Do all the images have to be the same size?**
They don't have to be, but the same `Y` means different things on different heights. If your set is mixed, normalise the sizes first.

---

## License

[MIT](LICENSE) — use it, change it, ship it.

## Contributing

Issues and pull requests are welcome. Fork, branch, commit, open a PR.

## Contact

Open an [issue](https://github.com/MCNYY117/crop_bottom_recursive_gui/issues).
