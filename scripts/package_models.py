#!/usr/bin/env python3
"""Package model files into a zip for GitHub Release upload."""
import zipfile, os, sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Directories to include (all files recursively)
INCLUDE_DIRS = [
    "mario_models_new/GPT_SoVITS_Mario",
    "mario_models_new/MarioSwitch",
    "mario_models_new/SuperMario_TITAN",
    "server/data/rvc_model",
]

# Individual files to include
INCLUDE_FILES = [
    "server/data/mario_reference_sentences_30s.wav",
]

# Optional files (include if they exist, don't fail if missing)
OPTIONAL_FILES = [
    "server/data/mario_reference_sentences.wav",
]


def main():
    output = PROJECT_ROOT / "models-v2.1.zip"

    # Verify required dirs/files exist
    missing = []
    for d in INCLUDE_DIRS:
        p = PROJECT_ROOT / d
        if not p.is_dir():
            missing.append(str(d))
    for f in INCLUDE_FILES:
        p = PROJECT_ROOT / f
        if not p.is_file():
            missing.append(str(f))

    if missing:
        print("ERROR: Missing required files/directories:")
        for m in missing:
            print(f"  - {m}")
        sys.exit(1)

    file_count = 0
    with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as zf:
        # Add directories
        for d in INCLUDE_DIRS:
            dir_path = PROJECT_ROOT / d
            for root, dirs, files in os.walk(dir_path):
                for f in files:
                    if f.endswith('.pyc') or '__pycache__' in root:
                        continue
                    full = Path(root) / f
                    arcname = full.relative_to(PROJECT_ROOT)
                    print(f"  Adding: {arcname}")
                    zf.write(full, arcname)
                    file_count += 1

        # Add required individual files
        for f in INCLUDE_FILES:
            full = PROJECT_ROOT / f
            print(f"  Adding: {f}")
            zf.write(full, f)
            file_count += 1

        # Add optional files
        for f in OPTIONAL_FILES:
            full = PROJECT_ROOT / f
            if full.is_file():
                print(f"  Adding: {f} (optional)")
                zf.write(full, f)
                file_count += 1

    size_mb = output.stat().st_size / 1024 / 1024
    print(f"\nCreated {output.name} ({size_mb:.1f} MB, {file_count} files)")


if __name__ == "__main__":
    main()
