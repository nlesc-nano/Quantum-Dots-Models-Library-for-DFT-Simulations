import os
import json
import re
import itertools

def parse_metadata(relpath):
    """
    Given a relative path like "II-VI/ZnSe/HLE17/28ang/geo_opt/Zn176Se147Cl58_HLE17_28ang_OPT.xyz",
    extract:
      - system_type    → "II-VI"
      - material       → "ZnSe"
      - filename       → "Zn176Se147Cl58_HLE17_28ang_OPT.xyz"
      - size (in nm)   → 2.8
      - functional     → "HLE17"  (if present; else "")
      - basis          → "DZVP"   (if filename contains DZVP/TZVP, use that; else if functional=="HLE17", use "DZVP")
      - run_type       → "Geometry Optimization"  if any folder is "geo_opt", or "Molecular Dynamics" if any folder is "md"
      - code           → "CP2k" (default) or "ORCA" if filename contains "orca"
    """
    parts = relpath.split('/')
    filename = os.path.basename(relpath)
    metadata = {
        "system_type": parts[0] if len(parts) > 0 else "",
        "material": parts[1] if len(parts) > 1 else "",
        "filename": filename
    }

    # ─── Size in nm ──────────────────────────────────────────────────────────────────────
    # Look for either “NNNnm” or “NNNang” (case‐insensitive)
    nm_match   = re.search(r'(\d+(\.\d+)?)\s*nm', filename, re.IGNORECASE)
    ang_match  = re.search(r'(\d+(\.\d+)?)\s*ang', filename, re.IGNORECASE)
    if nm_match:
        metadata["size"] = float(nm_match.group(1))
    elif ang_match:
        # Convert Å → nm
        ang_val = float(ang_match.group(1))
        metadata["size"] = round(ang_val / 10.0, 3)
    else:
        metadata["size"] = None

    # Always store size in nm; no need for units field:
    # metadata["size_units"] = "nm"

    # ─── Functional ──────────────────────────────────────────────────────────────────
    func_match = re.search(r'(HLE17|PBE|B3LYP|HSE06)', filename, re.IGNORECASE)
    metadata["functional"] = func_match.group(1).upper() if func_match else ""

    # ─── Basis Set ───────────────────────────────────────────────────────────────────
    basis_match = re.search(r'(DZVP|TZVP)', filename, re.IGNORECASE)
    if basis_match:
        metadata["basis"] = basis_match.group(1).upper()
    elif metadata["functional"] == "HLE17":
        metadata["basis"] = "DZVP"
    else:
        metadata["basis"] = ""

    # ─── Run Type (from any “geo_opt” or “md” folder) ───────────────────────────────────
    run_type = ""
    for part in parts:
        low = part.lower()
        if low == "geo_opt":
            run_type = "Geometry Optimization"
            break
        elif low == "md":
            run_type = "Molecular Dynamics"
            break
    metadata["run_type"] = run_type

    # ─── DFT Code (default CP2k; override if “orca” in filename) ────────────────────────
    if re.search(r'orca', filename, re.IGNORECASE):
        metadata["code"] = "ORCA"
    else:
        metadata["code"] = "CP2k"

    return metadata

def count_atoms(xyz_path):
    """
    Count atoms only from the first frame of an XYZ file.
    This way, if an MD “pos” file has many frames, we don’t aggregate across all frames.
    """
    counts = {}
    try:
        with open(xyz_path, 'r') as f:
            # 1) read first line: number of atoms (N)
            first = f.readline()
            if not first:
                return counts
            try:
                n_atoms = int(first.strip())
            except ValueError:
                # not a valid XYZ; fallback to naive parse of entire file
                lines = [first] + f.readlines()
                for line in lines[2:]:
                    parts = line.strip().split()
                    if parts:
                        el = parts[0]
                        counts[el] = counts.get(el, 0) + 1
                return counts

            # 2) skip comment line
            comment = f.readline()

            # 3) read exactly n_atoms lines and count
            for _ in range(n_atoms):
                line = f.readline()
                if not line:
                    break
                parts = line.strip().split()
                if parts:
                    el = parts[0]
                    counts[el] = counts.get(el, 0) + 1
    except Exception:
        pass

    return counts

def compute_all_ratios(counts):
    ratios = {}
    elements = [el for el in counts if counts[el] > 0]
    for el1, el2 in itertools.combinations(elements, 2):
        n1, n2 = counts.get(el1, 0), counts.get(el2, 0)
        if n2:
            ratios[f"{el1}/{el2}"] = round(n1 / n2, 3)
        if n1:
            ratios[f"{el2}/{el1}"] = round(n2 / n1, 3)
    return ratios

def find_xyz_files(root):
    xyz_paths = []
    for dirpath, dirnames, filenames in os.walk(root):
        # Skip any folder named “md” entirely – except we do want “pos” files if under md
        parts = dirpath.split(os.sep)
        if any(p.lower() == "md" for p in parts):
            # In an “md” folder: only include .xyz files containing “pos” in the name
            for f in filenames:
                if f.lower().endswith(".xyz") and "pos" in f.lower():
                    rel = os.path.relpath(os.path.join(dirpath, f), root).replace("\\", "/")
                    xyz_paths.append(rel)
            continue

        # Otherwise (not under md), include every .xyz
        for f in filenames:
            if f.lower().endswith(".xyz"):
                rel = os.path.relpath(os.path.join(dirpath, f), root).replace("\\", "/")
                xyz_paths.append(rel)
    xyz_paths.sort()
    return xyz_paths

def main():
    docs_dir = "docs"
    metadata_out = os.path.join(docs_dir, "metadata.json")

    xyz_files = find_xyz_files(docs_dir)
    meta = {}

    for relpath in xyz_files:
        entry = parse_metadata(relpath)
        full_path = os.path.join(docs_dir, relpath)
        atom_counts = count_atoms(full_path)
        entry["stoichiometry"] = atom_counts
        entry["ratios"] = compute_all_ratios(atom_counts)
        meta[relpath] = entry

    with open(metadata_out, "w") as out:
        json.dump(meta, out, indent=2)
    print(f"Generated {metadata_out} with {len(meta)} structures.")

if __name__ == "__main__":
    main()

