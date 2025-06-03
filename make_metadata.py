import os
import json
import re
import itertools

def parse_metadata(filepath):
    parts = filepath.split(os.sep)
    metadata = {
        "system_type": parts[0] if len(parts) > 0 else "",
        "material": parts[1] if len(parts) > 1 else "",
        "filename": os.path.basename(filepath)
    }
    fname = metadata["filename"]

    # ─── Size (nm or Å) ──────────────────────────────────────────────────────
    size_nm_match = re.search(r'(\d+(\.\d+)?)\s*nm', fname, re.IGNORECASE)
    size_A_match = re.search(r'(\d+(\.\d+)?)\s*(Å|Angstrom)', fname, re.IGNORECASE)
    if size_nm_match:
        metadata["size"] = float(size_nm_match.group(1))
        metadata["size_units"] = "nm"
    elif size_A_match:
        metadata["size"] = float(size_A_match.group(1))
        metadata["size_units"] = "angstrom"
    else:
        metadata["size"] = None
        metadata["size_units"] = ""

    # ─── Functional ─────────────────────────────────────────────────────────
    func_match = re.search(r'(HLE17|PBE|B3LYP|HSE06)', fname, re.IGNORECASE)
    if func_match:
        metadata["functional"] = func_match.group(1).upper()
    else:
        metadata["functional"] = ""

    # ─── Basis Set ──────────────────────────────────────────────────────────
    basis_match = re.search(r'(DZVP|TZVP)', fname, re.IGNORECASE)
    if basis_match:
        metadata["basis"] = basis_match.group(1).upper()
    elif metadata["functional"] == "HLE17":
        metadata["basis"] = "DZVP"
    else:
        metadata["basis"] = ""

    # ─── Run Type (from folder name: geo_opt or md) ─────────────────────────
    run_type = ""
    for part in parts:
        if part.lower() == "geo_opt":
            run_type = "Geometry Optimization"
            break
        elif part.lower() == "md":
            run_type = "Molecular Dynamics"
            break
    metadata["run_type"] = run_type

    # ─── DFT Code (default to CP2k unless 'orca' in name) ───────────────────
    if re.search(r'orca', fname, re.IGNORECASE):
        metadata["code"] = "ORCA"
    else:
        metadata["code"] = "CP2k"

    return metadata

def count_atoms(xyz_path):
    counts = {}
    try:
        with open(xyz_path, 'r') as f:
            lines = f.readlines()
        for line in lines[2:]:
            atom = line.strip().split()[0]
            if atom:
                counts[atom] = counts.get(atom, 0) + 1
    except Exception:
        pass
    return counts

def compute_all_ratios(counts):
    ratios = {}
    elements = [el for el in counts if counts[el] > 0]
    for el1, el2 in itertools.combinations(elements, 2):
        n1, n2 = counts[el1], counts[el2]
        if n2:
            ratios[f"{el1}/{el2}"] = round(n1 / n2, 3)
        if n1:
            ratios[f"{el2}/{el1}"] = round(n2 / n1, 3)
    return ratios

def find_xyz_files(root):
    xyz_paths = []
    for dirpath, dirnames, filenames in os.walk(root):
        # Skip any directory named 'md' (case-insensitive) 
        if any(part.lower() == "md" for part in dirpath.split(os.sep)):
            continue
        for f in filenames:
            if f.lower().endswith('.xyz'):
                relpath = os.path.relpath(os.path.join(dirpath, f), root)
                xyz_paths.append(relpath.replace("\\", "/"))
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
    print(f"Generated {metadata_out} for {len(meta)} structures.")

if __name__ == "__main__":
    main()

