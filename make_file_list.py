import os

docs_dir = "docs"
out_file = os.path.join(docs_dir, "file_list.js")

xyz_files = []
for root, dirs, files in os.walk(docs_dir):
    # Exclude any dir named 'md' or 'MD' at any level
    if any(part.lower() == "md" for part in root.split(os.sep)):
        continue
    for f in files:
        if f.endswith(".xyz"):
            relpath = os.path.relpath(os.path.join(root, f), docs_dir)
            xyz_files.append(relpath.replace("\\", "/"))

xyz_files.sort()

with open(out_file, "w") as out:
    out.write("const xyzFiles = [\n")
    for path in xyz_files:
        out.write(f'  "{path}",\n')
    out.write("];\n")
print(f"Generated {out_file} with {len(xyz_files)} .xyz files (excluding md folders).")

