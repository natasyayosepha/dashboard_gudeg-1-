from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

# ----------------------------------------------------------------------------
# Konfigurasi dasar
# ----------------------------------------------------------------------------
DATA_FILE = "Data_Simulasi_Penjualan_Gudeg_Jogja_2025.xlsx"
SHEET = "Data_Penjualan"
SOURCE = "Data Simulasi Penjualan Gudeg Sekar Arum, Yogyakarta, 2025 (4.380 baris), diolah kelompok"

ORANGE = "#E8710A"   # Malioboro (selalu oranye, sama seperti Fase 3)
BLUE = "#1F5FA8"     # outlet lain
GREY = "#8A8F98"
INK = "#1F2933"
KANAL_COLORS = {
    "Makan di tempat": "#1F5FA8",
    "Bawa pulang": "#7FA8D6",
    "Pesan antar online": "#B8BEC6",
}
OUTLET_ORDER = ["Malioboro", "Wijilan", "Kaliurang", "Godean"]
BULAN_ID = ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des"]
FONT = dict(family="Calibri, Arial, sans-serif", size=14, color=INK)

st.set_page_config(page_title="Dashboard Kepuasan Pelanggan - Gudeg Sekar Arum", layout="wide")

st.markdown(
    """
    <style>
      .block-container {padding-top: 1.2rem; padding-bottom: 1rem; max-width: 1400px;}
      .kpi {border:1px solid #D9DEE5; border-radius:8px; padding:12px 16px; background:#FFFFFF;}
      .kpi .lbl {font-size:0.85rem; color:#52606D; margin-bottom:2px;}
      .kpi .val {font-size:1.9rem; font-weight:700; color:#1F2933; line-height:1.2;}
      .kpi .sub {font-size:0.8rem; color:#7B8794;}
      .foot {font-size:0.8rem; color:#52606D;}
    </style>
    """,
    unsafe_allow_html=True,
)


# ----------------------------------------------------------------------------
# Data
# ----------------------------------------------------------------------------
def weighted_rating(df: pd.DataFrame) -> float:
    """Rating berbobot = sum(rating x ulasan) / sum(ulasan); baris tanpa ulasan tidak dihitung."""
    d = df[df["Jumlah_Ulasan"] > 0]
    total = d["Jumlah_Ulasan"].sum()
    if total == 0:
        return np.nan
    return float((d["Rating_Rata_rata"] * d["Jumlah_Ulasan"]).sum() / total)


def group_weighted(df: pd.DataFrame, by) -> pd.DataFrame:
    d = df[df["Jumlah_Ulasan"] > 0].copy()
    d["_rw"] = d["Rating_Rata_rata"] * d["Jumlah_Ulasan"]
    g = d.groupby(by, observed=True).agg(rw=("_rw", "sum"), ul=("Jumlah_Ulasan", "sum")).reset_index()
    g["Rating"] = g["rw"] / g["ul"]
    return g


@st.cache_data(show_spinner=False)
def load_data(source) -> pd.DataFrame:
    df = pd.read_excel(source, sheet_name=SHEET)
    df["Tanggal"] = pd.to_datetime(df["Tanggal"])
    df["BulanNo"] = df["Tanggal"].dt.month
    # Omzet_Bersih_Rp berisi rumus Excel; jika nilai tersimpan kosong, hitung ulang
    hitung = df["Omzet_Gudeg_Rp"] + df["Omzet_Oleh_Oleh_Rp"] - df["Diskon_Rp"]
    if "Omzet_Bersih_Rp" not in df or df["Omzet_Bersih_Rp"].isna().any():
        df["Omzet_Bersih_Rp"] = df.get("Omzet_Bersih_Rp", pd.Series(index=df.index, dtype=float)).fillna(hitung)
    df["Rating_Rata_rata"] = pd.to_numeric(df["Rating_Rata_rata"], errors="coerce")
    return df


def rupiah(x: float) -> str:
    """Rp9,27 miliar / Rp125,4 juta / Rp2.117.257 (format Indonesia)."""
    if x >= 1e9:
        return f"Rp{x / 1e9:,.2f} miliar".replace(",", "X").replace(".", ",").replace("X", ".")
    if x >= 1e6:
        return f"Rp{x / 1e6:,.1f} juta".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"Rp{x:,.0f}".replace(",", ".")


def angka(x: float) -> str:
    return f"{x:,.0f}".replace(",", ".")


def dec(x: float, n: int = 2) -> str:
    return f"{x:,.{n}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def warna_outlet(o: str) -> str:
    return ORANGE if o == "Malioboro" else BLUE


def style(fig: go.Figure, height: int = 340, **kw) -> go.Figure:
    opsi = dict(font=FONT, height=height, margin=dict(l=10, r=20, t=10, b=10),
                plot_bgcolor="white", paper_bgcolor="white", showlegend=False)
    opsi.update(kw)
    fig.update_layout(**opsi)
    return fig


def kartu(col, label, value, sub=""):
    col.markdown(
        f'<div class="kpi"><div class="lbl">{label}</div><div class="val">{value}</div>'
        f'<div class="sub">{sub}</div></div>',
        unsafe_allow_html=True,
    )


# ----------------------------------------------------------------------------
# Muat data
# ----------------------------------------------------------------------------
path = Path(__file__).with_name(DATA_FILE)
upload = None
if not path.exists():
    upload = st.sidebar.file_uploader("Unggah berkas data (.xlsx)", type="xlsx")
    if upload is None:
        st.title("Dashboard Kepuasan Pelanggan - Gudeg Sekar Arum 2025")
        st.info(f"Letakkan **{DATA_FILE}** di folder yang sama dengan app.py, atau unggah lewat sidebar.")
        st.stop()
df = load_data(upload if upload is not None else path)

# ----------------------------------------------------------------------------
# Judul dan petunjuk
# ----------------------------------------------------------------------------
st.title("Kepuasan Pelanggan Gudeg Sekar Arum, 2025")
st.caption(
    "Untuk Tim layanan pelanggan: di mana dan kapan rating ulasan berbeda? "
    "Gunakan filter di sebelah kiri; semua angka dan grafik ikut berubah. "
    "Oranye selalu menandai Malioboro."
)

# ----------------------------------------------------------------------------
# Filter (sidebar): Outlet, Kanal, Jenis hari, Rentang bulan
# ----------------------------------------------------------------------------
st.sidebar.header("Filter")
outlets_all = [o for o in OUTLET_ORDER if o in df["Outlet"].unique()] or sorted(df["Outlet"].unique())
kanal_all = list(KANAL_COLORS) if set(KANAL_COLORS) <= set(df["Kanal_Penjualan"].unique()) else sorted(df["Kanal_Penjualan"].unique())
hari_all = list(df["Jenis_Hari"].dropna().unique())

f_outlet = st.sidebar.multiselect("Outlet", outlets_all, default=outlets_all)
f_kanal = st.sidebar.multiselect("Kanal penjualan", kanal_all, default=kanal_all)
f_hari = st.sidebar.multiselect("Jenis hari", hari_all, default=hari_all)
b1, b2 = st.sidebar.select_slider(
    "Rentang bulan", options=list(range(1, 13)), value=(1, 12), format_func=lambda m: BULAN_ID[m - 1]
)
st.sidebar.markdown("---")
st.sidebar.caption(
    "Petunjuk singkat: pilih outlet atau kanal di atas, geser rentang bulan, lalu baca judul "
    "setiap grafik. Rating selalu berbobot (dihitung dari jumlah ulasan)."
)

f = df[
    df["Outlet"].isin(f_outlet)
    & df["Kanal_Penjualan"].isin(f_kanal)
    & df["Jenis_Hari"].isin(f_hari)
    & df["BulanNo"].between(b1, b2)
]
if f.empty:
    st.warning("Tidak ada data untuk kombinasi filter ini. Longgarkan filter di sebelah kiri.")
    st.stop()

# ----------------------------------------------------------------------------
# Kartu KPI
# ----------------------------------------------------------------------------
omzet = f["Omzet_Bersih_Rp"].sum()
trx = f["Jumlah_Transaksi"].sum()
avg_trx = omzet / trx if trx else 0
rating = weighted_rating(f)
ulasan = int(f["Jumlah_Ulasan"].sum())
rating_all = weighted_rating(df)

k1, k2, k3, k4 = st.columns(4)
kartu(k1, "Omzet bersih", rupiah(omzet), "omzet gudeg + oleh-oleh - diskon")
kartu(k2, "Jumlah transaksi", angka(trx), "seluruh outlet dan kanal terpilih")
kartu(k3, "Rata-rata nilai transaksi", rupiah(avg_trx), "omzet bersih / jumlah transaksi")
sel = "" if np.isnan(rating) else f"rata-rata usaha {dec(rating_all, 2)}"
kartu(k4, "Rating berbobot", "-" if np.isnan(rating) else f"{dec(rating, 2)} / 5", f"dari {angka(ulasan)} ulasan; {sel}")
st.write("")

# ----------------------------------------------------------------------------
# Baris 1: tren omzet + perbandingan outlet x kanal
# ----------------------------------------------------------------------------
c1, c2 = st.columns([3, 2])

with c1:
    st.subheader("Tren omzet bersih per bulan")
    m = f.groupby("BulanNo")["Omzet_Bersih_Rp"].sum().reindex(range(b1, b2 + 1), fill_value=0) / 1e6
    puncak = m.idxmax()
    fig = go.Figure(go.Scatter(
        x=[BULAN_ID[i - 1] for i in m.index], y=m.values, mode="lines+markers",
        line=dict(color=BLUE, width=3), marker=dict(size=7),
        hovertemplate="%{x}: Rp%{y:,.0f} juta<extra></extra>",
    ))
    fig.add_annotation(x=BULAN_ID[puncak - 1], y=m[puncak], text=f"Puncak: {BULAN_ID[puncak - 1]}",
                       showarrow=True, arrowhead=0, ay=-30, font=dict(color=INK))
    fig.update_yaxes(title="Omzet bersih (Rp juta)", rangemode="tozero", gridcolor="#EEF1F4")
    fig.update_xaxes(showgrid=False)
    st.plotly_chart(style(fig), width='stretch', theme=None)

with c2:
    st.subheader("Omzet bersih per outlet dan kanal")
    pv = f.pivot_table(index="Outlet", columns="Kanal_Penjualan", values="Omzet_Bersih_Rp", aggfunc="sum", fill_value=0) / 1e9
    pv = pv.loc[pv.sum(axis=1).sort_values().index]
    fig = go.Figure()
    for k in [c for c in KANAL_COLORS if c in pv.columns]:
        fig.add_bar(y=pv.index, x=pv[k], name=k, orientation="h", marker_color=KANAL_COLORS[k],
                    hovertemplate="%{y} - " + k + ": Rp%{x:,.2f} miliar<extra></extra>")
    for o, t in pv.sum(axis=1).items():
        fig.add_annotation(x=t, y=o, text=f" {dec(t, 2)}", showarrow=False, xanchor="left")
    fig.update_layout(barmode="stack", showlegend=True, legend=dict(orientation="h", y=1.12, x=0))
    fig.update_xaxes(title="Omzet bersih (Rp miliar)", rangemode="tozero", gridcolor="#EEF1F4")
    fig.update_yaxes(showgrid=False)
    st.plotly_chart(style(fig).update_layout(showlegend=True), width='stretch', theme=None)

# ----------------------------------------------------------------------------
# Baris 2: rating per outlet (dot plot) + heatmap outlet x jenis hari
# ----------------------------------------------------------------------------
c3, c4 = st.columns(2)

with c3:
    st.subheader("Rating berbobot per outlet")
    g = group_weighted(f, "Outlet").sort_values("Rating")
    fig = go.Figure()
    fig.add_vline(x=rating_all, line_dash="dash", line_color=GREY,
                  annotation_text=f"Rata-rata usaha {dec(rating_all, 2)}", annotation_position="top")
    fig.add_trace(go.Scatter(
        x=g["Rating"], y=g["Outlet"], mode="markers+text",
        marker=dict(size=16, color=[warna_outlet(o) for o in g["Outlet"]]),
        text=[dec(r, 2) for r in g["Rating"]], textposition="middle right",
        customdata=g["ul"], hovertemplate="%{y}: %{x:.2f} (%{customdata:,.0f} ulasan)<extra></extra>",
    ))
    fig.update_xaxes(title="Rating berbobot (sumbu mulai 4,0)", range=[4.0, 4.8], gridcolor="#EEF1F4")
    fig.update_yaxes(showgrid=False)
    st.plotly_chart(style(fig), width='stretch', theme=None)

with c4:
    st.subheader("Rating menurut jenis hari")
    h = group_weighted(f, ["Outlet", "Jenis_Hari"])
    mat = h.pivot(index="Outlet", columns="Jenis_Hari", values="Rating")
    mat = mat.reindex(index=[o for o in OUTLET_ORDER if o in mat.index], columns=[c for c in hari_all if c in mat.columns])
    fig = go.Figure(go.Heatmap(
        z=mat.values, x=mat.columns, y=mat.index, colorscale="Blues", zmin=3.9, zmax=4.7,
        text=[[("" if np.isnan(v) else dec(v, 2)) for v in row] for row in mat.values],
        texttemplate="%{text}", textfont=dict(size=16), showscale=False,
        hovertemplate="%{y} - %{x}: %{z:.2f}<extra></extra>",
    ))
    fig.update_yaxes(autorange="reversed")
    st.plotly_chart(style(fig), width='stretch', theme=None)

# ----------------------------------------------------------------------------
# Baris 3: distribusi rating harian + keandalan rating
# ----------------------------------------------------------------------------
c5, c6 = st.columns(2)

with c5:
    st.subheader("Seberapa sering rating harian di bawah 4,0")
    d = f[f["Jumlah_Ulasan"] > 0]
    outs = [o for o in OUTLET_ORDER if o in d["Outlet"].unique()]
    if outs:
        fig = make_subplots(rows=1, cols=len(outs), shared_yaxes=True, subplot_titles=outs, horizontal_spacing=0.02)
        bins = np.arange(3.0, 5.01, 0.25)
        for i, o in enumerate(outs, start=1):
            r = d.loc[d["Outlet"] == o, "Rating_Rata_rata"]
            cnt, _ = np.histogram(r, bins=bins)
            pct = cnt / max(len(r), 1) * 100
            low = (r < 4.0).mean() * 100
            fig.add_bar(x=bins[:-1] + 0.125, y=pct, width=0.23, marker_color=warna_outlet(o), row=1, col=i,
                        hovertemplate="rating %{x:.2f}: %{y:.1f}% baris<extra></extra>")
            fig.add_vline(x=4.0, line_dash="dash", line_color=GREY, row=1, col=i)
            fig.layout.annotations[i - 1].update(text=f"{o}<br><sub>{dec(low, 1)}% di bawah 4,0</sub>")
            fig.update_xaxes(range=[3, 5], tickvals=[3, 4, 5], row=1, col=i)
        fig.update_yaxes(title="% baris", rangemode="tozero", gridcolor="#EEF1F4", col=1)
        st.plotly_chart(style(fig, margin=dict(l=10, r=10, t=50, b=10)), width='stretch', theme=None)
    else:
        st.info("Tidak ada ulasan pada filter ini.")

with c6:
    st.subheader("Keandalan rating: ulasan per 100 transaksi")
    a = f.groupby(["Outlet", "Kanal_Penjualan"]).agg(u=("Jumlah_Ulasan", "sum"), t=("Jumlah_Transaksi", "sum")).reset_index()
    a["rasio"] = a["u"] / a["t"] * 100
    zr = a.pivot(index="Outlet", columns="Kanal_Penjualan", values="rasio")
    zu = a.pivot(index="Outlet", columns="Kanal_Penjualan", values="u")
    ro = [o for o in OUTLET_ORDER if o in zr.index]
    co = [k for k in KANAL_COLORS if k in zr.columns]
    zr, zu = zr.loc[ro, co], zu.loc[ro, co]
    fig = go.Figure(go.Heatmap(
        z=zr.values, x=co, y=ro, colorscale="Blues", zmin=0, zmax=max(5, float(np.nanmax(zr.values)) * 1.1),
        showscale=False, text=[[f"<b>{dec(zr.iloc[i, j], 1)}</b><br><sub>{angka(zu.iloc[i, j])} ulasan</sub>"
                                 for j in range(len(co))] for i in range(len(ro))],
        texttemplate="%{text}", textfont=dict(size=15),
        hovertemplate="%{y} - %{x}: %{z:.1f} ulasan per 100 transaksi<extra></extra>",
    ))
    fig.update_yaxes(autorange="reversed")
    st.plotly_chart(style(fig), width='stretch', theme=None)

# ----------------------------------------------------------------------------
# Baris 4: tren rating bulanan
# ----------------------------------------------------------------------------
st.subheader("Rating berbobot per bulan: Malioboro dibanding outlet lain")
f2 = f.copy()
f2["Kelompok"] = np.where(f2["Outlet"] == "Malioboro", "Malioboro", "Tiga outlet lain")
gm = group_weighted(f2, ["BulanNo", "Kelompok"])
fig = go.Figure()
for kel, warna in [("Malioboro", ORANGE), ("Tiga outlet lain", BLUE)]:
    s = gm[gm["Kelompok"] == kel].sort_values("BulanNo")
    if s.empty:
        continue
    fig.add_trace(go.Scatter(x=[BULAN_ID[i - 1] for i in s["BulanNo"]], y=s["Rating"], mode="lines+markers",
                             line=dict(color=warna, width=3), marker=dict(size=7), name=kel,
                             hovertemplate=kel + " %{x}: %{y:.2f}<extra></extra>"))
    fig.add_annotation(x=BULAN_ID[s["BulanNo"].iloc[-1] - 1], y=s["Rating"].iloc[-1], text=f"  {kel}",
                       showarrow=False, xanchor="left", font=dict(color=warna))
fig.update_yaxes(title="Rating berbobot (sumbu mulai 4,0)", range=[4.0, 4.8], gridcolor="#EEF1F4")
fig.update_xaxes(showgrid=False)
st.plotly_chart(style(fig, height=300, margin=dict(l=10, r=120, t=10, b=10)), width='stretch', theme=None)

# ----------------------------------------------------------------------------
# Teks pendukung
# ----------------------------------------------------------------------------
st.markdown("---")
st.markdown(
    f'<div class="foot"><b>Periode data:</b> {df["Tanggal"].min():%d-%m-%Y} s.d. {df["Tanggal"].max():%d-%m-%Y} '
    f'&nbsp;|&nbsp; <b>Sumber:</b> {SOURCE}. Seluruh angka adalah data simulasi. '
    f'Rating kosong (baris tanpa ulasan) tidak dihitung dan tidak dianggap nol.</div>',
    unsafe_allow_html=True,
)
