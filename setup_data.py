#!/usr/bin/env python3
"""
Setup script to populate backend/Tech Outputs with East Coast Model data.

Usage:
    python setup_data.py <path_to_east_coast_model>

Examples:
    python setup_data.py "D:/Rob M/East Coast Model"
    python setup_data.py ../East Coast Model

This creates symlinks (preferred) or copies (fallback) so the Flask backend
can discover the NPZ files without duplicating ~2 GB of data.
"""

import os
import sys
import shutil
from pathlib import Path


def main():
    if len(sys.argv) < 2:
        print("Usage: python setup_data.py <path_to_east_coast_model>")
        print('Example: python setup_data.py "D:/Rob M/East Coast Model"')
        sys.exit(1)

    east_coast_root = Path(sys.argv[1]).resolve()
    ec_tech = east_coast_root / "Tech Outputs"

    if not ec_tech.is_dir():
        print(f"ERROR: Tech Outputs directory not found at {ec_tech}")
        sys.exit(1)

    script_dir = Path(__file__).resolve().parent
    backend_tech = script_dir / "backend" / "Tech Outputs"
    backend_tech.mkdir(parents=True, exist_ok=True)

    # Mapping: (source subdirectory in East Coast Model, target subdirectory in backend)
    links = [
        (ec_tech / "Wind",                     backend_tech / "Wind"),
        (ec_tech / "Wave" / "ByState_Uniform",  backend_tech / "Wave" / "ByState_Uniform"),
        (ec_tech / "Wave" / "ByState",          backend_tech / "Wave" / "ByState"),
        (ec_tech / "Current",                   backend_tech / "Current"),
        (ec_tech / "Transmission" / "ByState",  backend_tech / "Transmission" / "ByState"),
    ]

    use_symlinks = True

    for src, dst in links:
        if not src.is_dir():
            print(f"  SKIP  {src}  (not found)")
            continue

        # Aggressively remove whatever is at dst (broken symlink, empty dir, etc.)
        def _force_remove(path):
            try:
                if os.path.islink(str(path)):
                    os.unlink(str(path))
                    return
            except OSError:
                pass
            try:
                # Try rmdir for empty dirs or junction points
                os.rmdir(str(path))
                return
            except OSError:
                pass
            try:
                os.unlink(str(path))
                return
            except OSError:
                pass

        # Check if dst exists at all (without following symlinks)
        if os.path.lexists(str(dst)):
            try:
                if os.path.islink(str(dst)):
                    # Broken or working symlink - remove it
                    _force_remove(dst)
                else:
                    # Real path - check for content
                    try:
                        contents = list(os.scandir(str(dst)))
                        if contents:
                            print(f"  EXISTS {dst}  ({len(contents)} items, skipping)")
                            continue
                        _force_remove(dst)
                    except OSError:
                        _force_remove(dst)
            except Exception as e:
                print(f"  WARN could not inspect {dst}: {e}")
                _force_remove(dst)

        # Make sure parent exists
        dst.parent.mkdir(parents=True, exist_ok=True)

        if use_symlinks:
            try:
                os.symlink(str(src), str(dst), target_is_directory=True)
                print(f"  LINK  {dst}  -->  {src}")
                continue
            except OSError as e:
                print(f"  Symlink failed ({e}), falling back to copy...")
                use_symlinks = False

        # Fallback: copy files
        print(f"  COPY  {src}  -->  {dst}")
        shutil.copytree(str(src), str(dst), dirs_exist_ok=True)

    # Also handle loose transmission files in the root Transmission dir
    trans_root_src = ec_tech / "Transmission"
    trans_root_dst = backend_tech / "Transmission"
    trans_root_dst.mkdir(parents=True, exist_ok=True)
    for f in trans_root_src.glob("Transmission_*.npz"):
        dst_file = trans_root_dst / f.name
        if not dst_file.exists():
            if use_symlinks:
                try:
                    os.symlink(str(f), str(dst_file))
                    print(f"  LINK  {dst_file.name}")
                except OSError:
                    shutil.copy2(str(f), str(dst_file))
                    print(f"  COPY  {dst_file.name}")
            else:
                shutil.copy2(str(f), str(dst_file))
                print(f"  COPY  {dst_file.name}")

    print("\nDone! Backend Tech Outputs is now populated.")
    print("You can start the app with: docker compose up --build")
    print("Or run the Flask backend directly: cd backend && python app.py")


if __name__ == "__main__":
    main()
