#!/usr/bin/env python3
"""
Interactive Plotly visualizer for Fuzzy + PDOS + COOP exports.

Inputs (from your Matplotlib pipeline):
  - fuzzy_data.npz  : centres, intensity, tick_positions, tick_labels, labels, extent, ewin
  - pdos_data.csv   : Energy_eV, <cumulative PDOS columns> (Ycum by symbol order)
  - coop_data.csv   : MO_Energy_eV, <pair1>, <pair2>, ...

Example:
  python plot_interactive.py \
      --fuzzy fuzzy_data.npz \
      --pdos  pdos_data.csv \
      --coop  coop_data.csv \
      --out   fuzzy_pdos_coop_interactive.html \
      --normalize-coop \
      --ef 0.0
"""

import argparse
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots


# ----------------------------- I/O helpers -----------------------------

def load_fuzzy(npz_path):
    d = np.load(npz_path, allow_pickle=True)
    centres = np.asarray(d["centres"], dtype=float)              # (nE,)
    Z = np.asarray(d["intensity"], dtype=float)                  # (nE, nK)
    tick_positions = np.asarray(d.get("tick_positions", np.arange(Z.shape[1])), dtype=float)
    tick_labels = [str(x) for x in d.get("tick_labels", np.arange(Z.shape[1]))]
    labels = [str(x) for x in d.get("labels", [])]
    extent = np.asarray(
        d.get("extent", [0.0, float(Z.shape[1]-1), float(centres.min()), float(centres.max())]),
        dtype=float
    )
    ewin = np.asarray(d.get("ewin", [float(centres.min()), float(centres.max())]), dtype=float)
    return dict(centres=centres, Z=Z,
                tick_positions=tick_positions, tick_labels=tick_labels,
                labels=labels, extent=extent, ewin=ewin)


def load_pdos_csv(csv_path):
    df = pd.read_csv(csv_path)
    energy = df.iloc[:, 0].to_numpy(dtype=float)  # Energy_eV
    labels = list(df.columns[1:])                 # cumulative columns (Ycum)
    Ycum = df.iloc[:, 1:].to_numpy(dtype=float)   # (nE, nCurves)
    return energy, labels, Ycum


def load_coop_csv(csv_path):
    df = pd.read_csv(csv_path)
    Ener = df.iloc[:, 0].to_numpy(dtype=float)     # MO_Energy_eV
    pairs = list(df.columns[1:])
    values = {p: df[p].to_numpy(dtype=float) for p in pairs}
    return Ener, pairs, values


# ----------------------------- plotting core -----------------------------

def build_combined_figure(
    fuzzy, pdos_energy, pdos_labels, pdos_Ycum,
    coop_energy, coop_pairs, coop_values,
    ef=None, normalize_coop=False, title="Fuzzy Band Map"
):
    centres = fuzzy["centres"]   # energy axis (y)
    Z = fuzzy["Z"]               # (nE, nK)
    ewin = fuzzy["ewin"]
    kmin, kmax = float(fuzzy["extent"][0]), float(fuzzy["extent"][1])
    nK = Z.shape[1]
    kx = np.linspace(kmin, kmax, nK)              # k-path distance axis

    # Map tick_positions to k-distance if they look like indices
    tpos = np.asarray(fuzzy["tick_positions"], dtype=float)
    if tpos.size and (tpos.max() <= nK + 1.5) and nK > 1:
        scale = (kmax - kmin) / (nK - 1)
        tpos_plot = kmin + tpos * scale
    else:
        tpos_plot = tpos
    tlabels = fuzzy["tick_labels"]

    # Figure scaffold: 3 columns (fuzzy | PDOS | COOP)
    fig = make_subplots(
        rows=1, cols=3, shared_yaxes=True,
        column_widths=[0.6, 0.2, 0.2],
        horizontal_spacing=0.06,
        specs=[[{"type": "heatmap"}, {"type": "xy"}, {"type": "xy"}]],
        subplot_titles=(title, "Stacked PDOS", "COOP sticks"),
    )

    # keep global figure backgrounds white
    fig.update_layout(template="plotly_white",
                      paper_bgcolor="white", plot_bgcolor="white")

    # ---------------- Fuzzy heatmap (Inferno, robust log, black bg) ----------------
    # robust log normalization (like your Matplotlib)
    Zpos = Z[Z > 1e-9]
    vmax = np.percentile(Z, 99.8)
    vmin = max(np.percentile(Zpos, 5), vmax / 1e4) if Zpos.size else vmax / 1e4

    Zm = Z.copy()
    Zm[Zm <= 0] = np.nan
    Zm[Zm < vmin] = np.nan

    # draw a black rectangle behind fuzzy panel only (use domain refs for col=1)
    fig.add_shape(
        type="rect",
        xref="x domain", yref="y domain",
        x0=0, x1=1, y0=0, y1=1,
        fillcolor="black", line=dict(width=0), layer="below"
    )

    heat = go.Heatmap(
        z=np.log10(Zm), x=kx, y=centres,
        colorscale="Inferno",
        zmin=np.log10(vmin), zmax=np.log10(vmax),
        colorbar=dict(title="log10 Intensity"),
        hovertemplate="k=%{x:.3f} Å⁻¹<br>E=%{y:.3f} eV<br>log10(I)=%{z:.2f}<extra></extra>",
    )
    fig.add_trace(heat, row=1, col=1)

    # axes & HS separators for fuzzy (axis text visible in white margin)
    fig.update_yaxes(
        title_text="Energy (eV)",
        title_font=dict(color="black"),
        range=[ewin[0], ewin[1]],
        showticklabels=True, ticks="outside",
        tickfont=dict(color="black"),
        row=1, col=1
    )
    fig.update_xaxes(
        title_text="High-Symmetry k-Path",
        title_font=dict(color="black"),
        showticklabels=True, ticks="outside",
        tickfont=dict(color="black"),
        row=1, col=1
    )
    if tpos_plot.size:
        for x in tpos_plot:
            fig.add_vline(x=float(x), line_color="rgba(200,200,200,0.6)", line_width=1, row=1, col=1)
        fig.update_xaxes(
            tickmode="array",
            tickvals=[float(x) for x in tpos_plot],
            ticktext=tlabels,
            row=1, col=1
        )

    # optional Fermi line on fuzzy (white for contrast)
    if ef is not None:
        fig.add_hline(y=float(ef), line_dash="dash", line_color="white", line_width=2, row=1, col=1)

    # ---------------- PDOS stacked area (from cumulative Ycum) ----------------
    # Interpolate to fuzzy centres if needed
    if not np.array_equal(pdos_energy, centres):
        Ycum_use = np.empty((centres.size, pdos_Ycum.shape[1]), dtype=float)
        for j in range(pdos_Ycum.shape[1]):
            Ycum_use[:, j] = np.interp(centres, pdos_energy, pdos_Ycum[:, j])
    else:
        Ycum_use = pdos_Ycum

    # colorway (Plotly default qualitative)
    palette = (go.Figure().layout.template.layout.colorway
               or ["#636EFA","#EF553B","#00CC96","#AB63FA","#FFA15A",
                   "#19D3F3","#FF6692","#B6E880","#FF97FF","#FECB52"])

    # Stack: each curve is the cumulative Ycum column with fill
    for j, lab in enumerate(pdos_labels):
        ycum = Ycum_use[:, j]
        fig.add_trace(
            go.Scatter(
                x=ycum, y=centres,
                mode="lines",
                line=dict(width=0.5, color="rgba(0,0,0,0)"),
                fill="tonextx" if j > 0 else "tozerox",
                fillcolor=palette[j % len(palette)],
                name=lab,
                hovertemplate=f"{lab}: %{x:.3f}<br>E=%{{y:.3f}} eV<extra></extra>",
            ),
            row=1, col=2
        )

    # Black total DOS = last cumulative column
    if Ycum_use.shape[1] > 0:
        total = Ycum_use[:, -1]
        fig.add_trace(
            go.Scatter(
                x=total, y=centres, mode="lines",
                line=dict(color="black", width=2),
                name="Total DOS",
                hovertemplate="Total: %{x:.3f}<br>E=%{y:.3f} eV<extra></extra>",
            ),
            row=1, col=2
        )
        xmax = float(max(total.max(), 1e-12)) * 1.05
        fig.update_xaxes(range=[0, xmax], row=1, col=2)

    # PDOS axes
    fig.update_xaxes(
        title_text="DOS (a.u.)",
        title_font=dict(color="black"),
        showticklabels=True, ticks="outside",
        tickfont=dict(color="black"),
        row=1, col=2
    )
    fig.update_yaxes(
        title_text="Energy (eV)",
        title_font=dict(color="black"),
        range=[ewin[0], ewin[1]],
        showticklabels=True, ticks="outside",
        tickfont=dict(color="black"),
        row=1, col=2
    )

    if ef is not None:
        fig.add_hline(y=float(ef), line_dash="dash", line_color="black", line_width=1.5, row=1, col=2)

    # ---------------- COOP sticks (as line segments), optional normalization ----------------
    coop_mask = (coop_energy >= ewin[0]) & (coop_energy <= ewin[1])
    Ener = coop_energy[coop_mask]

    # If no sticks fall in the window, expand y-range to include them
    if Ener.size == 0 and coop_energy.size:
        e_lo = float(min(ewin[0], np.nanmin(coop_energy)))
        e_hi = float(max(ewin[1], np.nanmax(coop_energy)))
        for c in (1, 2, 3):
            fig.update_yaxes(range=[e_lo, e_hi], row=1, col=c)
        coop_mask = (coop_energy >= e_lo) & (coop_energy <= e_hi)
        Ener = coop_energy[coop_mask]

    scale = 1.0
    if normalize_coop:
        gmax = 0.0
        for p in coop_pairs:
            v = coop_values[p][coop_mask]
            if v.size:
                gmax = max(gmax, float(np.max(np.abs(v))))
        scale = (1.0 / gmax) if gmax > 0 else 1.0

    pair_colors = {p: palette[i % len(palette)] for i, p in enumerate(coop_pairs)}

    # Draw each pair as one Scattergl trace composed of many small horizontal segments
    for p in coop_pairs:
        v = coop_values[p][coop_mask] * scale
        if v.size == 0:
            continue
        xs, ys = [], []
        for yi, xv in zip(Ener, v):
            xs.extend([0.0, xv, None])     # None splits segments
            ys.extend([yi,  yi, None])
        fig.add_trace(
            go.Scattergl(
                x=xs, y=ys, mode="lines",
                line=dict(color=pair_colors[p], width=2),
                name=p,
                hoverinfo="skip",
            ),
            row=1, col=3
        )

    # COOP axes + range
    if normalize_coop:
        fig.update_xaxes(range=[-1.05, 1.05], title_text="COOP (normalized)",
                         title_font=dict(color="black"), row=1, col=3)
    else:
        fig.update_xaxes(title_text="COOP (a.u.)",
                         title_font=dict(color="black"), row=1, col=3)
    fig.update_yaxes(
        title_text="Energy (eV)",
        title_font=dict(color="black"),
        showticklabels=True, ticks="outside",
        tickfont=dict(color="black"),
        row=1, col=3
    )

    if ef is not None:
        fig.add_hline(y=float(ef), line_dash="dash", line_color="black", line_width=1.5, row=1, col=3)

    # Force y-axis ticks/titles on all three panels (even with shared_yaxes)
    for c in (1, 2, 3):
        fig.update_yaxes(
            title_text="Energy (eV)",
            title_font=dict(color="black"),
            range=[ewin[0], ewin[1]],
            showticklabels=True, ticks="outside",
            tickfont=dict(color="black"),
            row=1, col=c
        )

    # ---------------- global layout ----------------
    fig.update_layout(
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0.0),
        margin=dict(l=80, r=40, t=60, b=70),
        height=800,
    )

    return fig


# ----------------------------- CLI -----------------------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fuzzy", required=True, help="Path to fuzzy_data.npz")
    ap.add_argument("--pdos",  required=True, help="Path to pdos_data.csv")
    ap.add_argument("--coop",  required=True, help="Path to coop_data.csv")
    ap.add_argument("--out",   default="fuzzy_pdos_coop_interactive.html", help="Output HTML")
    ap.add_argument("--normalize-coop", action="store_true", help="Normalize COOP to [-1,1]")
    ap.add_argument("--ef", type=float, default=None, help="Fermi/midgap energy for dashed line")
    ap.add_argument("--title", type=str, default="Fuzzy Band Map", help="Title for fuzzy panel")
    args = ap.parse_args()

    fuzzy = load_fuzzy(args.fuzzy)
    pdos_energy, pdos_labels, pdos_Ycum = load_pdos_csv(args.pdos)
    coop_energy, coop_pairs, coop_values = load_coop_csv(args.coop)

    fig = build_combined_figure(
        fuzzy, pdos_energy, pdos_labels, pdos_Ycum,
        coop_energy, coop_pairs, coop_values,
        ef=args.ef, normalize_coop=args.normalize_coop,
        title=args.title
    )
    fig.write_html(args.out, include_plotlyjs="cdn", full_html=True)
    print(f"✓ Wrote interactive HTML → {args.out}")


if __name__ == "__main__":
    main()

