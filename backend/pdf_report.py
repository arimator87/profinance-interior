import io
import logging
from datetime import datetime

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_RIGHT, TA_CENTER, TA_LEFT
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image as RLImage, PageBreak,
)
from reportlab.graphics.shapes import Drawing, Rect, Circle, String
from reportlab.graphics.charts.piecharts import Pie
from reportlab.lib.utils import ImageReader
import base64 as _b64

from storage import get_object

logger = logging.getLogger(__name__)

INK = colors.HexColor("#0F172A")
AMBER = colors.HexColor("#D97706")
AMBER_L = colors.HexColor("#FEF3C7")
SLATE = colors.HexColor("#64748B")
SLATE_L = colors.HexColor("#94A3B8")
LINE = colors.HexColor("#E2E8F0")
BG = colors.HexColor("#F8FAFC")
GREEN = colors.HexColor("#16A34A")
BLUE = colors.HexColor("#2563EB")
ORANGE = colors.HexColor("#EA580C")
RED = colors.HexColor("#DC2626")
WHITE = colors.white

CAT_COLORS = [AMBER, BLUE, GREEN, ORANGE, colors.HexColor("#7C3AED"),
              colors.HexColor("#0891B2"), colors.HexColor("#DB2777"), SLATE]


def rupiah(n):
    try:
        n = int(round(n))
    except Exception:
        n = 0
    neg = n < 0
    s = f"{abs(n):,}".replace(",", ".")
    return ("-Rp " if neg else "Rp ") + s


def _fmt(d):
    if not d:
        return "-"
    try:
        return datetime.fromisoformat(str(d)[:19]).strftime("%d/%m/%Y")
    except Exception:
        return str(d)[:10]


def _health(margin):
    m = margin or 0
    if m >= 20:
        return "SANGAT SEHAT", GREEN, "Margin keuntungan sangat baik, proyek berjalan optimal."
    if m >= 10:
        return "SEHAT", BLUE, "Margin keuntungan sehat, arus kas proyek terkendali."
    if m >= 0:
        return "CUKUP", AMBER, "Margin tipis, perhatikan pengeluaran agar tetap surplus."
    if m >= -10:
        return "PERHATIAN", ORANGE, "Proyek mulai defisit, tinjau ulang biaya & penagihan."
    return "KRITIS", RED, "Proyek defisit signifikan, perlu tindakan segera."


def _bar(track_w, frac, color, h=9):
    frac = max(0.0, min(1.0, frac))
    d = Drawing(track_w, h + 2)
    d.add(Rect(0, 1, track_w, h, rx=h / 2, ry=h / 2, fillColor=LINE, strokeColor=None))
    if frac > 0:
        d.add(Rect(0, 1, max(track_w * frac, h), h, rx=h / 2, ry=h / 2, fillColor=color, strokeColor=None))
    return d


def _donut(total_in, total_out):
    d = Drawing(150, 130)
    tot = (total_in or 0) + (total_out or 0)
    if tot <= 0:
        return d
    pie = Pie()
    pie.x, pie.y, pie.width, pie.height = 20, 12, 106, 106
    pie.data = [max(total_in, 0.0001), max(total_out, 0.0001)]
    pie.slices[0].fillColor = GREEN
    pie.slices[1].fillColor = ORANGE
    pie.slices.strokeColor = WHITE
    pie.slices.strokeWidth = 2
    d.add(pie)
    cx, cy = 20 + 53, 12 + 53
    d.add(Circle(cx, cy, 30, fillColor=WHITE, strokeColor=WHITE))
    pct = int(round(total_in / tot * 100))
    d.add(String(cx, cy + 2, f"{pct}%", fontName="Helvetica-Bold", fontSize=15, fillColor=INK, textAnchor="middle"))
    d.add(String(cx, cy - 12, "Masuk", fontName="Helvetica", fontSize=7, fillColor=SLATE, textAnchor="middle"))
    return d


def build_report_pdf(project, summary, transactions, workers, work_items, progress_entries):
    company = (project.get("companyName") or "ProFinance Interior").upper()
    published = datetime.now().strftime("%d/%m/%Y, %H.%M")

    def draw_page(canvas, doc):
        w, h = A4
        # header band
        canvas.setFillColor(INK)
        canvas.rect(0, h - 22 * mm, w, 22 * mm, fill=1, stroke=0)
        canvas.setFillColor(AMBER)
        canvas.setFont("Helvetica-Bold", 13)
        canvas.drawString(15 * mm, h - 12 * mm, company)
        canvas.setFillColor(colors.HexColor("#CBD5E1"))
        canvas.setFont("Helvetica", 7.5)
        canvas.drawString(15 * mm, h - 17 * mm, "LAPORAN KEUANGAN INTERNAL")
        # confidential pill
        canvas.setFillColor(colors.HexColor("#7F1D1D"))
        canvas.roundRect(w - 55 * mm, h - 15 * mm, 40 * mm, 7 * mm, 3.5 * mm, fill=1, stroke=0)
        canvas.setFillColor(colors.HexColor("#FCA5A5"))
        canvas.setFont("Helvetica-Bold", 7.5)
        canvas.drawCentredString(w - 35 * mm, h - 12.6 * mm, "RAHASIA \u2014 INTERNAL")
        # footer band
        canvas.setFillColor(INK)
        canvas.rect(0, 0, w, 12 * mm, fill=1, stroke=0)
        canvas.setFillColor(colors.HexColor("#CBD5E1"))
        canvas.setFont("Helvetica", 7)
        canvas.drawString(15 * mm, 4.6 * mm, f"{company}  \u2022  Laporan Keuangan Internal \u2014 Rahasia")
        canvas.setFont("Helvetica", 7)
        canvas.drawRightString(w - 15 * mm, 4.6 * mm, f"Diterbitkan: {published}  \u2022  Hal {canvas.getPageNumber()}")

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=15 * mm, rightMargin=15 * mm, topMargin=28 * mm, bottomMargin=16 * mm,
    )
    content_w = A4[0] - 30 * mm

    styles = getSampleStyleSheet()
    st_kick = ParagraphStyle("kick", parent=styles["Normal"], fontSize=9, textColor=AMBER, spaceAfter=2, fontName="Helvetica-Bold")
    st_title = ParagraphStyle("title", parent=styles["Normal"], fontSize=26, leading=30, textColor=INK, fontName="Helvetica-Bold", spaceAfter=2)
    st_sub = ParagraphStyle("sub", parent=styles["Normal"], fontSize=13, leading=16, textColor=SLATE, spaceAfter=8)
    st_small = ParagraphStyle("small", parent=styles["Normal"], fontSize=8.5, textColor=SLATE)
    st_sec = ParagraphStyle("sec", parent=styles["Normal"], fontSize=12.5, textColor=INK, fontName="Helvetica-Bold", spaceBefore=14, spaceAfter=8)
    st_norm = ParagraphStyle("norm", parent=styles["Normal"], fontSize=9, leading=13, textColor=INK)
    st_cell = ParagraphStyle("cell", parent=styles["Normal"], fontSize=8.5, leading=11, textColor=INK)
    story = []

    def section(title):
        t = Table([[Paragraph(title, ParagraphStyle("s", parent=st_sec, spaceBefore=0, spaceAfter=0))]], colWidths=[content_w])
        t.setStyle(TableStyle([
            ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 12), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("LINEBELOW", (0, 0), (-1, -1), 2, AMBER),
        ]))
        return t

    # ---- values ----
    nominal = summary.get("nominal", 0)
    total_in = summary["totalIn"]
    total_out = summary["totalOut"]
    balance = summary["balance"]
    margin = summary["marginPct"]
    realisasi = summary["realisasiPct"]
    terbayar = summary["terbayar"]
    sisa = summary["sisaTagihan"]
    in_txs = [t for t in transactions if t.get("type") == "in"]
    out_txs = [t for t in transactions if t.get("type") == "out"]
    hstatus, hcolor, hdesc = _health(margin)

    # ================= COVER =================
    story.append(Spacer(1, 6))
    story.append(Paragraph("LAPORAN KEUANGAN PROYEK", st_kick))
    story.append(Paragraph(project.get("name", "-"), st_title))
    owner = project.get("owner") or "-"
    loc = project.get("alamatProyek") or "-"
    story.append(Paragraph(f"<b>Owner / Klien:</b> {owner} &nbsp;&nbsp;&bull;&nbsp;&nbsp; <b>Lokasi:</b> {loc}", st_sub))

    def metric(label, value, vcolor=INK, big=False):
        return Paragraph(
            f"<font size=7.5 color='#94A3B8'>{label}</font><br/>"
            f"<font size={'13' if big else '11'} color='{vcolor.hexval() if hasattr(vcolor,'hexval') else vcolor}'><b>{value}</b></font>",
            ParagraphStyle("m", parent=st_norm, leading=16))

    rep_date = datetime.now().strftime("%d %B %Y")
    m_rows = [
        [metric("NILAI KONTRAK", rupiah(nominal), big=True), metric("TANGGAL LAPORAN", rep_date)],
        [metric("TANGGAL MULAI", _fmt(project.get("tanggalMulai"))), metric("TARGET SELESAI", _fmt(project.get("targetSelesai")))],
        [metric("TOTAL TRANSAKSI", f"{summary.get('txCount', len(transactions))} transaksi"), metric("STATUS KEUANGAN", hstatus, hcolor, big=True)],
    ]
    mt = Table(m_rows, colWidths=[content_w / 2, content_w / 2])
    mt.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), BG), ("BOX", (0, 0), (-1, -1), 0.6, LINE),
        ("INNERGRID", (0, 0), (-1, -1), 0.6, LINE),
        ("TOPPADDING", (0, 0), (-1, -1), 12), ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
        ("LEFTPADDING", (0, 0), (-1, -1), 14), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    story.append(Spacer(1, 10))
    story.append(mt)
    story.append(Spacer(1, 12))
    story.append(Paragraph("DOKUMEN RAHASIA \u2014 HANYA UNTUK INTERNAL", ParagraphStyle("c", parent=st_small, textColor=SLATE_L)))
    story.append(PageBreak())

    # ================= HEALTH + KPI =================
    story.append(section("STATUS KESEHATAN KEUANGAN"))
    hbox = Table([[
        Paragraph(f"<font size=22 color='{hcolor.hexval()}'><b>{hstatus}</b></font><br/>"
                  f"<font size=9 color='#64748B'>{hdesc}</font>", ParagraphStyle("h", parent=st_norm, leading=26)),
        Paragraph(f"<font size=7.5 color='#94A3B8'>MARGIN KEUNTUNGAN</font><br/>"
                  f"<font size=24 color='{hcolor.hexval()}'><b>{margin:.1f}%</b></font>",
                  ParagraphStyle("hm", parent=st_norm, leading=27, alignment=TA_RIGHT)),
    ]], colWidths=[content_w * 0.62, content_w * 0.38])
    hbox.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), BG), ("BOX", (0, 0), (-1, -1), 0.6, LINE),
        ("LINEBEFORE", (0, 0), (0, 0), 4, hcolor),
        ("TOPPADDING", (0, 0), (-1, -1), 14), ("BOTTOMPADDING", (0, 0), (-1, -1), 14),
        ("LEFTPADDING", (0, 0), (-1, -1), 16), ("RIGHTPADDING", (0, 0), (-1, -1), 16),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    story.append(hbox)

    cards = [
        ("TOTAL PEMASUKAN", rupiah(total_in), f"{len(in_txs)} transaksi masuk", GREEN),
        ("TOTAL PENGELUARAN", rupiah(total_out), f"{len(out_txs)} transaksi keluar", ORANGE),
        ("SALDO / KEUNTUNGAN", rupiah(balance), "Surplus dari nilai proyek" if balance >= 0 else "Defisit proyek", BLUE),
        ("NILAI KONTRAK", rupiah(nominal), "Total nilai pekerjaan", INK),
        ("MARGIN KEUNTUNGAN", f"{margin:.2f}%", "Dari nilai kontrak", hcolor),
        ("REALISASI TAGIHAN", f"{realisasi:.1f}%", f"{rupiah(terbayar)} dari {rupiah(nominal)}", AMBER),
    ]

    def card_para(t, v, d, c):
        return Paragraph(
            f"<font size=7.5 color='#64748B'>{t}</font><br/>"
            f"<font size=14 color='{c.hexval()}'><b>{v}</b></font><br/>"
            f"<font size=7 color='#94A3B8'>{d}</font>",
            ParagraphStyle("cp", parent=st_norm, leading=17))

    cw = content_w / 2
    crows = [[card_para(*cards[0]), card_para(*cards[1])],
             [card_para(*cards[2]), card_para(*cards[3])],
             [card_para(*cards[4]), card_para(*cards[5])]]
    ct = Table(crows, colWidths=[cw, cw])
    cst = [
        ("BACKGROUND", (0, 0), (-1, -1), WHITE), ("BOX", (0, 0), (-1, -1), 0.6, LINE),
        ("INNERGRID", (0, 0), (-1, -1), 6, WHITE),
        ("ROWBACKGROUNDS", (0, 0), (-1, -1), [BG, BG]),
        ("TOPPADDING", (0, 0), (-1, -1), 12), ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
        ("LEFTPADDING", (0, 0), (-1, -1), 14), ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]
    idx = [(0, 0, GREEN), (1, 0, ORANGE), (0, 1, BLUE), (1, 1, INK), (0, 2, hcolor), (1, 2, AMBER)]
    for c, r, col in idx:
        cst.append(("LINEBEFORE", (c, r), (c, r), 4, col))
    ct.setStyle(TableStyle(cst))
    story.append(Spacer(1, 8))
    story.append(ct)

    # Realisasi tagihan
    story.append(section("REALISASI TAGIHAN"))
    frac = (terbayar / nominal) if nominal else 0
    rhead = Table([[
        Paragraph("Progress Penagihan Kontrak", st_small),
        Paragraph(f"<font size=15 color='{AMBER.hexval()}'><b>{realisasi:.1f}%</b></font>",
                  ParagraphStyle("r", parent=st_norm, alignment=TA_RIGHT)),
    ]], colWidths=[content_w * 0.6, content_w * 0.4 - 28])
    rhead.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("LEFTPADDING", (0, 0), (-1, -1), 0),
                               ("RIGHTPADDING", (0, 0), (-1, -1), 0), ("TOPPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 4)]))
    rfoot = Table([[
        Paragraph("Rp 0", st_small),
        Paragraph(f"<b>Sudah dibayar: {rupiah(terbayar)}</b> &nbsp; &bull; &nbsp; Sisa: {rupiah(sisa)}",
                  ParagraphStyle("rr", parent=st_small, alignment=TA_RIGHT)),
    ]], colWidths=[content_w * 0.3, content_w * 0.7 - 28])
    rfoot.setStyle(TableStyle([("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                               ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 0)]))
    rbar = Table([[rhead], [_bar(content_w - 28, frac, BLUE, h=11)], [rfoot]], colWidths=[content_w - 28])
    rbar.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), BG), ("BOX", (0, 0), (-1, -1), 0.6, LINE),
        ("TOPPADDING", (0, 0), (-1, -1), 8), ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("LEFTPADDING", (0, 0), (-1, -1), 14), ("RIGHTPADDING", (0, 0), (-1, -1), 14),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    story.append(rbar)

    # Distribusi keuangan (donut)
    story.append(section("DISTRIBUSI KEUANGAN"))
    legend = Paragraph(
        f"<font color='#16A34A'>&#9632;</font> <b>Total Pemasukan</b> &nbsp; {rupiah(total_in)}<br/>"
        f"<font color='#EA580C'>&#9632;</font> <b>Total Pengeluaran</b> &nbsp; {rupiah(total_out)}<br/><br/>"
        f"<font size=8 color='#64748B'>Saldo Akhir</font><br/>"
        f"<font size=15 color='{BLUE.hexval()}'><b>{rupiah(balance)}</b></font>",
        ParagraphStyle("lg", parent=st_norm, leading=16))
    dt = Table([[_donut(total_in, total_out), legend]], colWidths=[content_w * 0.42, content_w * 0.58])
    dt.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), BG), ("BOX", (0, 0), (-1, -1), 0.6, LINE),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("TOPPADDING", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10), ("LEFTPADDING", (0, 0), (-1, -1), 14),
    ]))
    story.append(dt)

    # Breakdown pengeluaran per kategori
    story.append(section("BREAKDOWN PENGELUARAN PER KATEGORI"))
    by_cat = {}
    for t in out_txs:
        by_cat[t.get("category", "Lainnya")] = by_cat.get(t.get("category", "Lainnya"), 0) + t.get("amount", 0)
    cat_list = sorted(by_cat.items(), key=lambda x: x[1], reverse=True)
    if not cat_list:
        story.append(Paragraph("Belum ada pengeluaran.", st_small))
    else:
        maxv = cat_list[0][1] or 1
        rows = []
        for i, (name, val) in enumerate(cat_list):
            pct = (val / total_out * 100) if total_out else 0
            col = CAT_COLORS[i % len(CAT_COLORS)]
            rows.append([
                Paragraph(f"<b>{name}</b>", st_cell),
                _bar(content_w * 0.34, val / maxv, col, h=8),
                Paragraph(f"<b>{rupiah(val)}</b>", ParagraphStyle("v", parent=st_cell, alignment=TA_RIGHT)),
                Paragraph(f"{pct:.1f}%", ParagraphStyle("p", parent=st_cell, alignment=TA_RIGHT, textColor=SLATE)),
            ])
        bt = Table(rows, colWidths=[content_w * 0.28, content_w * 0.40, content_w * 0.20, content_w * 0.12])
        bt.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("ROWBACKGROUNDS", (0, 0), (-1, -1), [WHITE, BG]),
            ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("LEFTPADDING", (0, 0), (-1, -1), 8), ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ("LINEBELOW", (0, 0), (-1, -2), 0.4, LINE),
        ]))
        story.append(bt)

    # ================= TABLES =================
    def tx_table(rows_data, total_label, total_val):
        head = ["TANGGAL", "KATEGORI", "KETERANGAN", "JUMLAH"]
        rows = [head]
        for t in rows_data:
            rows.append([_fmt(t.get("date")), t.get("category", "-"),
                         (t.get("description", "") or "")[:60], rupiah(t.get("amount", 0))])
        if len(rows) == 1:
            rows.append(["-", "-", "Belum ada transaksi", "-"])
        rows.append(["", "", total_label, rupiah(total_val)])
        tbl = Table(rows, colWidths=[content_w * 0.16, content_w * 0.24, content_w * 0.42, content_w * 0.18], repeatRows=1)
        tbl.setStyle(TableStyle([
            ("FONTSIZE", (0, 0), (-1, -1), 8), ("BACKGROUND", (0, 0), (-1, 0), INK),
            ("TEXTCOLOR", (0, 0), (-1, 0), WHITE), ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -2), [WHITE, BG]),
            ("GRID", (0, 0), (-1, -1), 0.4, LINE), ("ALIGN", (3, 0), (3, -1), "RIGHT"),
            ("BACKGROUND", (0, -1), (-1, -1), AMBER_L), ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
            ("TEXTCOLOR", (0, -1), (-1, -1), colors.HexColor("#92400E")), ("SPAN", (0, -1), (1, -1)),
            ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ]))
        return tbl

    story.append(section("DETAIL PEMASUKAN"))
    story.append(Paragraph("Rincian Transaksi Masuk", st_small))
    story.append(Spacer(1, 4))
    story.append(tx_table(sorted(in_txs, key=lambda x: x.get("date", "")), "TOTAL PEMASUKAN", total_in))

    story.append(section("DETAIL PENGELUARAN"))
    story.append(Paragraph("Rincian Transaksi Keluar", st_small))
    story.append(Spacer(1, 4))
    story.append(tx_table(sorted(out_txs, key=lambda x: x.get("date", "")), "TOTAL PENGELUARAN", total_out))

    # Tukang summary
    if workers:
        story.append(section("RINGKASAN TUKANG"))
        wr = [["NAMA TUKANG", "BORONGAN", "KASBON", "PELUNASAN", "SISA HUTANG"]]
        for w in workers:
            wr.append([w.get("name", "-"), rupiah(w.get("borongan", 0)), rupiah(w.get("totalKasbon", 0)),
                       rupiah(w.get("totalPelunasan", 0)), rupiah(w.get("sisaHutang", 0))])
        wt = Table(wr, colWidths=[content_w * 0.28, content_w * 0.19, content_w * 0.18, content_w * 0.18, content_w * 0.17], repeatRows=1)
        wt.setStyle(TableStyle([
            ("FONTSIZE", (0, 0), (-1, -1), 8), ("BACKGROUND", (0, 0), (-1, 0), INK),
            ("TEXTCOLOR", (0, 0), (-1, 0), WHITE), ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, BG]), ("GRID", (0, 0), (-1, -1), 0.4, LINE),
            ("ALIGN", (1, 0), (-1, -1), "RIGHT"), ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5), ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ]))
        story.append(wt)

    doc.build(story, onFirstPage=draw_page, onLaterPages=draw_page)
    buf.seek(0)
    return buf.read()


def _scurve(curve, width, height=150):
    from reportlab.graphics.charts.lineplots import LinePlot
    from reportlab.graphics.widgets.markers import makeMarker
    d = Drawing(width, height)
    if not curve:
        return d
    planned = [(i, c["planned"]) for i, c in enumerate(curve)]
    actual = [(i, c["actual"]) for i, c in enumerate(curve)]
    lp = LinePlot()
    lp.x, lp.y, lp.width, lp.height = 34, 26, width - 50, height - 42
    lp.data = [planned, actual]
    lp.lines[0].strokeColor = BLUE
    lp.lines[0].strokeWidth = 2
    lp.lines[1].strokeColor = AMBER
    lp.lines[1].strokeWidth = 2.5
    lp.lines[1].symbol = makeMarker("FilledCircle", size=4, fillColor=AMBER)
    lp.yValueAxis.valueMin = 0
    lp.yValueAxis.valueMax = 100
    lp.yValueAxis.valueStep = 25
    lp.yValueAxis.labelTextFormat = "%d%%"
    lp.yValueAxis.labels.fontSize = 7
    lp.xValueAxis.valueMin = 0
    lp.xValueAxis.valueMax = max(len(curve) - 1, 1)
    lp.xValueAxis.valueStep = max(1, (len(curve) - 1) // 5 or 1)
    lp.xValueAxis.labels.fontSize = 6
    n = len(curve)
    lp.xValueAxis.labelTextFormat = lambda v: (curve[int(v)]["date"][5:] if 0 <= int(v) < n else "")
    d.add(lp)
    return d


def build_progress_pdf(project, summary, prog, transactions, entries_by_key):
    company = (project.get("companyName") or "ProFinance Interior").upper()
    published = datetime.now().strftime("%d/%m/%Y, %H.%M")
    NAVY = colors.HexColor("#1E3A8A")

    def draw_page(canvas, doc):
        w, h = A4
        canvas.setFillColor(INK)
        canvas.rect(0, h - 22 * mm, w, 22 * mm, fill=1, stroke=0)
        canvas.setFillColor(WHITE)
        canvas.setFont("Helvetica-Bold", 13)
        canvas.drawString(15 * mm, h - 12 * mm, company)
        canvas.setFillColor(colors.HexColor("#93C5FD"))
        canvas.setFont("Helvetica", 7.5)
        canvas.drawString(15 * mm, h - 17 * mm, "LAPORAN PROGRES RESMI PROYEK")
        canvas.setFillColor(colors.HexColor("#1D4ED8"))
        canvas.roundRect(w - 52 * mm, h - 15 * mm, 37 * mm, 7 * mm, 3.5 * mm, fill=1, stroke=0)
        canvas.setFillColor(WHITE)
        canvas.setFont("Helvetica-Bold", 7.5)
        canvas.drawCentredString(w - 33.5 * mm, h - 12.6 * mm, "PROGRES RESMI")
        canvas.setFillColor(INK)
        canvas.rect(0, 0, w, 12 * mm, fill=1, stroke=0)
        canvas.setFillColor(colors.HexColor("#CBD5E1"))
        canvas.setFont("Helvetica", 7)
        canvas.drawString(15 * mm, 4.6 * mm, f"{company}  \u2022  Laporan Progres Resmi")
        canvas.drawRightString(w - 15 * mm, 4.6 * mm, f"Diterbitkan: {published}  \u2022  Hal {canvas.getPageNumber()}")

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=15 * mm, rightMargin=15 * mm, topMargin=28 * mm, bottomMargin=16 * mm)
    content_w = A4[0] - 30 * mm
    styles = getSampleStyleSheet()
    st_kick = ParagraphStyle("k", parent=styles["Normal"], fontSize=9, textColor=BLUE, fontName="Helvetica-Bold", spaceAfter=2)
    st_title = ParagraphStyle("t", parent=styles["Normal"], fontSize=24, leading=28, textColor=NAVY, fontName="Helvetica-Bold")
    st_sub = ParagraphStyle("su", parent=styles["Normal"], fontSize=11, leading=15, textColor=SLATE, spaceAfter=6)
    st_small = ParagraphStyle("sm", parent=styles["Normal"], fontSize=8.5, textColor=SLATE)
    st_sec = ParagraphStyle("se", parent=styles["Normal"], fontSize=12.5, textColor=NAVY, fontName="Helvetica-Bold")
    st_norm = ParagraphStyle("n", parent=styles["Normal"], fontSize=9, leading=13, textColor=INK)
    st_cell = ParagraphStyle("c", parent=styles["Normal"], fontSize=8.5, leading=11, textColor=INK)
    story = []

    def section(title):
        t = Table([[Paragraph(title, st_sec)]], colWidths=[content_w])
        t.setStyle(TableStyle([("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                               ("TOPPADDING", (0, 0), (-1, -1), 12), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                               ("LINEBELOW", (0, 0), (-1, -1), 2, BLUE)]))
        return t

    nominal = summary.get("nominal", 0)
    terbayar = summary["terbayar"]
    sisa = summary["sisaTagihan"]
    realisasi = summary["realisasiPct"]
    actual = prog.get("totalProgress", 0)
    planned = prog.get("plannedProgress", 0)
    items = prog.get("items", [])

    # Cover
    story.append(Paragraph("LAPORAN PROGRES RESMI", st_kick))
    story.append(Paragraph(project.get("name", "-"), st_title))
    story.append(Paragraph(f"Kepada: <b>{project.get('owner') or '-'}</b> &nbsp;&bull;&nbsp; Lokasi: {project.get('alamatProyek') or '-'}", st_sub))

    info = Table([[
        Paragraph(f"<font size=7.5 color='#BFDBFE'>NAMA PROYEK</font><br/><b>{project.get('name','-')}</b><br/><br/>"
                  f"<font size=7.5 color='#BFDBFE'>NILAI KONTRAK</font><br/><b>{rupiah(nominal)}</b>", ParagraphStyle("i1", parent=st_norm, textColor=WHITE, leading=14)),
        Paragraph(f"<font size=7.5 color='#BFDBFE'>PEMILIK / KLIEN</font><br/><b>{project.get('owner') or '-'}</b><br/><br/>"
                  f"<font size=7.5 color='#BFDBFE'>TARGET SELESAI</font><br/><b>{_fmt(project.get('targetSelesai'))}</b>", ParagraphStyle("i2", parent=st_norm, textColor=WHITE, leading=14)),
    ]], colWidths=[content_w / 2, content_w / 2])
    info.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), NAVY), ("TOPPADDING", (0, 0), (-1, -1), 14),
                              ("BOTTOMPADDING", (0, 0), (-1, -1), 14), ("LEFTPADDING", (0, 0), (-1, -1), 16), ("VALIGN", (0, 0), (-1, -1), "TOP")]))
    story.append(Spacer(1, 8))
    story.append(info)

    # Payment cards
    def card(t, v, d):
        return Paragraph(f"<font size=7.5 color='#64748B'>{t}</font><br/><font size=13 color='{NAVY.hexval()}'><b>{v}</b></font><br/><font size=7 color='#94A3B8'>{d}</font>",
                         ParagraphStyle("cd", parent=st_norm, leading=16))
    pc = Table([[card("NILAI KONTRAK", rupiah(nominal), "Total nilai pekerjaan"),
                 card("TOTAL TERBAYAR", rupiah(terbayar), f"{realisasi:.0f}% dari nilai kontrak"),
                 card("SISA PEMBAYARAN", rupiah(sisa), "Ditagih saat serah terima")]],
                colWidths=[content_w / 3] * 3)
    pc.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), BG), ("BOX", (0, 0), (-1, -1), 0.6, LINE), ("INNERGRID", (0, 0), (-1, -1), 6, WHITE),
                            ("ROWBACKGROUNDS", (0, 0), (-1, -1), [BG]), ("TOPPADDING", (0, 0), (-1, -1), 12), ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
                            ("LEFTPADDING", (0, 0), (-1, -1), 12), ("VALIGN", (0, 0), (-1, -1), "TOP"),
                            ("LINEBEFORE", (0, 0), (0, 0), 3, NAVY), ("LINEBEFORE", (1, 0), (1, 0), 3, GREEN), ("LINEBEFORE", (2, 0), (2, 0), 3, ORANGE)]))
    story.append(Spacer(1, 8))
    story.append(pc)

    # Realisasi pembayaran
    story.append(section("REALISASI PEMBAYARAN"))
    frac = (terbayar / nominal) if nominal else 0
    rr = Table([[Paragraph(f"<b>Progress Penagihan</b>  Rp 0 &rarr; {rupiah(nominal)}", st_small),
                 Paragraph(f"<font size=15 color='{NAVY.hexval()}'><b>{realisasi:.0f}%</b></font>", ParagraphStyle("rp", parent=st_norm, alignment=TA_RIGHT))],
                [_bar(content_w - 28, frac, ORANGE, h=11), ""]],
               colWidths=[content_w * 0.7, content_w * 0.3 - 28])
    rr.setStyle(TableStyle([("SPAN", (0, 1), (1, 1)), ("BACKGROUND", (0, 0), (-1, -1), BG), ("BOX", (0, 0), (-1, -1), 0.6, LINE),
                            ("TOPPADDING", (0, 0), (-1, -1), 8), ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                            ("LEFTPADDING", (0, 0), (-1, -1), 14), ("RIGHTPADDING", (0, 0), (-1, -1), 14), ("VALIGN", (0, 0), (-1, -1), "MIDDLE")]))
    story.append(rr)

    # Payment termin history
    story.append(section("RIWAYAT & JADWAL PEMBAYARAN TERMIN"))
    paid_cats = {"Downpayment", "Termin", "Pelunasan"}
    pays = [t for t in transactions if t.get("type") == "in" and t.get("category") in paid_cats]
    pays = sorted(pays, key=lambda x: x.get("date", ""))
    rows = [["#", "TANGGAL", "KETERANGAN", "JUMLAH", "STATUS"]]
    for i, t in enumerate(pays, 1):
        rows.append([str(i), _fmt(t.get("date")), (t.get("description") or t.get("category"))[:40], rupiah(t.get("amount", 0)), "Diterima"])
    wait_row = len(rows)
    if sisa > 0:
        rows.append([str(len(pays) + 1), "-", "Sisa Pembayaran (Serah Terima)", rupiah(sisa), "Menunggu"])
    pt = Table(rows, colWidths=[content_w * 0.06, content_w * 0.2, content_w * 0.42, content_w * 0.2, content_w * 0.12], repeatRows=1)
    pst = [("FONTSIZE", (0, 0), (-1, -1), 8), ("BACKGROUND", (0, 0), (-1, 0), NAVY), ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
           ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"), ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, BG]), ("GRID", (0, 0), (-1, -1), 0.4, LINE),
           ("ALIGN", (3, 0), (3, -1), "RIGHT"), ("ALIGN", (0, 0), (0, -1), "CENTER"), ("ALIGN", (4, 0), (4, -1), "CENTER"),
           ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5), ("VALIGN", (0, 0), (-1, -1), "MIDDLE")]
    for r in range(1, len(rows)):
        if rows[r][4] == "Diterima":
            pst += [("BACKGROUND", (4, r), (4, r), colors.HexColor("#DCFCE7")), ("TEXTCOLOR", (4, r), (4, r), colors.HexColor("#15803D"))]
        else:
            pst += [("BACKGROUND", (4, r), (4, r), colors.HexColor("#FEF9C3")), ("TEXTCOLOR", (4, r), (4, r), colors.HexColor("#A16207"))]
    pt.setStyle(TableStyle(pst))
    story.append(pt)
    if sisa > 0:
        story.append(Spacer(1, 4))
        story.append(Paragraph(f"<font color='#2563EB'>&#9432;</font> <b>Catatan:</b> Sisa pembayaran {rupiah(sisa)} akan ditagihkan pada saat serah terima proyek.", st_small))

    # S-Curve
    story.append(section("PROGRESS PER AREA PEKERJAAN"))
    story.append(Paragraph("<b>KURVA S \u2014 Rencana vs Realisasi</b> &nbsp;<font size=8 color='#64748B'>(bobot tertimbang seluruh area)</font>", st_norm))
    sc = Table([[_scurve(prog.get("curve", []), content_w * 0.66),
                 Paragraph(f"<font size=8 color='#64748B'>Progress Tertimbang</font><br/><font size=26 color='{NAVY.hexval()}'><b>{actual:.1f}%</b></font><br/>"
                           f"<font size=8 color='#64748B'>Rencana s/d kini</font><br/><font size=13 color='{BLUE.hexval()}'><b>{planned:.1f}%</b></font>",
                           ParagraphStyle("scr", parent=st_norm, leading=20, alignment=TA_CENTER))]],
               colWidths=[content_w * 0.66, content_w * 0.34])
    sc.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), BG), ("BOX", (0, 0), (-1, -1), 0.6, LINE), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                            ("TOPPADDING", (0, 0), (-1, -1), 8), ("BOTTOMPADDING", (0, 0), (-1, -1), 8)]))
    story.append(Spacer(1, 6))
    story.append(sc)

    # Area progress cards
    if items:
        cells = []
        for it in items:
            kontrib = it["weight"] * it["lastProgress"] / 100
            status = "Selesai" if it["lastProgress"] >= 100 else ("Berjalan" if it["lastProgress"] > 0 else "Belum Mulai")
            scol = GREEN if it["lastProgress"] >= 100 else (AMBER if it["lastProgress"] > 0 else SLATE)
            cells.append(Paragraph(
                f"<b>{it['name'][:34]}</b><br/><font size=7 color='#64748B'>Bobot {it['weight']:.2f}% &bull; Kontribusi {kontrib:.1f}%</font><br/>"
                f"<font size=16 color='{NAVY.hexval()}'><b>{int(round(it['lastProgress']))}%</b></font> <font size=8 color='{scol.hexval()}'>&bull; {status}</font>",
                ParagraphStyle("ac", parent=st_norm, leading=15)))
        while len(cells) % 2:
            cells.append(Paragraph("", st_norm))
        grid = [cells[i:i + 2] for i in range(0, len(cells), 2)]
        gt = Table(grid, colWidths=[content_w / 2, content_w / 2])
        gt.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), WHITE), ("BOX", (0, 0), (-1, -1), 0.6, LINE), ("INNERGRID", (0, 0), (-1, -1), 6, WHITE),
                                ("ROWBACKGROUNDS", (0, 0), (-1, -1), [BG, BG]), ("TOPPADDING", (0, 0), (-1, -1), 10), ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
                                ("LEFTPADDING", (0, 0), (-1, -1), 12), ("VALIGN", (0, 0), (-1, -1), "TOP")]))
        story.append(Spacer(1, 8))
        story.append(gt)

    # Deviasi RAB: Baseline vs Revisi
    baseline = prog.get("rabBaseline")
    if baseline:
        RED = colors.HexColor("#DC2626")
        b_items = baseline.get("items", [])
        cur_map = {it["id"]: it for it in items}
        b_ids = {bi["id"] for bi in b_items}
        b_tot = baseline.get("totalItemValue", 0) or 0
        c_tot = prog.get("totalItemValue", 0) or 0
        d_tot = c_tot - b_tot
        pct = (d_tot / b_tot * 100) if b_tot else 0
        story.append(section("DEVIASI RAB \u2014 BASELINE VS REVISI"))
        story.append(Paragraph(
            f"Baseline disimpan <b>{_fmt(baseline.get('savedAt'))}</b>. Perbandingan nilai tiap area terhadap RAB awal (sebelum negosiasi).", st_small))
        drows = [["AREA PEKERJAAN", "BASELINE", "REVISI", "SELISIH"]]
        deltas = []
        for bi in b_items:
            cur = cur_map.get(bi["id"])
            cur_val = cur["nilai"] if cur else 0
            delta = cur_val - (bi.get("value", 0) or 0)
            label = (bi.get("name", "-") or "-")[:44] + ("  (DIHAPUS)" if not cur else "")
            drows.append([Paragraph(label, st_cell), rupiah(bi.get("value", 0)),
                          rupiah(cur_val) if cur else "\u2014",
                          (("+" if delta > 0 else "") + rupiah(delta)) if delta else "\u2014"])
            deltas.append(delta)
        for it in items:
            if it["id"] not in b_ids:
                drows.append([Paragraph((it["name"] or "-")[:44] + "  (BARU)", st_cell), "\u2014",
                              rupiah(it["nilai"]), "+" + rupiah(it["nilai"])])
                deltas.append(it["nilai"])
        drows.append(["TOTAL RAB", rupiah(b_tot), rupiah(c_tot), (("+" if d_tot > 0 else "") + rupiah(d_tot)) if d_tot else "\u2014"])
        dt = Table(drows, colWidths=[content_w * 0.46, content_w * 0.18, content_w * 0.18, content_w * 0.18], repeatRows=1)
        dstyle = [("FONTSIZE", (0, 0), (-1, -1), 8), ("BACKGROUND", (0, 0), (-1, 0), NAVY), ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
                  ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"), ("ROWBACKGROUNDS", (0, 1), (-1, -2), [WHITE, BG]),
                  ("GRID", (0, 0), (-1, -1), 0.4, LINE), ("ALIGN", (1, 0), (-1, -1), "RIGHT"), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                  ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5), ("LEFTPADDING", (0, 0), (-1, -1), 6),
                  ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#E2E8F0")), ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold")]
        for idx, delta in enumerate(deltas, start=1):
            col = RED if delta > 0 else (GREEN if delta < 0 else SLATE)
            dstyle.append(("TEXTCOLOR", (3, idx), (3, idx), col))
        dstyle.append(("TEXTCOLOR", (3, len(drows) - 1), (3, len(drows) - 1), RED if d_tot > 0 else (GREEN if d_tot < 0 else INK)))
        dt.setStyle(TableStyle(dstyle))
        story.append(Spacer(1, 6))
        story.append(dt)
        story.append(Spacer(1, 4))
        arah = "kenaikan" if d_tot > 0 else ("penurunan" if d_tot < 0 else "tanpa perubahan")
        story.append(Paragraph(
            f"<font color='#2563EB'>&#9432;</font> <b>Total deviasi:</b> "
            f"<font color='{(RED if d_tot > 0 else GREEN).hexval()}'><b>{('+' if d_tot > 0 else '')}{rupiah(d_tot)} ({('+' if d_tot > 0 else '')}{pct:.1f}%)</b></font> "
            f"dari baseline &mdash; {arah} nilai RAB setelah negosiasi.", st_small))

    # Detailed per-area update history + photos
    for it in items:
        ents = entries_by_key.get(("item", it["id"]), [])
        subs = it.get("subItems", [])
        if not ents and not subs:
            continue
        story.append(Spacer(1, 8))
        story.append(Paragraph(f"<b>{it['name']}</b> &nbsp;<font size=8 color='#64748B'>Bobot {it['weight']:.2f}% &bull; Progress {int(round(it['lastProgress']))}%</font>", st_norm))

        def hist_table(rowsrc):
            hr = [["TANGGAL", "PROGRESS", "CATATAN", "FOTO"]]
            photo_cells = []
            for pe in rowsrc:
                imgs = []
                for path in (pe.get("photoUrls") or [])[:3]:
                    try:
                        c, _ = get_object(path)
                        imgs.append(RLImage(io.BytesIO(c), width=18 * mm, height=14 * mm, kind="proportional"))
                    except Exception as e:
                        logger.warning(f"progress pdf img {path}: {e}")
                pcell = Table([imgs], colWidths=[19 * mm] * len(imgs)) if imgs else Paragraph("-", st_cell)
                hr.append([_fmt(pe.get("date")), f"{pe.get('progress',0)}%", Paragraph((pe.get("notes", "") or "")[:70], st_cell), pcell])
            t = Table(hr, colWidths=[content_w * 0.16, content_w * 0.12, content_w * 0.42, content_w * 0.30], repeatRows=1)
            t.setStyle(TableStyle([("FONTSIZE", (0, 0), (-1, -1), 8), ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E2E8F0")),
                                   ("TEXTCOLOR", (0, 0), (-1, 0), INK), ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                                   ("GRID", (0, 0), (-1, -1), 0.4, LINE), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                                   ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4), ("LEFTPADDING", (0, 0), (-1, -1), 5)]))
            return t

        if subs:
            for s in subs:
                sents = entries_by_key.get(("sub", s["id"]), [])
                story.append(Paragraph(f"&nbsp;&nbsp;<font color='#1E3A8A'>&#9642;</font> <b>{s['name']}</b> <font size=7.5 color='#64748B'>({s['weight']:.2f}% &bull; {s['lastProgress']}%)</font>", st_cell))
                if sents:
                    story.append(hist_table(sents))
                    story.append(Spacer(1, 3))
        elif ents:
            story.append(hist_table(ents))

    # Signatures
    story.append(Spacer(1, 16))
    story.append(section("PERSETUJUAN & TANDA TANGAN"))
    sig = Table([[Paragraph("Dibuat oleh,<br/><br/><br/><br/>________________________<br/><b>Kontraktor Pelaksana</b>", ParagraphStyle("s1", parent=st_norm, leading=15, alignment=TA_CENTER)),
                  Paragraph(f"Diterima oleh,<br/><br/><br/><br/>________________________<br/><b>{project.get('owner') or 'Klien'}</b>", ParagraphStyle("s2", parent=st_norm, leading=15, alignment=TA_CENTER))]],
                colWidths=[content_w / 2, content_w / 2])
    sig.setStyle(TableStyle([("TOPPADDING", (0, 0), (-1, -1), 16), ("VALIGN", (0, 0), (-1, -1), "TOP")]))
    story.append(sig)

    doc.build(story, onFirstPage=draw_page, onLaterPages=draw_page)
    buf.seek(0)
    return buf.read()



def _terbilang(n):
    n = int(round(abs(n or 0)))
    satuan = ["", "satu", "dua", "tiga", "empat", "lima", "enam", "tujuh", "delapan", "sembilan",
              "sepuluh", "sebelas"]

    def _t(x):
        if x < 12:
            return satuan[x]
        if x < 20:
            return _t(x - 10) + " belas"
        if x < 100:
            return _t(x // 10) + " puluh" + ((" " + _t(x % 10)) if x % 10 else "")
        if x < 200:
            return "seratus" + ((" " + _t(x - 100)) if x - 100 else "")
        if x < 1000:
            return _t(x // 100) + " ratus" + ((" " + _t(x % 100)) if x % 100 else "")
        if x < 2000:
            return "seribu" + ((" " + _t(x - 1000)) if x - 1000 else "")
        if x < 1000000:
            return _t(x // 1000) + " ribu" + ((" " + _t(x % 1000)) if x % 1000 else "")
        if x < 1000000000:
            return _t(x // 1000000) + " juta" + ((" " + _t(x % 1000000)) if x % 1000000 else "")
        if x < 1000000000000:
            return _t(x // 1000000000) + " miliar" + ((" " + _t(x % 1000000000)) if x % 1000000000 else "")
        return _t(x // 1000000000000) + " triliun" + ((" " + _t(x % 1000000000000)) if x % 1000000000000 else "")

    if n == 0:
        return "Nol Rupiah"
    words = " ".join(_t(n).split())
    return words.strip().capitalize() + " Rupiah"


def _decode_signature(data_uri):
    """Return (BytesIO, width_px, height_px) for a base64 data URI / raw base64, else None."""
    if not data_uri or not isinstance(data_uri, str):
        return None
    try:
        raw = data_uri.split(",", 1)[1] if "," in data_uri else data_uri
        img_bytes = _b64.b64decode(raw)
        bio = io.BytesIO(img_bytes)
        ir = ImageReader(bio)
        w, h = ir.getSize()
        bio.seek(0)
        return bio, w, h
    except Exception:
        return None


def build_rab_pdf(project, rab, computed):
    """Surat Penawaran (RAB) — sections, sub-items, materials, totals, termins, bank & signatures."""
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4, leftMargin=14 * mm, rightMargin=14 * mm,
        topMargin=14 * mm, bottomMargin=14 * mm,
    )
    content_w = doc.width
    AMBER = colors.HexColor("#d97706")
    DARK = colors.HexColor("#0f172a")
    GREYTX = colors.HexColor("#475569")
    LINE = colors.HexColor("#e2e8f0")
    SECBG = colors.HexColor("#fef3c7")

    st_company = ParagraphStyle("co", fontName="Helvetica-Bold", fontSize=15, textColor=DARK, leading=17)
    st_small = ParagraphStyle("sm", fontName="Helvetica", fontSize=8, textColor=GREYTX, leading=11)
    st_title = ParagraphStyle("ti", fontName="Helvetica-Bold", fontSize=17, textColor=AMBER, leading=19, alignment=TA_RIGHT)
    st_meta = ParagraphStyle("me", fontName="Helvetica", fontSize=8.5, textColor=DARK, leading=12, alignment=TA_RIGHT)
    st_cell = ParagraphStyle("ce", fontName="Helvetica", fontSize=8.5, textColor=DARK, leading=11)
    st_cellb = ParagraphStyle("ceb", fontName="Helvetica-Bold", fontSize=8.5, textColor=DARK, leading=11)
    st_mat = ParagraphStyle("mt", fontName="Helvetica-Oblique", fontSize=7.8, textColor=GREYTX, leading=10, leftIndent=8)
    st_secname = ParagraphStyle("sn", fontName="Helvetica-Bold", fontSize=9, textColor=DARK, leading=11)
    st_num = ParagraphStyle("nu", fontName="Helvetica", fontSize=8.5, textColor=DARK, leading=11, alignment=TA_RIGHT)
    st_numb = ParagraphStyle("nub", fontName="Helvetica-Bold", fontSize=8.5, textColor=DARK, leading=11, alignment=TA_RIGHT)

    story = []
    # "Quotation by" small label so header never looks empty
    company_label = (rab.get("companyName") or "").strip()
    quotation_by = "Quotation by " + (company_label if company_label else "—")
    st_qby = ParagraphStyle("qby", fontName="Helvetica-Oblique", fontSize=7.5, textColor=AMBER, leading=10, alignment=TA_RIGHT)

    # ---- Header: company (left) + title/meta (right)
    company = rab.get("companyName") or "Perusahaan Anda"
    co_info = "<br/>".join([x for x in [rab.get("companyAddress", ""), ("Telp: " + rab["companyPhone"]) if rab.get("companyPhone") else ""] if x])
    left = [Paragraph(company, st_company)]
    if co_info:
        left.append(Paragraph(co_info, st_small))
    meta_lines = []
    if rab.get("quotationNo"):
        meta_lines.append(f"No : {rab['quotationNo']}")
    meta_lines.append("Tanggal : " + _fmt(rab.get("quotationDate")))
    right = [Paragraph("QUOTATION", st_title), Spacer(1, 2), Paragraph(quotation_by, st_qby),
             Spacer(1, 3), Paragraph("<br/>".join(meta_lines), st_meta)]
    head = Table([[left, right]], colWidths=[content_w * 0.58, content_w * 0.42])
    head.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
    story.append(head)
    story.append(Spacer(1, 6))
    story.append(Table([[""]], colWidths=[content_w], style=TableStyle([("LINEBELOW", (0, 0), (-1, -1), 1.4, AMBER)])))
    story.append(Spacer(1, 8))

    # ---- Client block
    cl = [
        [Paragraph("<b>Kepada Yth,</b>", st_cell)],
        [Paragraph(rab.get("clientName") or "-", st_cellb)],
    ]
    if rab.get("clientAddress"):
        cl.append([Paragraph(rab["clientAddress"], st_cell)])
    if rab.get("clientPhone"):
        cl.append([Paragraph("Telp: " + rab["clientPhone"], st_cell)])
    cltbl = Table(cl, colWidths=[content_w])
    cltbl.setStyle(TableStyle([("TOPPADDING", (0, 0), (-1, -1), 0.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 0.5), ("LEFTPADDING", (0, 0), (-1, -1), 0)]))
    story.append(cltbl)
    story.append(Spacer(1, 8))

    # ---- Main items table
    cw = [content_w * 0.05, content_w * 0.47, content_w * 0.08, content_w * 0.08, content_w * 0.16, content_w * 0.16]
    rows = [[Paragraph("NO", st_cellb), Paragraph("KETERANGAN", st_cellb), Paragraph("QTY", st_numb),
             Paragraph("SAT", st_cellb), Paragraph("HARGA", st_numb), Paragraph("TOTAL", st_numb)]]
    style_cmds = [
        ("BACKGROUND", (0, 0), (-1, 0), DARK),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 8.5),
        ("ALIGN", (2, 0), (2, 0), "RIGHT"),
        ("ALIGN", (4, 0), (5, 0), "RIGHT"),
        ("ALIGN", (3, 0), (3, 0), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 3.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3.5),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
    ]
    r = 1
    for sec in computed.get("sections", []):
        rows.append([Paragraph((sec.get("name") or "PEKERJAAN").upper(), st_secname), "", "", "", "",
                     Paragraph(rupiah(sec.get("subtotal", 0)), st_numb)])
        style_cmds += [("BACKGROUND", (0, r), (-1, r), SECBG), ("SPAN", (0, r), (4, r)),
                       ("FONTNAME", (5, r), (5, r), "Helvetica-Bold")]
        r += 1
        for si in sec.get("subItems", []):
            qty = si.get("qty", 0)
            qty_s = (f"{qty:.2f}".rstrip("0").rstrip(".")) if isinstance(qty, float) else str(qty)
            rows.append([
                Paragraph(str(si.get("no", "")), st_cell),
                Paragraph(si.get("name") or "-", st_cell),
                Paragraph(qty_s, st_num),
                Paragraph(si.get("unit") or "", ParagraphStyle("u", parent=st_cell, alignment=TA_CENTER)),
                Paragraph(rupiah(si.get("hargaSatuan", 0)), st_num),
                Paragraph(rupiah(si.get("nilai", 0)), st_num),
            ])
            style_cmds += [("LINEBELOW", (0, r), (-1, r), 0.4, LINE)]
            r += 1
            for m in si.get("materials", []):
                nm = m.get("name") or "-"
                val = int(m.get("nilai") or 0)
                tail = ("  (" + rupiah(val) + ")") if val else ""
                rows.append(["", Paragraph("• " + nm + tail, st_mat), "", "", "", ""])
                style_cmds += [("SPAN", (1, r), (5, r)), ("TOPPADDING", (0, r), (-1, r), 1), ("BOTTOMPADDING", (0, r), (-1, r), 1)]
                r += 1

    tbl = Table(rows, colWidths=cw, repeatRows=1)
    tbl.setStyle(TableStyle(style_cmds + [
        ("BOX", (0, 0), (-1, -1), 0.6, LINE),
        ("LINEBELOW", (0, 0), (-1, 0), 0.6, DARK),
    ]))
    story.append(tbl)
    story.append(Spacer(1, 6))

    # ---- Summary (right aligned)
    def sumrow(label, val, bold=False, big=False):
        ls = ParagraphStyle("sl", fontName="Helvetica-Bold" if bold else "Helvetica", fontSize=11 if big else 9,
                            textColor=colors.white if big else DARK, alignment=TA_RIGHT, leading=13)
        vs = ParagraphStyle("sv", fontName="Helvetica-Bold", fontSize=11 if big else 9,
                            textColor=colors.white if big else DARK, alignment=TA_RIGHT, leading=13)
        return [Paragraph(label, ls), Paragraph(rupiah(val), vs)]

    srows = [sumrow("Sub Total", computed.get("totalItems", 0))]
    if computed.get("discount", 0):
        srows.append(sumrow("Discount", -computed.get("discount", 0)))
    if computed.get("ppnEnabled"):
        srows.append(sumrow(f"PPN {computed.get('ppnPercent', 0):g}%", computed.get("ppnAmount", 0)))
    srows.append(sumrow("GRAND TOTAL", computed.get("grandTotal", 0), bold=True, big=True))
    ncols = len(srows)
    stbl = Table(srows, colWidths=[content_w * 0.22, content_w * 0.22])
    scmd = [("ALIGN", (0, 0), (-1, -1), "RIGHT"), ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ("LINEBELOW", (0, 0), (-1, ncols - 2), 0.4, LINE),
            ("BACKGROUND", (0, ncols - 1), (-1, ncols - 1), AMBER)]
    stbl.setStyle(TableStyle(scmd))
    wrap = Table([[Paragraph("<i>Terbilang: " + _terbilang(computed.get("grandTotal", 0)) + "</i>", st_small), stbl]],
                 colWidths=[content_w * 0.56, content_w * 0.44])
    wrap.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
    story.append(wrap)
    story.append(Spacer(1, 10))

    # ---- Termins
    termins = computed.get("termins", []) or []
    if termins:
        trows = [[Paragraph("METODE PEMBAYARAN", st_cellb), Paragraph("%", st_numb), Paragraph("NOMINAL", st_numb)]]
        for t in termins:
            trows.append([Paragraph(t.get("label") or "-", st_cell),
                          Paragraph(f"{t.get('percent', 0):g}%", st_num),
                          Paragraph(rupiah(t.get("nominal", 0)), st_num)])
        tt = Table(trows, colWidths=[content_w * 0.6, content_w * 0.12, content_w * 0.28])
        tt.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f1f5f9")),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("BOX", (0, 0), (-1, -1), 0.6, LINE),
            ("INNERGRID", (0, 0), (-1, -1), 0.4, LINE),
            ("TOPPADDING", (0, 0), (-1, -1), 3.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 3.5),
            ("LEFTPADDING", (0, 0), (-1, -1), 5), ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ]))
        story.append(tt)
        story.append(Spacer(1, 8))

    # ---- Bank + notes
    if rab.get("bankName") or rab.get("bankAccount"):
        bank = f"<b>Pembayaran ditransfer ke:</b> {rab.get('bankName','')} {rab.get('bankAccount','')}"
        if rab.get("bankHolder"):
            bank += f" a/n {rab['bankHolder']}"
        story.append(Paragraph(bank, st_cell))
        story.append(Spacer(1, 4))
    if rab.get("notes"):
        story.append(Paragraph(rab["notes"].replace("\n", "<br/>"), st_small))
        story.append(Spacer(1, 6))
    story.append(Paragraph(
        "<i>Informasi di atas merupakan penawaran, bukan faktur. Pekerjaan di luar penawaran akan dihitung ulang sebagai pekerjaan tambahan.</i>",
        st_small))
    story.append(Spacer(1, 16))

    # ---- Signatures (with optional uploaded signature image on the left/creator side)
    st_sig = ParagraphStyle("sg", fontName="Helvetica", fontSize=9, textColor=DARK, alignment=TA_CENTER, leading=13)
    left_name = rab.get("signerLeft") or rab.get("companyName") or "Kontraktor"
    right_name = rab.get("signerRight") or rab.get("clientName") or "Klien"

    col_w = content_w / 2
    sig_decoded = _decode_signature(rab.get("signatureImage"))
    if sig_decoded:
        bio, iw, ih = sig_decoded
        max_w = 45 * mm
        max_h = 22 * mm
        ratio = (ih / iw) if iw else 0.4
        draw_w = max_w
        draw_h = draw_w * ratio
        if draw_h > max_h:
            draw_h = max_h
            draw_w = draw_h / ratio if ratio else max_w
        sig_img = RLImage(bio, width=draw_w, height=draw_h)
        left_cell = [
            Paragraph("Hormat kami,", st_sig), Spacer(1, 4),
            sig_img, Spacer(1, 2),
            Table([[""]], colWidths=[45 * mm], style=TableStyle([("LINEBELOW", (0, 0), (-1, -1), 0.6, DARK)])),
            Paragraph(f"<b>{left_name}</b>", st_sig),
        ]
        left_tbl = Table([[c] for c in left_cell], colWidths=[col_w])
        left_tbl.setStyle(TableStyle([("ALIGN", (0, 0), (-1, -1), "CENTER"), ("TOPPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 0)]))
        left_block = left_tbl
    else:
        left_block = Paragraph(f"Hormat kami,<br/><br/><br/><br/>________________________<br/><b>{left_name}</b>", st_sig)

    sig = Table([[
        left_block,
        Paragraph(f"Menyetujui,<br/><br/><br/><br/>________________________<br/><b>{right_name}</b>", st_sig),
    ]], colWidths=[col_w, col_w])
    sig.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
    story.append(sig)

    # ---- Footer: "Quotation by" on every page
    def _rab_footer(canvas, doc_):
        canvas.saveState()
        canvas.setFont("Helvetica-Oblique", 7.5)
        canvas.setFillColor(GREYTX)
        footer_txt = quotation_by + ("  ·  Telp: " + rab["companyPhone"] if rab.get("companyPhone") else "")
        canvas.drawCentredString(A4[0] / 2, 8 * mm, footer_txt)
        canvas.setStrokeColor(LINE)
        canvas.setLineWidth(0.5)
        canvas.line(14 * mm, 11 * mm, A4[0] - 14 * mm, 11 * mm)
        canvas.restoreState()

    doc.build(story, onFirstPage=_rab_footer, onLaterPages=_rab_footer)
    buf.seek(0)
    return buf.read()



INVOICE_TITLES = {
    "proforma": "PROFORMA INVOICE",
    "final": "INVOICE",
    "retention": "INVOICE RETENSI",
}


def build_invoice_pdf(invoice, computed):
    """Invoice / Proforma / Retention invoice — company header, client, item table, totals, bank & signature."""
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4, leftMargin=14 * mm, rightMargin=14 * mm,
        topMargin=14 * mm, bottomMargin=16 * mm,
    )
    content_w = doc.width
    AMBER = colors.HexColor("#d97706")
    DARK = colors.HexColor("#0f172a")
    GREYTX = colors.HexColor("#475569")
    LINE = colors.HexColor("#e2e8f0")

    inv_type = (invoice.get("type") or "proforma").lower()
    title_txt = INVOICE_TITLES.get(inv_type, "INVOICE")

    st_company = ParagraphStyle("ico", fontName="Helvetica-Bold", fontSize=15, textColor=DARK, leading=17)
    st_small = ParagraphStyle("ism", fontName="Helvetica", fontSize=8, textColor=GREYTX, leading=11)
    st_title = ParagraphStyle("iti", fontName="Helvetica-Bold", fontSize=17, textColor=AMBER, leading=19, alignment=TA_RIGHT)
    st_meta = ParagraphStyle("ime", fontName="Helvetica", fontSize=8.5, textColor=DARK, leading=12, alignment=TA_RIGHT)
    st_cell = ParagraphStyle("ice", fontName="Helvetica", fontSize=8.5, textColor=DARK, leading=11)
    st_cellb = ParagraphStyle("iceb", fontName="Helvetica-Bold", fontSize=8.5, textColor=DARK, leading=11)
    st_num = ParagraphStyle("inu", fontName="Helvetica", fontSize=8.5, textColor=DARK, leading=11, alignment=TA_RIGHT)
    st_numb = ParagraphStyle("inub", fontName="Helvetica-Bold", fontSize=8.5, textColor=DARK, leading=11, alignment=TA_RIGHT)

    company_label = (invoice.get("companyName") or "").strip()
    issued_by = "Diterbitkan oleh " + (company_label if company_label else "—")
    st_iby = ParagraphStyle("iby", fontName="Helvetica-Oblique", fontSize=7.5, textColor=AMBER, leading=10, alignment=TA_RIGHT)

    story = []
    # ---- Header
    company = invoice.get("companyName") or "Perusahaan Anda"
    co_info = "<br/>".join([x for x in [invoice.get("companyAddress", ""), ("Telp: " + invoice["companyPhone"]) if invoice.get("companyPhone") else ""] if x])
    left = [Paragraph(company, st_company)]
    if co_info:
        left.append(Paragraph(co_info, st_small))
    meta_lines = []
    if invoice.get("number"):
        meta_lines.append(f"No : {invoice['number']}")
    if invoice.get("quotationNo"):
        meta_lines.append(f"Ref. Quotation : {invoice['quotationNo']}")
    meta_lines.append("Tanggal : " + _fmt(invoice.get("invoiceDate")))
    if invoice.get("dueDate"):
        meta_lines.append("Jatuh Tempo : " + _fmt(invoice.get("dueDate")))
    status = (invoice.get("status") or "Draft")
    meta_lines.append("Status : " + status)
    right = [Paragraph(title_txt, st_title), Spacer(1, 2), Paragraph(issued_by, st_iby),
             Spacer(1, 3), Paragraph("<br/>".join(meta_lines), st_meta)]
    head = Table([[left, right]], colWidths=[content_w * 0.58, content_w * 0.42])
    head.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
    story.append(head)
    story.append(Spacer(1, 6))
    story.append(Table([[""]], colWidths=[content_w], style=TableStyle([("LINEBELOW", (0, 0), (-1, -1), 1.4, AMBER)])))
    story.append(Spacer(1, 8))

    # ---- Proforma / retention note banner
    if inv_type == "proforma":
        story.append(Paragraph(
            "<i>Dokumen ini adalah <b>Proforma Invoice</b> (permintaan pembayaran/uang muka/termin), <b>bukan faktur pajak</b>.</i>",
            st_small))
        story.append(Spacer(1, 6))
    elif inv_type == "retention":
        story.append(Paragraph(
            "<i>Invoice penagihan <b>retensi</b> pekerjaan setelah berakhirnya masa pemeliharaan.</i>",
            st_small))
        story.append(Spacer(1, 6))

    # ---- Client block
    cl = [
        [Paragraph("<b>Kepada Yth,</b>", st_cell)],
        [Paragraph(invoice.get("clientName") or "-", st_cellb)],
    ]
    if invoice.get("clientAddress"):
        cl.append([Paragraph(invoice["clientAddress"], st_cell)])
    if invoice.get("clientPhone"):
        cl.append([Paragraph("Telp: " + invoice["clientPhone"], st_cell)])
    cltbl = Table(cl, colWidths=[content_w])
    cltbl.setStyle(TableStyle([("TOPPADDING", (0, 0), (-1, -1), 0.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 0.5), ("LEFTPADDING", (0, 0), (-1, -1), 0)]))
    story.append(cltbl)
    story.append(Spacer(1, 8))

    # ---- Payment reference (quotation) so the client knows what they are paying for
    if invoice.get("quotationNo"):
        ref_txt = f"Berdasarkan Quotation No: <b>{invoice['quotationNo']}</b>"
        if invoice.get("projectName"):
            ref_txt += f" — Proyek {invoice['projectName']}"
        story.append(Paragraph("<i>" + ref_txt + "</i>", st_small))
        story.append(Spacer(1, 6))

    # ---- Items table
    cw = [content_w * 0.06, content_w * 0.52, content_w * 0.10, content_w * 0.16, content_w * 0.16]
    rows = [[Paragraph("NO", st_cellb), Paragraph("DESKRIPSI", st_cellb), Paragraph("QTY", st_numb),
             Paragraph("HARGA SATUAN", st_numb), Paragraph("JUMLAH", st_numb)]]
    style_cmds = [
        ("BACKGROUND", (0, 0), (-1, 0), DARK),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 8.5),
        ("ALIGN", (2, 0), (4, 0), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
    ]
    r = 1
    for it in computed.get("items", []):
        qty = it.get("qty", 0)
        qty_s = (f"{qty:.2f}".rstrip("0").rstrip(".")) if isinstance(qty, float) else str(qty)
        rows.append([
            Paragraph(str(it.get("no", r)), st_cell),
            Paragraph(it.get("description") or "-", st_cell),
            Paragraph(qty_s, st_num),
            Paragraph(rupiah(it.get("unitPrice", 0)), st_num),
            Paragraph(rupiah(it.get("amount", 0)), st_num),
        ])
        style_cmds += [("LINEBELOW", (0, r), (-1, r), 0.4, LINE)]
        r += 1
    tbl = Table(rows, colWidths=cw, repeatRows=1)
    tbl.setStyle(TableStyle(style_cmds + [
        ("BOX", (0, 0), (-1, -1), 0.6, LINE),
        ("LINEBELOW", (0, 0), (-1, 0), 0.6, DARK),
    ]))
    story.append(tbl)
    story.append(Spacer(1, 6))

    # ---- Summary
    def sumrow(label, val, bold=False, big=False, color=None):
        ls = ParagraphStyle("isl", fontName="Helvetica-Bold" if bold else "Helvetica", fontSize=11 if big else 9,
                            textColor=(color or (colors.white if big else DARK)), alignment=TA_RIGHT, leading=13)
        vs = ParagraphStyle("isv", fontName="Helvetica-Bold", fontSize=11 if big else 9,
                            textColor=(color or (colors.white if big else DARK)), alignment=TA_RIGHT, leading=13)
        return [Paragraph(label, ls), Paragraph(rupiah(val), vs)]

    srows = [sumrow("Sub Total", computed.get("subtotal", 0))]
    if computed.get("ppnEnabled"):
        srows.append(sumrow(f"PPN {computed.get('ppnPercent', 0):g}%", computed.get("ppnAmount", 0)))
    ret_on = computed.get("retentionEnabled") and computed.get("retentionAmount", 0) > 0
    if ret_on:
        srows.append(sumrow("Total", computed.get("grossTotal", 0), bold=True))
        srows.append(sumrow(f"Retensi {computed.get('retentionPercent', 0):g}% dari Nilai Kontrak (ditahan)", -computed.get("retentionAmount", 0)))
    big_label = "DIBAYAR SEKARANG" if ret_on else "TOTAL TAGIHAN"
    srows.append(sumrow(big_label, computed.get("amountDue", 0), bold=True, big=True))
    ncols = len(srows)
    stbl = Table(srows, colWidths=[content_w * 0.24, content_w * 0.22])
    scmd = [("ALIGN", (0, 0), (-1, -1), "RIGHT"), ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ("LINEBELOW", (0, 0), (-1, ncols - 2), 0.4, LINE),
            ("BACKGROUND", (0, ncols - 1), (-1, ncols - 1), AMBER)]
    stbl.setStyle(TableStyle(scmd))
    wrap = Table([[Paragraph("<i>Terbilang: " + _terbilang(computed.get("amountDue", 0)) + "</i>", st_small), stbl]],
                 colWidths=[content_w * 0.54, content_w * 0.46])
    wrap.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
    story.append(wrap)
    story.append(Spacer(1, 8))

    if ret_on:
        story.append(Paragraph(
            f"<i>Retensi {computed.get('retentionPercent', 0):g}% dari Nilai Kontrak sebesar {rupiah(computed.get('retentionAmount', 0))} ditahan dan akan ditagih terpisah setelah masa pemeliharaan selesai.</i>",
            st_small))
        story.append(Spacer(1, 6))

    # ---- Bank + notes
    if invoice.get("bankName") or invoice.get("bankAccount"):
        bank = f"<b>Pembayaran ditransfer ke:</b> {invoice.get('bankName','')} {invoice.get('bankAccount','')}"
        if invoice.get("bankHolder"):
            bank += f" a/n {invoice['bankHolder']}"
        story.append(Paragraph(bank, st_cell))
        story.append(Spacer(1, 4))
    if invoice.get("notes"):
        story.append(Paragraph(invoice["notes"].replace("\n", "<br/>"), st_small))
        story.append(Spacer(1, 6))
    story.append(Spacer(1, 12))

    # ---- Signature (creator side, optional uploaded signature)
    st_sig = ParagraphStyle("isg", fontName="Helvetica", fontSize=9, textColor=DARK, alignment=TA_CENTER, leading=13)
    left_name = invoice.get("signerLeft") or invoice.get("companyName") or "Kontraktor"
    col_w = content_w / 2
    sig_decoded = _decode_signature(invoice.get("signatureImage"))
    if sig_decoded:
        bio, iw, ih = sig_decoded
        max_w = 45 * mm
        max_h = 22 * mm
        ratio = (ih / iw) if iw else 0.4
        draw_w = max_w
        draw_h = draw_w * ratio
        if draw_h > max_h:
            draw_h = max_h
            draw_w = draw_h / ratio if ratio else max_w
        sig_img = RLImage(bio, width=draw_w, height=draw_h)
        left_cell = [
            Paragraph("Hormat kami,", st_sig), Spacer(1, 4),
            sig_img, Spacer(1, 2),
            Table([[""]], colWidths=[45 * mm], style=TableStyle([("LINEBELOW", (0, 0), (-1, -1), 0.6, DARK)])),
            Paragraph(f"<b>{left_name}</b>", st_sig),
        ]
        left_tbl = Table([[c] for c in left_cell], colWidths=[col_w])
        left_tbl.setStyle(TableStyle([("ALIGN", (0, 0), (-1, -1), "CENTER"), ("TOPPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 0)]))
        left_block = left_tbl
    else:
        left_block = Paragraph(f"Hormat kami,<br/><br/><br/><br/>________________________<br/><b>{left_name}</b>", st_sig)
    sig = Table([[left_block, ""]], colWidths=[col_w, col_w])
    sig.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
    story.append(sig)

    def _inv_footer(canvas, doc_):
        canvas.saveState()
        canvas.setFont("Helvetica-Oblique", 7.5)
        canvas.setFillColor(GREYTX)
        footer_txt = issued_by + ("  ·  Telp: " + invoice["companyPhone"] if invoice.get("companyPhone") else "")
        canvas.drawCentredString(A4[0] / 2, 8 * mm, footer_txt)
        canvas.setStrokeColor(LINE)
        canvas.setLineWidth(0.5)
        canvas.line(14 * mm, 11 * mm, A4[0] - 14 * mm, 11 * mm)
        canvas.restoreState()

    doc.build(story, onFirstPage=_inv_footer, onLaterPages=_inv_footer)
    buf.seek(0)
    return buf.read()


# =====================================================================
# Laporan Upah Tukang (per tukang & keseluruhan)
# =====================================================================

def _worker_page_decor(company, subtitle):
    """Header/footer band style shared by worker reports (matches build_report_pdf)."""
    published = datetime.now().strftime("%d/%m/%Y, %H.%M")

    def draw_page(canvas, doc):
        w, h = A4
        canvas.setFillColor(INK)
        canvas.rect(0, h - 22 * mm, w, 22 * mm, fill=1, stroke=0)
        canvas.setFillColor(AMBER)
        canvas.setFont("Helvetica-Bold", 13)
        canvas.drawString(15 * mm, h - 12 * mm, company)
        canvas.setFillColor(colors.HexColor("#CBD5E1"))
        canvas.setFont("Helvetica", 7.5)
        canvas.drawString(15 * mm, h - 17 * mm, subtitle)
        canvas.setFillColor(INK)
        canvas.rect(0, 0, w, 12 * mm, fill=1, stroke=0)
        canvas.setFillColor(colors.HexColor("#CBD5E1"))
        canvas.setFont("Helvetica", 7)
        canvas.drawString(15 * mm, 4.6 * mm, f"{company}  \u2022  {subtitle.title()}")
        canvas.drawRightString(w - 15 * mm, 4.6 * mm, f"Diterbitkan: {published}  \u2022  Hal {canvas.getPageNumber()}")

    return draw_page


def _worker_styles():
    styles = getSampleStyleSheet()
    return {
        "kick": ParagraphStyle("wkick", parent=styles["Normal"], fontSize=9, textColor=AMBER, spaceAfter=2, fontName="Helvetica-Bold"),
        "title": ParagraphStyle("wtitle", parent=styles["Normal"], fontSize=24, leading=28, textColor=INK, fontName="Helvetica-Bold", spaceAfter=2),
        "sub": ParagraphStyle("wsub", parent=styles["Normal"], fontSize=11.5, leading=15, textColor=SLATE, spaceAfter=8),
        "sec": ParagraphStyle("wsec", parent=styles["Normal"], fontSize=12, textColor=INK, fontName="Helvetica-Bold", spaceBefore=10, spaceAfter=6),
        "cell": ParagraphStyle("wcell", parent=styles["Normal"], fontSize=8.5, leading=11, textColor=INK),
        "cellb": ParagraphStyle("wcellb", parent=styles["Normal"], fontSize=8.5, leading=11, textColor=INK, fontName="Helvetica-Bold"),
        "num": ParagraphStyle("wnum", parent=styles["Normal"], fontSize=8.5, leading=11, textColor=INK, alignment=TA_RIGHT),
        "numb": ParagraphStyle("wnumb", parent=styles["Normal"], fontSize=8.5, leading=11, textColor=INK, fontName="Helvetica-Bold", alignment=TA_RIGHT),
        "small": ParagraphStyle("wsmall", parent=styles["Normal"], fontSize=8, leading=11, textColor=SLATE),
        "sig": ParagraphStyle("wsig", parent=styles["Normal"], fontSize=9, leading=13, textColor=INK, alignment=TA_CENTER),
    }


def _metric_cards(items, content_w):
    """items: list of (label, value, hex_color) -> 1-row card table."""
    cells = []
    for label, value, hexcol in items:
        cells.append(Paragraph(
            f"<font size=7.5 color='#94A3B8'>{label}</font><br/>"
            f"<font size=12.5 color='{hexcol}'><b>{value}</b></font>",
            ParagraphStyle("mc", fontName="Helvetica", fontSize=9, leading=15, textColor=INK),
        ))
    n = len(items)
    t = Table([cells], colWidths=[content_w / n] * n)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), BG),
        ("BOX", (0, 0), (-1, -1), 0.6, LINE),
        ("INNERGRID", (0, 0), (-1, -1), 0.6, LINE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
    ]))
    return t


def _section_bar(title, content_w):
    t = Table([[Paragraph(title, ParagraphStyle("s", fontSize=12, textColor=INK, fontName="Helvetica-Bold"))]], colWidths=[content_w])
    t.setStyle(TableStyle([
        ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 12), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LINEBELOW", (0, 0), (-1, -1), 2, AMBER),
    ]))
    return t


def build_worker_pdf(project, worker, payments):
    """Laporan upah SATU tukang: ringkasan borongan + riwayat kasbon/pelunasan + tanda terima."""
    company = (project.get("companyName") or "ProFinance Interior").upper()
    draw_page = _worker_page_decor(company, "LAPORAN UPAH TUKANG")

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=15 * mm, rightMargin=15 * mm, topMargin=28 * mm, bottomMargin=16 * mm,
    )
    content_w = A4[0] - 30 * mm
    st = _worker_styles()
    story = []

    borongan = worker.get("borongan", 0) or 0
    kasbon = worker.get("totalKasbon", 0)
    pelunasan = worker.get("totalPelunasan", 0)
    dibayar = worker.get("totalDibayar", kasbon + pelunasan)
    sisa = worker.get("sisaHutang", borongan - dibayar)
    lunas = sisa <= 0 and borongan > 0
    paid_pct = min(100.0, (dibayar / borongan * 100.0)) if borongan > 0 else 0.0

    # ---- Title block
    story.append(Spacer(1, 6))
    story.append(Paragraph("LAPORAN UPAH TUKANG", st["kick"]))
    story.append(Paragraph(worker.get("name", "-"), st["title"]))
    story.append(Paragraph(
        f"<b>Proyek:</b> {project.get('name', '-')} &nbsp;&nbsp;&bull;&nbsp;&nbsp; "
        f"<b>Owner/Klien:</b> {project.get('owner') or '-'}", st["sub"]))

    # ---- Metric cards
    story.append(_metric_cards([
        ("NILAI BORONGAN", rupiah(borongan), "#0F172A"),
        ("TOTAL KASBON", rupiah(kasbon), "#D97706"),
        ("TOTAL PELUNASAN", rupiah(pelunasan), "#2563EB"),
        ("TOTAL DIBAYAR", rupiah(dibayar), "#16A34A"),
        ("SISA HUTANG", rupiah(max(sisa, 0)), "#B45309" if not lunas else "#15803D"),
    ], content_w))
    story.append(Spacer(1, 8))

    # ---- Status + progress
    status_txt = "LUNAS" if lunas else "BELUM LUNAS"
    status_col = GREEN if lunas else AMBER
    status_tbl = Table([[
        Paragraph(f"<b>Status Pembayaran: <font color='{'#15803D' if lunas else '#B45309'}'>{status_txt}</font></b>"
                  f" &nbsp;\u2022&nbsp; {paid_pct:.0f}% borongan terbayar", st["cell"]),
        _bar(content_w * 0.42, paid_pct / 100.0, status_col, h=8),
    ]], colWidths=[content_w * 0.56, content_w * 0.44])
    status_tbl.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0),
    ]))
    story.append(status_tbl)

    # ---- Payment history
    story.append(_section_bar("RIWAYAT PEMBAYARAN", content_w))
    cw = [content_w * 0.06, content_w * 0.14, content_w * 0.44, content_w * 0.14, content_w * 0.22]
    rows = [[Paragraph("NO", st["cellb"]), Paragraph("TANGGAL", st["cellb"]),
             Paragraph("KETERANGAN", st["cellb"]), Paragraph("TIPE", st["cellb"]),
             Paragraph("JUMLAH", st["numb"])]]
    style_cmds = [
        ("BACKGROUND", (0, 0), (-1, 0), INK),
        ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 5), ("RIGHTPADDING", (0, 0), (-1, -1), 5),
    ]
    if not payments:
        rows.append([Paragraph("-", st["cell"]), Paragraph("-", st["cell"]),
                     Paragraph("Belum ada pembayaran tercatat", st["cell"]),
                     Paragraph("-", st["cell"]), Paragraph(rupiah(0), st["num"])])
    else:
        for i, t in enumerate(payments, start=1):
            tipe = "Kasbon" if str(t.get("category", "")).startswith("Kasbon") else "Pelunasan"
            rows.append([
                Paragraph(str(i), st["cell"]),
                Paragraph(_fmt(t.get("date")), st["cell"]),
                Paragraph(t.get("description") or "-", st["cell"]),
                Paragraph(tipe, st["cell"]),
                Paragraph(rupiah(t.get("amount", 0)), st["num"]),
            ])
            style_cmds.append(("LINEBELOW", (0, i), (-1, i), 0.4, LINE))
    # total row
    last = len(rows)
    rows.append([Paragraph("", st["cellb"]), Paragraph("", st["cellb"]),
                 Paragraph("TOTAL DIBAYAR", st["cellb"]), Paragraph("", st["cellb"]),
                 Paragraph(rupiah(dibayar), st["numb"])])
    style_cmds += [
        ("BACKGROUND", (0, last), (-1, last), AMBER_L),
        ("LINEABOVE", (0, last), (-1, last), 0.8, AMBER),
        ("BOX", (0, 0), (-1, -1), 0.6, LINE),
        ("LINEBELOW", (0, 0), (-1, 0), 0.6, INK),
    ]
    tbl = Table(rows, colWidths=cw, repeatRows=1)
    tbl.setStyle(TableStyle(style_cmds))
    story.append(tbl)
    story.append(Spacer(1, 6))
    story.append(Paragraph("<i>Terbilang total dibayar: " + _terbilang(dibayar) + "</i>", st["small"]))
    if sisa > 0:
        story.append(Paragraph(
            f"<i>Sisa hutang kepada tukang sebesar <b>{rupiah(sisa)}</b> ({_terbilang(sisa)}).</i>", st["small"]))
    story.append(Spacer(1, 18))

    # ---- Signature block (tanda terima)
    company_label = project.get("companyName") or "Kontraktor"
    col_w = content_w / 2
    sig_left = Paragraph(f"Dibuat oleh,<br/><br/><br/><br/>________________________<br/><b>{company_label}</b>", st["sig"])
    sig_right = Paragraph(f"Diterima oleh,<br/><br/><br/><br/>________________________<br/><b>{worker.get('name', 'Tukang')}</b>", st["sig"])
    sig = Table([[sig_left, sig_right]], colWidths=[col_w, col_w])
    sig.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
    story.append(sig)

    doc.build(story, onFirstPage=draw_page, onLaterPages=draw_page)
    buf.seek(0)
    return buf.read()


def build_workers_pdf(project, workers):
    """Laporan KESELURUHAN tukang dalam satu proyek: rekap borongan, pembayaran & sisa hutang."""
    company = (project.get("companyName") or "ProFinance Interior").upper()
    draw_page = _worker_page_decor(company, "LAPORAN KESELURUHAN TUKANG")

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=15 * mm, rightMargin=15 * mm, topMargin=28 * mm, bottomMargin=16 * mm,
    )
    content_w = A4[0] - 30 * mm
    st = _worker_styles()
    story = []

    tot_borongan = sum(w.get("borongan", 0) or 0 for w in workers)
    tot_kasbon = sum(w.get("totalKasbon", 0) for w in workers)
    tot_pelunasan = sum(w.get("totalPelunasan", 0) for w in workers)
    tot_dibayar = sum(w.get("totalDibayar", 0) for w in workers)
    tot_sisa = sum(max(w.get("sisaHutang", 0), 0) for w in workers)
    n_lunas = sum(1 for w in workers if w.get("sisaHutang", 1) <= 0 and (w.get("borongan", 0) or 0) > 0)
    paid_pct = min(100.0, (tot_dibayar / tot_borongan * 100.0)) if tot_borongan > 0 else 0.0

    # ---- Title block
    story.append(Spacer(1, 6))
    story.append(Paragraph("LAPORAN KESELURUHAN TUKANG", st["kick"]))
    story.append(Paragraph(project.get("name", "-"), st["title"]))
    story.append(Paragraph(
        f"<b>Owner/Klien:</b> {project.get('owner') or '-'} &nbsp;&nbsp;&bull;&nbsp;&nbsp; "
        f"<b>Jumlah Tukang:</b> {len(workers)} &nbsp;&nbsp;&bull;&nbsp;&nbsp; "
        f"<b>Lunas:</b> {n_lunas} tukang", st["sub"]))

    # ---- Metric cards
    story.append(_metric_cards([
        ("TOTAL BORONGAN", rupiah(tot_borongan), "#0F172A"),
        ("TOTAL KASBON", rupiah(tot_kasbon), "#D97706"),
        ("TOTAL PELUNASAN", rupiah(tot_pelunasan), "#2563EB"),
        ("TOTAL DIBAYAR", rupiah(tot_dibayar), "#16A34A"),
        ("TOTAL SISA HUTANG", rupiah(tot_sisa), "#B45309"),
    ], content_w))
    story.append(Spacer(1, 8))

    status_tbl = Table([[
        Paragraph(f"<b>{paid_pct:.0f}%</b> dari total nilai borongan sudah dibayarkan", st["cell"]),
        _bar(content_w * 0.42, paid_pct / 100.0, GREEN if paid_pct >= 100 else AMBER, h=8),
    ]], colWidths=[content_w * 0.56, content_w * 0.44])
    status_tbl.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0),
    ]))
    story.append(status_tbl)

    # ---- Workers table
    story.append(_section_bar("REKAP PEMBAYARAN PER TUKANG", content_w))
    cw = [content_w * 0.05, content_w * 0.24, content_w * 0.15, content_w * 0.13,
          content_w * 0.13, content_w * 0.15, content_w * 0.15]
    rows = [[Paragraph("NO", st["cellb"]), Paragraph("NAMA TUKANG", st["cellb"]),
             Paragraph("BORONGAN", st["numb"]), Paragraph("KASBON", st["numb"]),
             Paragraph("PELUNASAN", st["numb"]), Paragraph("SISA HUTANG", st["numb"]),
             Paragraph("STATUS", st["cellb"])]]
    style_cmds = [
        ("BACKGROUND", (0, 0), (-1, 0), INK),
        ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 5), ("RIGHTPADDING", (0, 0), (-1, -1), 5),
    ]
    if not workers:
        rows.append([Paragraph("-", st["cell"]), Paragraph("Belum ada tukang", st["cell"]),
                     Paragraph(rupiah(0), st["num"]), Paragraph(rupiah(0), st["num"]),
                     Paragraph(rupiah(0), st["num"]), Paragraph(rupiah(0), st["num"]),
                     Paragraph("-", st["cell"])])
    else:
        for i, w in enumerate(workers, start=1):
            sisa_w = w.get("sisaHutang", 0)
            lunas_w = sisa_w <= 0 and (w.get("borongan", 0) or 0) > 0
            rows.append([
                Paragraph(str(i), st["cell"]),
                Paragraph(w.get("name", "-"), st["cell"]),
                Paragraph(rupiah(w.get("borongan", 0) or 0), st["num"]),
                Paragraph(rupiah(w.get("totalKasbon", 0)), st["num"]),
                Paragraph(rupiah(w.get("totalPelunasan", 0)), st["num"]),
                Paragraph(rupiah(max(sisa_w, 0)), st["num"]),
                Paragraph(f"<font color='{'#15803D' if lunas_w else '#B45309'}'><b>{'LUNAS' if lunas_w else 'BELUM'}</b></font>", st["cell"]),
            ])
            style_cmds.append(("LINEBELOW", (0, i), (-1, i), 0.4, LINE))
            if i % 2 == 0:
                style_cmds.append(("BACKGROUND", (0, i), (-1, i), BG))
    last = len(rows)
    rows.append([Paragraph("", st["cellb"]), Paragraph("TOTAL", st["cellb"]),
                 Paragraph(rupiah(tot_borongan), st["numb"]), Paragraph(rupiah(tot_kasbon), st["numb"]),
                 Paragraph(rupiah(tot_pelunasan), st["numb"]), Paragraph(rupiah(tot_sisa), st["numb"]),
                 Paragraph("", st["cellb"])])
    style_cmds += [
        ("BACKGROUND", (0, last), (-1, last), AMBER_L),
        ("LINEABOVE", (0, last), (-1, last), 0.8, AMBER),
        ("BOX", (0, 0), (-1, -1), 0.6, LINE),
        ("LINEBELOW", (0, 0), (-1, 0), 0.6, INK),
    ]
    tbl = Table(rows, colWidths=cw, repeatRows=1)
    tbl.setStyle(TableStyle(style_cmds))
    story.append(tbl)
    story.append(Spacer(1, 6))
    story.append(Paragraph(
        "<i>Total dibayar (kasbon + pelunasan): " + rupiah(tot_dibayar) + " \u2014 " + _terbilang(tot_dibayar) + ".</i>",
        st["small"]))
    story.append(Paragraph(
        "<i>Rincian riwayat pembayaran per tukang tersedia pada laporan individu masing-masing tukang.</i>",
        st["small"]))

    doc.build(story, onFirstPage=draw_page, onLaterPages=draw_page)
    buf.seek(0)
    return buf.read()