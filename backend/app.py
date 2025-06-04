# backend/app.py

import os
import tempfile
import subprocess
import yaml
import shutil
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

class AttachRequest(BaseModel):
    xyztext: str
    smiles: str
    split: bool

app = FastAPI()

# ① CORS, allow only your Pages domain or '*' for now
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["POST"],
    allow_headers=["*"],
)

# ② Add a root GET so GET / returns 200 (eliminate the 404 noise)
@app.get("/")
def root():
    return {"message": "CAT backend is alive. Use POST /attach"}

@app.post("/attach")
def attach(req: AttachRequest):
    # 1) Write the selected XYZ to a temp file
    tmpdir = tempfile.mkdtemp()
    xyz_path = os.path.join(tmpdir, "core.xyz")
    with open(xyz_path, "w") as f:
        f.write(req.xyztext)

    # 2) Build input.yaml
    inp = {
        "path": ".",
        "input_cores": [{"core.xyz": {"guess_bonds": False}}],
        "input_ligands": [req.smiles],
        "optional": {
            "core":    {"dirname": "core", "anchor": "Cl", "allignment": "sphere", "subset": None},
            "ligand":  {"dirname": "ligand", "optimize": True, "split": req.split, "anchor": None, "cosmo-rs": False},
            "qd":      {"dirname": "qd",   "construct_qd": True, "optimize": False, "bulkiness": False,
                        "activation_strain": False, "dissociate": False},
            "database": {}, 
        },
    }
    yaml_path = os.path.join(tmpdir, "input.yaml")
    with open(yaml_path, "w") as f:
        yaml.safe_dump(inp, f)

    # 3) Debug print (optional, helps see what's happening on Render)
    print("Temp dir:", tmpdir)
    print("Before running init_cat, contents:", os.listdir(tmpdir))

    # 4) Run CAT
    try:
        subprocess.run(
            ["init_cat", "input.yaml"],
            cwd=tmpdir,
            check=True,
            capture_output=True
        )
    except subprocess.CalledProcessError as e:
        # Dump stderr to logs for debugging
        print("init_cat stderr:", e.stderr.decode())
        raise HTTPException(status_code=500, detail=e.stderr.decode())

    # 5) After CAT runs, verify output folder exists
    qd_dir = os.path.join(tmpdir, "qd")
    if not os.path.isdir(qd_dir):
        raise HTTPException(status_code=500, detail="CAT did not create a 'qd' folder")

    outs = sorted([f for f in os.listdir(qd_dir) if f.lower().endswith(".xyz")])
    if not outs:
        raise HTTPException(status_code=500, detail="CAT produced no .xyz files")

    all_results = []
    for fname in outs:
        path = os.path.join(qd_dir, fname)
        try:
            with open(path, "r") as f:
                txt = f.read()
        except OSError as e:
            raise HTTPException(status_code=500, detail=f"Failed reading {fname}: {e}")
        all_results.append({"filename": fname, "xyz": txt})

    # Cleanup temporary directory after collecting results
    try:
        shutil.rmtree(tmpdir)
    except OSError as e:
        print(f"Warning: failed to remove temp directory {tmpdir}: {e}")

    return {"results": all_results, "message": f"CAT generated {len(all_results)} structure(s)"}

