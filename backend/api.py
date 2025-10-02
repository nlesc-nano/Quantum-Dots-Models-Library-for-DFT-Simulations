# backend/app.py
import os, glob, shlex, shutil, tempfile, subprocess
from typing import List, Dict, Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

class Job(BaseModel):
    ligands: List[str] = Field(..., min_items=1)
    dummy: str
    dist: str  # "r1:r2:...:mode" where mode ∈ {random, segmented}

class MiniCATRequest(BaseModel):
    xyztext: str
    out_prefix: str = "final_passivated_dot"
    jobs: List[Job] = Field(..., min_items=1)

class LegacyAttachRequest(BaseModel):
    xyztext: str
    smiles: str
    split: bool = True  # split→random, not split→segmented

app = FastAPI(title="miniCAT backend")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def root():
    return {"message": "miniCAT backend is alive. POST /attach"}

@app.post("/attach")
def attach(payload: Dict):
    # Parse new schema first
    req_jobs: List[Job]
    out_prefix = "final_passivated_dot"
    try:
        new = MiniCATRequest(**payload)
        xyztext = new.xyztext
        out_prefix = new.out_prefix
        req_jobs = new.jobs
    except Exception:
        # Fallback legacy: 1 ligand, single ratio
        try:
            old = LegacyAttachRequest(**payload)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid request body")
        xyztext = old.xyztext
        mode = "random" if old.split else "segmented"
        dist = f"1.0:{mode}"
        req_jobs = [Job(ligands=[old.smiles], dummy="Cl", dist=dist)]

    tmp = tempfile.mkdtemp(prefix="minicat_")
    try:
        core = os.path.join(tmp, "initial_dot.xyz")
        with open(core, "w") as f:
            f.write(xyztext)

        cmd = ["miniCAT", "--qd", "initial_dot.xyz", "--out_prefix", out_prefix]
        for j in req_jobs:
            cmd += ["--job-ligands", *j.ligands, "--job-dummy", j.dummy, "--job-dist", j.dist]
        cmd_str = " ".join(shlex.quote(c) for c in cmd)

        try:
            proc = subprocess.run(cmd, cwd=tmp, check=True, capture_output=True, text=True)
        except FileNotFoundError:
            raise HTTPException(status_code=500, detail="miniCAT executable not found on PATH")
        except subprocess.CalledProcessError as e:
            raise HTTPException(status_code=500, detail=e.stderr or e.stdout or "miniCAT failed")

        outs = sorted(glob.glob(os.path.join(tmp, f"{out_prefix}*.xyz")))
        if not outs:
            raise HTTPException(status_code=500, detail="miniCAT produced no .xyz files")

        results = []
        for p in outs:
            with open(p, "r") as f:
                results.append({"filename": os.path.basename(p), "xyz": f.read()})

        return {
            "message": f"miniCAT OK ({len(results)} file(s))",
            "results": results,
            "cmd": cmd_str,
            "stdout": proc.stdout,
            "stderr": proc.stderr,
        }
    finally:
        try: shutil.rmtree(tmp)
        except OSError: pass

