// ---- Config
const CAT_ATTACH = 'http://127.0.0.1:8000/attach';

// ---- State
let metadata = {};
let viewer = null;
let currentFile = "";
let currentXYZText = "";
let currentMeta = null;      // keep selected meta
let atomColors = {};

// ---- DOM map
const els = {
  sys: document.getElementById('filter-system'),
  mat: document.getElementById('filter-material'),
  size: document.getElementById('filter-size'),
  fun: document.getElementById('filter-functional'),
  run: document.getElementById('filter-runtype'),
  file: document.getElementById('xyz-file'),
  down: document.getElementById('download-btn'),
  downpng: document.getElementById('download-png-btn'),
  reset: document.getElementById('reset-btn'),
  viewer: document.getElementById('viewer'),
  traj: document.getElementById('traj-controls'),
  details: document.getElementById('details-content'),
  ratios: document.getElementById('ratios-wrap'),
  stoTot: document.getElementById('stoich-totals'),
  stoCore: document.getElementById('stoich-core'),
  stoShell: document.getElementById('stoich-shell'),
  stoLig: document.getElementById('stoich-lig'),

  // miniCAT
  anRows: document.getElementById('an_rows'),
  anAdd: document.getElementById('an_add'),
  anDummy: document.getElementById('an_dummy'),
  runCat: document.getElementById('run-cat-btn'),
  catStatus: document.getElementById('cat-status'),
  catSelect: document.getElementById('cat-output-select'),
  catDownload: document.getElementById('download-catxyz-btn'),
  term: document.getElementById('cat-term'),
  resetCat: document.getElementById('reset-cat-btn'),
};

const tooltipEl = document.getElementById('tooltip');
document.addEventListener('mouseover', e=>{
  const t=e.target.getAttribute('data-help'); if(!t) return;
  tooltipEl.textContent=t; tooltipEl.style.left=(e.clientX+12)+'px'; tooltipEl.style.top=(e.clientY+12)+'px'; tooltipEl.classList.add('show');
});
document.addEventListener('mousemove', e=>{
  if(tooltipEl.classList.contains('show')){ tooltipEl.style.left=(e.clientX+12)+'px'; tooltipEl.style.top=(e.clientY+12)+'px';}
});
document.addEventListener('mouseout', e=>{
  if(e.target.getAttribute('data-help')) tooltipEl.classList.remove('show');
});

// ---- helpers
function jmolHex(el){
  const v = $3Dmol.elementColors.Jmol[el];
  if (typeof v === 'number') return '#'+v.toString(16).padStart(6,'0');
  if (typeof v === 'string' && v.startsWith('0x')) return '#'+v.slice(2).padStart(6,'0');
  return '#909090';
}
function downloadDataURL(u,name){ const a=document.createElement('a'); a.href=u; a.download=name; document.body.appendChild(a); a.click(); a.remove(); }
function downloadBlob(data,name,type){ const blob=data instanceof Blob?data:new Blob([data],{type}); const url=URL.createObjectURL(blob); const a=document.createElement('a'); a.href=url; a.download=name; a.click(); URL.revokeObjectURL(url); }

// auto output prefix: e.g., CdSe_12ang_HLE_passivated
function autoPrefix(meta){
  const material = meta.material || 'QD';
  const ang = Number.isFinite(meta.size) ? Math.round(meta.size * 10) : null;
  const fun = (meta.functional || 'DFT').replace(/\d+$/,''); // HLE17 -> HLE
  const parts = [material];
  if (ang !== null) parts.push(`${ang}ang`);
  parts.push(fun);
  return parts.join('_') + '_passivated';
}

// ---- style
function applyStyle(){
  if(!viewer) return;
  const mode = document.querySelector('input[name="style-radio"]:checked').value;
  let base={};
  if(mode==='sphere') base={sphere:{scale:1.0, colorscheme:'Jmol'}};
  else if(mode==='ballstick') base={stick:{radius:0.12, colorscheme:'Jmol'}, sphere:{scale:0.30, colorscheme:'Jmol'}};
  else base={stick:{radius:0.15, colorscheme:'Jmol'}};
  viewer.setStyle({},{}); viewer.setStyle({},base);
  Object.keys(atomColors).forEach(el=>{
    const styled=JSON.parse(JSON.stringify(base));
    if(styled.sphere){ delete styled.sphere.colorscheme; styled.sphere.color=atomColors[el]; }
    if(styled.stick){  delete styled.stick.colorscheme;  styled.stick.color =atomColors[el]; }
    viewer.setStyle({elem:el}, styled);
  });
  viewer.zoomTo(); viewer.render();
}
document.querySelectorAll('input[name="style-radio"]').forEach(r=>r.addEventListener('change',applyStyle));

// ---- stoichiometry
function chipHTML(el,n){
  const hex = atomColors[el] || jmolHex(el);
  return `<span class="atom-chip border" data-el="${el}"
            style="border-color:#000; color:${hex}">
            ${el}<span class="ml-1 text-slate-600 font-normal">· ${n}</span>
          </span>`;
}
function blockHTML(title,obj){
  const tot=obj?.total||0; const by=obj?.by_element||{};
  const items = Object.entries(by).sort(([a],[b])=>a.localeCompare(b)).map(([e,n])=>chipHTML(e,n)).join('');
  return `<div class="mb-2"><div class="text-sm font-semibold">${title} — Total: ${tot}</div><div class="mt-1">${items||'<span class="text-gray-400 text-xs">—</span>'}</div></div>`;
}
function bindChipPickers(root){
  root.querySelectorAll('.atom-chip').forEach(ch=>{
    ch.onclick=()=>{
      const el = ch.getAttribute('data-el');
      const input=document.createElement('input'); input.type='color'; input.value=atomColors[el]||jmolHex(el); input.style.position='fixed'; input.style.left='-9999px';
      document.body.appendChild(input); input.click();
      input.oninput=()=>{ atomColors[el]=input.value; applyStyle(); ch.style.borderColor='#000'; ch.style.color=input.value; };
      input.addEventListener('blur',()=>input.remove());
    };
  });
}
function updateStoichiometry(meta){
  const gc = meta.grouped_counts || null;
  const flat = meta.stoichiometry || {};
  if(gc && gc.total_atoms){
    els.stoTot.textContent = `Total Atoms: ${gc.total_atoms}`;
    els.stoCore.innerHTML = blockHTML('Core', gc.core || {total:0, by_element:{}});
    els.stoShell.innerHTML = blockHTML('Shell', gc.shell || {total:0, by_element:{}});
    els.stoLig.innerHTML = blockHTML('Ligand placeholders', gc.ligands || {total:0, by_element:{}});
  } else {
    const total = Object.values(flat).reduce((a,b)=>a+b,0);
    els.stoTot.textContent = `Total Atoms: ${total}`;
    els.stoCore.innerHTML = blockHTML('All atoms', {total, by_element: flat});
    els.stoShell.innerHTML = '';
    els.stoLig.innerHTML = '';
  }
  bindChipPickers(document);
}

// ---- ratios
function renderRatios(obj){
  els.ratios.innerHTML='';
  Object.entries(obj||{}).sort().forEach(([k,v])=>{
    const pill=document.createElement('span'); pill.className='ratio-pill';
    pill.innerHTML=`<span class="k">${k}</span><span class="v">${Number(v).toFixed(3)}</span>`;
    els.ratios.appendChild(pill);
  });
}

// ---- MD controls
function setupTrajectoryControls(){
  const n = viewer.getNumFrames?.() || 0;
  els.traj.innerHTML = '';
  if(!n){ els.traj.classList.add('hidden'); return; }
  els.traj.classList.remove('hidden');

  const wrap=document.createElement('div'); wrap.className='flex flex-wrap items-center gap-3';
  const mkBtn=t=>{ const b=document.createElement('button'); b.textContent=t; b.className='btn'; return b; };
  const mkSel=opts=>{ const s=document.createElement('select'); s.className='input text-sm';
    opts.forEach(o=>{const op=document.createElement('option'); op.value=o.v; op.text=o.t; if(o.sel) op.selected=true; s.appendChild(op);});
    return s; };

  const stop=mkBtn('Stop'), replay=mkBtn('Replay'), play=mkBtn('Play');
  const slider=document.createElement('input'); slider.type='range'; slider.min=0; slider.max=n-1; slider.value=0; slider.className='w-72';
  const label=document.createElement('span'); label.className='text-sm text-slate-600'; label.textContent=`Frame: 1 / ${n}`;
  const speed=mkSel([{t:'0.25x',v:160},{t:'0.5x',v:80},{t:'1x',v:40,sel:true},{t:'2x',v:20}]);
  const spLbl=document.createElement('span'); spLbl.className='text-sm text-slate-600'; spLbl.textContent='Speed:';
  const exXYZ=mkBtn('Export XYZ'), exPNG=mkBtn('Export PNG');

  let playing=false, h=null, interval=parseInt(speed.value,10);
  function upd(f){ slider.value=f; label.textContent=`Frame: ${f+1} / ${n}`; }
  function start(from){
    if(h) clearInterval(h);
    playing=true; play.textContent='Pause';
    let cur=parseInt(from ?? slider.value,10);
    h=setInterval(()=>{
      if(cur<n-1){ cur++; viewer.setFrame(cur); viewer.render(); upd(cur); }
      else { clearInterval(h); playing=false; play.textContent='Play'; }
    }, interval);
  }

  play.onclick=()=>{ if(!playing) start(slider.value); else { playing=false; play.textContent='Play'; clearInterval(h);} };
  stop.onclick=()=>{ playing=false; play.textContent='Play'; clearInterval(h); viewer.setFrame(0); viewer.render(); upd(0); };
  replay.onclick=()=>{ playing=false; play.textContent='Pause'; clearInterval(h); viewer.setFrame(0); viewer.render(); upd(0); start(0); };
  speed.onchange=()=>{ interval=parseInt(speed.value,10); if(playing){ clearInterval(h); start(slider.value);} };
  slider.oninput=()=>{ const f=parseInt(slider.value,10); viewer.setFrame(f); viewer.render(); upd(f); if(playing){ playing=false; play.textContent='Play'; clearInterval(h);} };

  exXYZ.onclick=()=>{ const f=parseInt(slider.value,10);
    const model=viewer.getModel(); const atoms=model.selectedAtoms({frame:f});
    let s=atoms.length+'\nframe '+(f+1)+'\n';
    atoms.forEach(a=>{ s+=`${a.elem||a.atom} ${a.x} ${a.y} ${a.z}\n`; });
    downloadBlob(s,`frame_${f+1}.xyz`,'text/plain');
  };
  exPNG.onclick=()=>{ const canvas=els.viewer.querySelector('canvas'); if(!canvas) return;
    downloadDataURL(canvas.toDataURL('image/png'),`frame_${parseInt(slider.value,10)+1}.png`);
  };

  wrap.append(stop,replay,play,slider,label,spLbl,speed,exXYZ,exPNG);
  els.traj.appendChild(wrap);
}

// ---- filter chain (unchanged)
function populateSystemTypes(){ const s=new Set(); for(const p in metadata){ const m=metadata[p]; if(m.system_type) s.add(m.system_type);} [...s].sort().forEach(v=>{const o=document.createElement('option'); o.value=v; o.text=v; els.sys.appendChild(o);}); }
function populateMaterials(){ els.mat.innerHTML='<option value="">— Select —</option>'; const sys=els.sys.value; const s=new Set(); for(const p in metadata){ const m=metadata[p]; if(m.system_type===sys && m.material) s.add(m.material);} [...s].sort().forEach(v=>{const o=document.createElement('option'); o.value=v; o.text=v; els.mat.appendChild(o);}); els.mat.disabled=s.size===0; }
function populateSizes(){ els.size.innerHTML='<option value="">— Select —</option>'; const sys=els.sys.value, mat=els.mat.value; const s=new Set(); for(const p in metadata){ const m=metadata[p]; if(m.system_type===sys && m.material===mat && m.size!=null) s.add(m.size);} [...s].sort((a,b)=>a-b).forEach(v=>{const o=document.createElement('option'); o.value=v; o.text=`${v} nm`; els.size.appendChild(o);}); els.size.disabled=s.size===0; }
function populateFunctionals(){ els.fun.innerHTML='<option value="">— Select —</option>'; const sys=els.sys.value, mat=els.mat.value, size=parseFloat(els.size.value); const s=new Set(); for(const p in metadata){ const m=metadata[p]; if(m.system_type===sys && m.material===mat && m.size===size && m.functional) s.add(m.functional);} [...s].sort().forEach(v=>{const o=document.createElement('option'); o.value=v; o.text=v; els.fun.appendChild(o);}); els.fun.disabled=s.size===0; }
function populateRunTypes(){ els.run.innerHTML='<option value="">— Select —</option>'; const sys=els.sys.value, mat=els.mat.value, size=parseFloat(els.size.value), f=els.fun.value; const s=new Set(); for(const p in metadata){ const m=metadata[p]; if(m.system_type===sys && m.material===mat && m.size===size && m.functional===f && m.run_type) s.add(m.run_type);} [...s].sort().forEach(v=>{const o=document.createElement('option'); o.value=v; o.text=v; els.run.appendChild(o);}); els.run.disabled=s.size===0; }
function populateFileList(){ els.file.innerHTML='<option value="">— Select —</option>'; const sys=els.sys.value, mat=els.mat.value, size=parseFloat(els.size.value), f=els.fun.value, run=els.run.value; const matches=[]; for(const p in metadata){ const m=metadata[p]; if(m.system_type===sys&&m.material===mat&&m.size===size&&m.functional===f&&m.run_type===run) matches.push(p);} matches.sort().forEach(p=>{const o=document.createElement('option'); o.value=p; o.text=metadata[p].filename; els.file.appendChild(o);}); const has=matches.length>0; [els.file, els.down, els.downpng].forEach(e=>e.disabled=!has); if(has){ els.file.value=matches[0]; loadXYZ(matches[0]); } }

els.sys.addEventListener('change', ()=>{ if(els.sys.value){ populateMaterials(); els.mat.disabled=false; } else { els.mat.innerHTML='<option value="">— Select —</option>'; els.mat.disabled=true; } els.size.innerHTML='<option value="">— Select —</option>'; els.size.disabled=true; els.fun.innerHTML='<option value="">— Select —</option>'; els.fun.disabled=true; els.run.innerHTML='<option value="">— Select —</option>'; els.run.disabled=true; els.file.innerHTML='<option value="">— Select —</option>'; els.file.disabled=true; [els.down,els.downpng].forEach(e=>e.disabled=true); });
els.mat.addEventListener('change', ()=>{ if(els.mat.value){ populateSizes(); els.size.disabled=false; } else { els.size.innerHTML='<option value="">— Select —</option>'; els.size.disabled=true; } els.fun.innerHTML='<option value="">— Select —</option>'; els.fun.disabled=true; els.run.innerHTML='<option value="">— Select —</option>'; els.run.disabled=true; els.file.innerHTML='<option value="">— Select —</option>'; els.file.disabled=true; [els.down,els.downpng].forEach(e=>e.disabled=true); });
els.size.addEventListener('change', ()=>{ if(els.size.value){ populateFunctionals(); els.fun.disabled=false; } else { els.fun.innerHTML='<option value="">— Select —</option>'; els.fun.disabled=true; } els.run.innerHTML='<option value="">— Select —</option>'; els.run.disabled=true; els.file.innerHTML='<option value="">— Select —</option>'; els.file.disabled=true; [els.down,els.downpng].forEach(e=>e.disabled=true); });
els.fun.addEventListener('change', ()=>{ if(els.fun.value){ populateRunTypes(); els.run.disabled=false; } else { els.run.innerHTML='<option value="">— Select —</option>'; els.run.disabled=true; } els.file.innerHTML='<option value="">— Select —</option>'; els.file.disabled=true; [els.down,els.downpng].forEach(e=>e.disabled=true); });
els.run.addEventListener('change', ()=>{ if(els.run.value) populateFileList(); });
els.file.addEventListener('change', ()=>{ if(els.file.value) loadXYZ(els.file.value); });

// ---- details + load
function renderDetails(meta,file){
  const sizeText = meta.size!=null ? `${meta.size} nm` : 'N/A';
  els.details.innerHTML = `
    <div class="space-y-2">
      <div class="text-sm"><span class="font-semibold mr-1">System:</span>${meta.system_type||'N/A'}</div>
      <div class="text-sm"><span class="font-semibold mr-1">Material:</span>${meta.material||'N/A'}</div>
      <div class="text-sm"><span class="font-semibold mr-1">Size:</span><span class="font-mono">${sizeText}</span></div>
      <div class="text-sm"><span class="font-semibold mr-1">DFT functional:</span>${meta.functional||'N/A'}</div>
      <div class="text-sm"><span class="font-semibold mr-1">Basis:</span>${meta.basis||'N/A'}</div>
      <div class="text-sm"><span class="font-semibold mr-1">Code:</span>${meta.code||'N/A'}</div>
      <div class="text-sm"><span class="font-semibold mr-1">Run type:</span>${meta.run_type||'N/A'}</div>
      <div class="text-xs text-slate-500">${meta.filename || file}</div>
    </div>`;
  renderRatios(meta.ratios || {});
}

function loadXYZ(file){
  currentFile=file;
  fetch(`./${file}`).then(r=>{ if(!r.ok) throw new Error('File not found'); return r.text();})
  .then(data=>{
    const meta=metadata[file]||{};
    currentMeta = meta;

    atomColors = {}; Object.keys(meta.stoichiometry || {}).forEach(el=> atomColors[el]=jmolHex(el));

    let first = data;
    if (meta.run_type==='Molecular Dynamics'){
      const lines=data.split('\n'); const n=parseInt(lines[0]?.trim()); first = lines.slice(0,n+2).join('\n');
    }
    currentXYZText=first;

    els.viewer.innerHTML='';
    viewer=$3Dmol.createViewer(els.viewer,{backgroundColor:'white'});

    if(meta.run_type==='Molecular Dynamics' && viewer.addModelsAsFrames){
      viewer.addModelsAsFrames(data,'xyz');
      setupTrajectoryControls();
    } else {
      viewer.addModel(first,'xyz');
      els.traj.classList.add('hidden'); els.traj.innerHTML='';
    }

    document.querySelector('input[name="style-radio"][value="sphere"]').checked=true;
    applyStyle();
    renderDetails(meta,file);
    updateStoichiometry(meta);
    viewer.zoomTo(); viewer.render();

    if (els.runCat) els.runCat.disabled = false;
  })
  .catch(err=>{
    console.error(err);
    els.viewer.innerHTML='<div class="p-4 text-sm text-red-600">Error loading file.</div>';
    els.details.innerHTML=''; els.ratios.innerHTML='';
    els.traj.classList.add('hidden'); els.traj.innerHTML='';
  });
}

// ---- downloads/reset
els.down?.addEventListener('click', ()=>{ if(!currentFile) return; const a=document.createElement('a'); a.href=`./${currentFile}`; a.download='structure.xyz'; document.body.appendChild(a); a.click(); a.remove();});
els.downpng?.addEventListener('click', ()=>{ if(!viewer) return; viewer.render(); const uri=viewer.pngURI(); downloadDataURL(uri,'structure.png');});
els.reset?.addEventListener('click', ()=> window.location.reload());

// ---- miniCAT UI
function mkRow(smiles = '', ratio = '') {
  const row = document.createElement('div');
  row.className = 'grid grid-cols-1 md:grid-cols-3 gap-2';
  row.innerHTML = `
    <label class="text-sm">SMILES
      <input type="text" class="input lig-smiles" value="" placeholder="Ligand SMILES">
    </label>
    <label class="text-sm">Ratio
      <input type="number" step="0.1" min="0" class="input lig-ratio" value="${ratio}" placeholder="ratio of Ligand">
    </label>
    <div class="flex items-end">
      <button class="px-3 py-2 rounded bg-red-100 text-red-700 hover:bg-red-200 rm">Remove</button>
    </div>`;
  row.querySelector('.rm').onclick = () => row.remove();
  return row;
}
function getMode(name){
  const r=document.querySelector(`input[name="${name}"]:checked`);
  return r ? r.value : 'random';
}
function collectJob(rowsId, dummyId, modeName){
  const rows = [...document.getElementById(rowsId).querySelectorAll('.grid')];
  if (!rows.length) return null;
  const ligs   = rows.map(r => r.querySelector('.lig-smiles').value.trim()).filter(Boolean);
  const ratios = rows.map(r => parseFloat(r.querySelector('.lig-ratio').value)).filter(v => !Number.isNaN(v));
  if (ligs.length !== ratios.length) return { error: 'Ratio/ligand count mismatch' };
  const sum = ratios.reduce((a,b)=>a+b,0);
  if (sum <= 0)          return { error: 'Ratios must sum > 0' };
  if (sum > 1 + 1e-6)    return { error: `Ratios sum must be ≤ 1.0 (got ${sum.toFixed(3)})` };
  const norm = ratios.map(v => v / sum);
  const mode = getMode(modeName);
  const dist = `${norm.map(v=>v.toFixed(3)).join(':')}:${mode}`;
  return { ligands: ligs, dummy: document.getElementById(dummyId).value.trim(), dist };
}
// init rows
if (els.anRows && els.anAdd){
  els.anAdd.onclick = ()=> els.anRows.appendChild(mkRow());
}

// terminal helpers
function tclear(){ if(els.term) els.term.textContent=''; }
function tlog(line=''){ if(els.term){ els.term.textContent += line + '\n'; els.term.scrollTop = els.term.scrollHeight; } }

els.runCat?.addEventListener('click', ()=>{
  if (!viewer || !currentFile) return;

  const anJob = collectJob('an_rows','an_dummy','an_mode');
  if (anJob?.error){
    const msg = 'Error: ' + anJob.error;
    els.catStatus.textContent = msg;
    window.alert(msg);        // popup
    return;
  }
  if (!anJob){
    const msg = 'Error: add at least one ligand row.';
    els.catStatus.textContent = msg;
    window.alert(msg);
    return;
  }
  const body = {
    xyztext: currentXYZText,
    out_prefix: autoPrefix(currentMeta || {}),
    jobs: [anJob]
  };

  els.catStatus.textContent = 'Running miniCAT…';
  els.runCat.disabled = true;
  tclear(); tlog('Preparing command…');

  fetch(CAT_ATTACH, {
    method: 'POST',
    headers: {'Content-Type':'application/json'},
    body: JSON.stringify(body)
  })
  .then(async r => { const data = await r.json().catch(()=>null); if(!r.ok) throw (data||{detail:`HTTP ${r.status}`}); return data; })
  .then(resp => {
    if (resp.cmd)    tlog(`$ ${resp.cmd}`);
    if (resp.stdout) { tlog('\n[stdout]'); tlog(resp.stdout.trim()); }
    if (resp.stderr) { tlog('\n[stderr]'); tlog(resp.stderr.trim()); }

    if (!resp.results?.length) { els.catStatus.textContent = 'No structures returned.'; return; }

    els.catSelect.innerHTML = '<option value="">— choose —</option>';
    resp.results.forEach((e,i)=>{ const o=document.createElement('option'); o.value=i; o.text=e.filename; els.catSelect.appendChild(o); });

    const show=i=>{ const e=resp.results[i]; if(!e) return; loadCATResult(e); els.catDownload.disabled=false; els.catDownload.onclick=()=>downloadBlob(e.xyz,e.filename,'chemical/x-xyz'); };
    show(0);
    els.catSelect.disabled = false;
    els.catStatus.textContent = resp.message || `Returned ${resp.results.length} file(s)`;
  })
  .catch(err => {
    const msg = (err.detail || err.message || String(err));
    els.catStatus.textContent = 'Error: ' + msg;
    tlog('\n[error] ' + msg);
  })
  .finally(()=> els.runCat.disabled = false);
});

// render CAT result
function loadCATResult(entry){
  els.viewer.innerHTML = "";
  viewer = $3Dmol.createViewer(els.viewer, { backgroundColor: "white" });
  viewer.addModel(entry.xyz, "xyz");
  applyStyle();
  viewer.zoomTo();
  viewer.render();

  const lines = entry.xyz.split("\n");
  let nAtoms = parseInt(lines[0].trim()) || 0;
  const sto = {}; let start=2;
  for (let i=0;i<nAtoms && start+i<lines.length;i++){
    const t=lines[start+i].trim().split(/\s+/); if(t.length>=4){ const el=t[0]; sto[el]=(sto[el]||0)+1; }
  }
  els.details.innerHTML = `
    <div class="space-y-2">
      <div class="text-sm"><span class="font-semibold mr-1">Filename:</span>${entry.filename}</div>
      <div class="text-sm"><span class="font-semibold mr-1">Total atoms:</span>${nAtoms}</div>
      <div class="text-sm"><span class="font-semibold mr-1">Stoichiometry:</span>${Object.entries(sto).map(([e,c])=>`${e} (${c})`).join(', ')||'N/A'}</div>
    </div>`;
  updateStoichiometry({stoichiometry:sto});
}
// ---- Reset miniCAT process
function resetMiniCAT(){
  els.anRows.innerHTML = '';
  els.catStatus.textContent = 'Add ligands and select a QD.';
  els.catSelect.innerHTML = '<option value="">— none —</option>';
  els.catSelect.disabled = true;
  els.catDownload.disabled = true;
  tclear();
  els.runCat.disabled = !currentFile;
}
els.resetCat?.addEventListener('click', resetMiniCAT);

// ---- boot
fetch('metadata.json').then(r=>r.json()).then(d=>{ metadata=d; populateSystemTypes();}).catch(()=>console.warn('metadata.json missing'));

