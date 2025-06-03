import os

docs_dir = "docs"
out_file = os.path.join(docs_dir, "file_list.js")

xyz_files = []
for root, dirs, files in os.walk(docs_dir):
    # Determine if this path is under an “md” folder (case‐insensitive)
    parts = root.split(os.sep)
    in_md_folder = any(part.lower() == "md" for part in parts)

    for f in files:
        if not f.lower().endswith(".xyz"):
            continue

        relpath = os.path.relpath(os.path.join(root, f), docs_dir).replace("\\", "/")

        if in_md_folder:
            # Only include .xyz filenames that contain “pos”
            if "pos" in f.lower():
                xyz_files.append(relpath)
        else:
            # Not under md/: include every .xyz
            xyz_files.append(relpath)

xyz_files.sort()

with open(out_file, "w") as out:
    out.write("const xyzFiles = [\n")
    for path in xyz_files:
        out.write(f'  "{path}",\n')
    out.write("];\n")

print(f"Generated {out_file} with {len(xyz_files)} .xyz files.")

