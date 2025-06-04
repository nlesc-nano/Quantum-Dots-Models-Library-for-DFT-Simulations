import os
import json
import re
import itertools

def parse_metadata(relpath):
    """
    Given a relative path like "II-VI/ZnSe/HLE17/28ang/geo_opt/StartXYZ.xyz",
    extract:
      - system_type   → "II-VI"
      - material      → "ZnSe"
      - filename      → "StartXYZ.xyz"
      - size (in nm)  → parsed from “28ang” → 2.8
      - functional    → "HLE17" if present
      - basis         → parsed from filename if “DZVP”/“TZVP” or default to "DZVP" when functional=="HLE17"
      - run_type      → "Geometry Optimization" if any folder is "geo_opt",
                         "Molecular Dynamics" if any folder is "md",
                         "Start" if any folder is "start" or if neither geo_opt nor md appear
      - code          → "ORCA" if “orca” in filename; else default "CP2K"
    """
    parts = relpath.split('/')
    filename = os.path.basename(relpath)
    metadata = {
        "system_type": parts[0] if len(parts) > 0 else "",
        "material": parts[1] if len(parts) > 1 else "",
        "filename": filename
    }

    # ─── Size in nm ───────────────────────────────────────────────────────
    nm_match  = re.search(r'(\d+(\.\d+)?)\s*nm', filename, re.IGNORECASE)
    ang_match = re.search(r'(\d+(\.\d+)?)\s*ang', filename, re.IGNORECASE)
    if nm_match:
        metadata["size"] = float(nm_match.group(1))
    elif ang_match:
        metadata["size"] = round(float(ang_match.group(1)) / 10.0, 3)
    else:
        metadata["size"] = None

    # ─── Functional ───────────────────────────────────────────────────────
    func_match = re.search(r'(HLE17|PBE|B3LYP|HSE06)', filename, re.IGNORECASE)
    metadata["functional"] = func_match.group(1).upper() if func_match else ""

    # ─── Basis Set ────────────────────────────────────────────────────────
    basis_match = re.search(r'(DZVP|TZVP)', filename, re.IGNORECASE)
    if basis_match:
        metadata["basis"] = basis_match.group(1).upper()
    elif metadata["functional"] == "HLE17":
        metadata["basis"] = "DZVP"
    else:
        metadata["basis"] = ""

    # ─── Run Type ─────────────────────────────────────────────────────────
    run_type = ""
    for part in parts:
        low = part.lower()
        if low == "geo_opt":
            run_type = "Geometry Optimization"
            break
        elif low == "md":
            run_type = "Molecular Dynamics"
            break
        elif low == "start":
            run_type = "Start"
            break
    # If neither geo_opt, md, nor start was found, default to "Start"
    if not run_type:
        run_type = "Start"
    metadata["run_type"] = run_type

    # ─── DFT Code ──────────────────────────────────────────────────────────
    if re.search(r'orca', filename, re.IGNORECASE):
        metadata["code"] = "ORCA"
    else:
        metadata["code"] = "CP2K"

    return metadata

def count_atoms(xyz_path):
    """
    Count atoms only from the first frame of an XYZ file.
    That way, for an MD “pos” file with multiple frames, we only count the first frame.
    """
    counts = {}
    try:
        with open(xyz_path, 'r') as f:
            first = f.readline()
            if not first:
                return counts
            try:
                n_atoms = int(first.strip())
            except ValueError:
                # If header is malformed, fall back to counting all lines after line 2
                lines = [first] + f.readlines()
                for line in lines[2:]:
                    parts = line.strip().split()
                    if parts:
                        el = parts[0]
                        counts[el] = counts.get(el, 0) + 1
                return counts

            # Skip comment line
            f.readline()

            # Read exactly n_atoms lines for the first frame
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
        parts = dirpath.split(os.sep)
        in_md_folder = any(p.lower() == "md" for p in parts)

        for f in filenames:
            if not f.lower().endswith(".xyz"):
                continue

            rel = os.path.relpath(os.path.join(dirpath, f), root).replace("\\", "/")

            if in_md_folder:
                # In an MD folder: only include files containing “pos”
                if "pos" in f.lower():
                    xyz_paths.append(rel)
            else:
                # Include everything else (including “start” frames, geo_opt, etc.)
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


