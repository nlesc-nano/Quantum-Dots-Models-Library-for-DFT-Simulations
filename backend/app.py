import os
import tempfile
import subprocess
import yaml
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

class AttachRequest(BaseModel):
    xyztext: str
    smiles: str
    split: bool

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["POST"],
    allow_headers=["*"],
)

@app.post("/attach")
def attach(req: AttachRequest):
    # 1) Create a temporary directory to work in
    tmpdir = tempfile.mkdtemp()
    xyz_path = os.path.join(tmpdir, "core.xyz")
    with open(xyz_path, "w") as f:
        f.write(req.xyztext)

    # 2) Build the YAML input (always name the core file "core.xyz")
    inp = {
        "path": ".",
        "input_cores": [{ "core.xyz": {"guess_bonds": False} }],
        "input_ligands": [ req.smiles ],
        "optional": {
            "core":    { "dirname": "core", "anchor": "Cl", "allignment": "sphere", "subset": None },
            "ligand":  { "dirname": "ligand", "optimize": True, "split": req.split, "anchor": None, "cosmo-rs": False },
            "qd":      { "dirname": "qd",   "construct_qd": True, "optimize": False, "bulkiness": False,
                         "activation_strain": False, "dissociate": False },
        },
    }
    yaml_path = os.path.join(tmpdir, "input.yaml")
    with open(yaml_path, "w") as f:
        yaml.safe_dump(inp, f)

    # 3) Run CAT via the "init_cat" command
    try:
        # Make sure "init_cat" is on PATH (conda env) and points to your CAT entrypoint
        subprocess.run(
            ["init_cat", "input.yaml"],
            cwd=tmpdir,
            check=True,
            capture_output=True
        )
    except subprocess.CalledProcessError as e:
        # If CAT fails, forward the stderr back to the client as an HTTP 500
        raise HTTPException(status_code=500, detail=e.stderr.decode())

    # 4) Look in the "qd" subfolder for all .xyz files
    qd_dir = os.path.join(tmpdir, "qd")
    if not os.path.isdir(qd_dir):
        raise HTTPException(status_code=500, detail="CAT did not create a 'qd' folder")

    outs = sorted([fname for fname in os.listdir(qd_dir) if fname.lower().endswith(".xyz")])
    if not outs:
        raise HTTPException(status_code=500, detail="CAT produced no .xyz files")

    # 5) Read each .xyz into memory and append to results[]
    all_results = []
    for fname in outs:
        path = os.path.join(qd_dir, fname)
        try:
            with open(path, "r") as f:
                txt = f.read()
        except OSError as e:
            raise HTTPException(status_code=500, detail=f"Failed reading {fname}: {e}")
        all_results.append({
            "filename": fname,
            "xyz": txt
        })

    # 6) Return a consistent JSON with a "results" array
    return {
        "results": all_results,
        "message": f"CAT generated {len(all_results)} structure(s)"
    }


