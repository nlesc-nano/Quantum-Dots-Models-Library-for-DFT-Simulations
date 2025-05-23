import os
import re

# List of all target folders (excluding the source 'CdSe')
targets = [
    "CdS", "CdTe", "HgS", "HgSe", "HgTe", "ZnS", "ZnSe", "ZnTe"
]
source = "CdSe"

# Auto-detect geometry sizes from CdSe/HLE17/
size_root = os.path.join(source, "HLE17")
sizes = [d for d in os.listdir(size_root) if os.path.isdir(os.path.join(size_root, d))]

# List of halogens for filename and atom ordering
halogens = ["F", "Cl", "Br", "I", "At"]

def get_atom_mapping(target):
    """Return mapping from (Cd, Se) to the two elements of the target system."""
    match = re.match(r"([A-Z][a-z]?)([A-Z][a-z]?)", target)
    first, second = match.groups()
    return {"Cd": first, "Se": second}

def update_filename(old_filename, atom_counts, core, chalcogen):
    """
    Build new xyz filename:
    Core first, then chalcogen, then halogens (alphabetical), then any others.
    E.g. Hg68S55Cl26_HLE17_20ang_start.xyz
    """
    parts = []
    if core in atom_counts:
        parts.append(f"{core}{atom_counts[core]}")
    if chalcogen in atom_counts:
        parts.append(f"{chalcogen}{atom_counts[chalcogen]}")
    for hal in halogens:
        if hal in atom_counts:
            parts.append(f"{hal}{atom_counts[hal]}")
    # Add any other atoms
    for at in sorted(atom_counts):
        if at not in ([core, chalcogen] + halogens):
            parts.append(f"{at}{atom_counts[at]}")
    prefix = "".join(parts)
    # Use original suffix
    m = re.search(r"(_HLE17_.*)", old_filename)
    suffix = m.group(1) if m else ""
    return prefix + suffix

def atom_sort_key(atom, core, chalcogen):
    """Custom sorting: core first, chalcogen second, halogens next, then others."""
    if atom == core:
        return (0, atom)
    elif atom == chalcogen:
        return (1, atom)
    elif atom in halogens:
        return (2, halogens.index(atom))
    else:
        return (3, atom)

def parse_atom_line(line):
    """Split line into (symbol, rest_of_line, original_line)."""
    parts = line.rstrip('\n').split(maxsplit=1)
    symbol = parts[0]
    rest = parts[1] if len(parts) > 1 else ""
    return symbol, rest, line.rstrip('\n')

for target in targets:
    print(f"\n=== Processing target system: {target} ===")
    folders = ["HLE17"]
    if target.startswith("Hg"):
        folders.append("PBE")
        print(f"  (HgX detected, will also process PBE functional)")

    atom_map = get_atom_mapping(target)
    core, chalcogen = atom_map["Cd"], atom_map["Se"]

    for func in folders:
        for size in sizes:
            source_dir = os.path.join(source, "HLE17", size, "start")
            target_dir = os.path.join(target, func, size, "start")
            os.makedirs(target_dir, exist_ok=True)

            print(f"\n  Processing {func}/{size}...")
            print(f"    Source: {source_dir}")
            print(f"    Target: {target_dir}")

            if not os.path.isdir(source_dir):
                print(f"    [!] Source directory does not exist, skipping...")
                continue
            xyz_files = [f for f in os.listdir(source_dir) if f.endswith(".xyz")]
            if not xyz_files:
                print(f"    [!] No xyz files found, skipping...")
                continue

            for xyz_file in xyz_files:
                print(f"    - Reading: {xyz_file}")
                src_path = os.path.join(source_dir, xyz_file)

                with open(src_path) as f:
                    lines = f.readlines()
                n_atoms = int(lines[0].strip())
                comment = lines[1]
                atom_lines = lines[2:2+n_atoms]

                # Substitute and collect (new_atom, rest, original_line)
                atoms_list = []
                atom_counts = {}

                for line in atom_lines:
                    orig_symbol, rest, orig_line = parse_atom_line(line)
                    new_symbol = atom_map.get(orig_symbol, orig_symbol)
                    atoms_list.append((new_symbol, rest, orig_line))
                    atom_counts[new_symbol] = atom_counts.get(new_symbol, 0) + 1

                # Sort atom lines
                sorted_atoms = sorted(atoms_list, key=lambda x: atom_sort_key(x[0], core, chalcogen))

                # Rebuild lines, preserving layout (replace only symbol)
                new_atom_lines = []
                for symbol, rest, orig_line in sorted_atoms:
                    if rest:
                        # Replace only the symbol (preserve original line's spacing)
                        # Use the original spacing after the symbol
                        new_line = f"{symbol}{orig_line[len(symbol):]}"
                    else:
                        new_line = symbol
                    new_atom_lines.append(new_line + "\n")

                # Generate new filename
                new_filename = update_filename(xyz_file, atom_counts, core, chalcogen)
                dst_path = os.path.join(target_dir, new_filename)

                # Write output xyz
                with open(dst_path, "w") as fout:
                    fout.write(f"{n_atoms}\n")
                    fout.write(comment)
                    fout.writelines(new_atom_lines)
                    # Write extra lines if present
                    if len(lines) > 2 + n_atoms:
                        fout.writelines(lines[2 + n_atoms:])

                print(f"      -> Written: {dst_path} (atoms: {atom_counts})")

print("\nAll done!")

