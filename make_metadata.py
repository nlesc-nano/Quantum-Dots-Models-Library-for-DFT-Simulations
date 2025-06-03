import os
import json
import re
import itertools

def parse_metadata(filepath):
    # Extract info from path
    parts = filepath.split(os.sep)
    metadata = {
        "system_type": parts[0] if len(parts) > 0 else "",
        "material": parts[1] if len(parts) > 1 else "",
        "filename": os.path.basename(filepath)
    }
    fname = metadata["filename"]
    # Size in nm or angstroms
    size_nm = re.search(r'(\d+(\.\d+)?)\s*nm', fname, re.IGNORECASE)
    size_A = re.search(r'(\d+(\.\d+)?)\s*(A|Angstrom)', fname, re.IGNORECASE)
    if size_nm:
        metadata["size"] = float(size_nm.group(1))
        metadata["size_units"] = "nm"
    elif size_A:
        metadata["size"] = float(size_A.group(1))
        metadata["size_units"] = "angstrom"
    else:
        metadata["size"] = None
        metadata["size_units"] = ""
    # Functional, with default DZVP
    functional = re.search(r'(HLE17|PBE|B3LYP|HSE06|DZVP|TZVP)', fname, re.IGNORECASE)
    metadata["functional"] = functional.group(1) if functional else "DZVP"
    # Run type
    if "geo" in fname.lower():
        metadata["run_type"] = "Geometry Optimization"
    elif "md" in fname.lower():
        metadata["run_type"] = "MD"
    else:
        metadata["run_type"] = ""
    # DFT code, with default CP2k
    if "cp2k" in fname.lower():
        metadata["code"] = "CP2k"
    elif "orca" in fname.lower():
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
            if len(atom) > 0:
                counts[atom] = counts.get(atom, 0) + 1
    except Exception:
        pass
    return counts

def compute_all_ratios(counts):
    ratios = {}
    elements = [el for el in counts if counts[el] > 0]
    for el1, el2 in itertools.combinations(elements, 2):
        n1, n2 = counts[el1], counts[el2]
        ratios[f"{el1}/{el2}"] = round(n1 / n2, 3) if n2 else None
        ratios[f"{el2}/{el1}"] = round(n2 / n1, 3) if n1 else None
    return ratios

def find_xyz_files(root):
    xyz_paths = []
    for dirpath, dirnames, filenames in os.walk(root):
        # Skip md/MD folders
        if any(part.lower() == "md" for part in dirpath.split(os.sep)):
            continue
        for f in filenames:
            if f.endswith('.xyz'):
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

