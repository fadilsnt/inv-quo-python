import os
from fpdf import FPDF
from datetime import datetime
from db_connect import connect_db

# ─── Konstanta warna ──────────────────────────────────────────────────────────
CLR_PRIMARY   = (10,  50, 110)   # navy dalam — kontras tinggi di header
CLR_TEAL      = (32, 178, 198)   # teal vibrant sesuai logo
CLR_SECONDARY = (235, 246, 252)  # background ringan teal-ish
CLR_STRIPE    = (245, 251, 253)  # zebra stripe
CLR_TEXT_DARK = (30,  30,  30)
CLR_TEXT_GRAY = (100, 100, 100)
CLR_WHITE     = (255, 255, 255)
CLR_BORDER    = (195, 220, 235)

# ─── Dimensi halaman ──────────────────────────────────────────────────────────
PAGE_W   = 210          # A4 lebar (mm)
PAGE_H   = 297          # A4 tinggi (mm)
MARGIN   = 12           # margin kiri & kanan
CONTENT  = PAGE_W - 2 * MARGIN   # 186 mm

# Tinggi section-section FIXED (mm) — dipakai untuk menghitung sisa ruang tabel
H_HEADER   = 26    # header bar biru
H_GAP1     = 3     # jarak setelah header
H_INFO     = 26    # kotak info customer + invoice
H_GAP2     = 3     # jarak setelah info
H_TH       = 7     # header baris tabel
H_GAP3     = 3     # jarak setelah tabel (garis + ln)
H_TOTALS   = 4 * 7 + 3  # 4 baris total @ 7mm + ln kecil = 31
H_NOTES    = 14    # catatan (jika ada, disiapkan ruang)
H_ACCOUNT  = 26    # seksi rekening
H_FOOTER   = 18    # footer (dari bawah)
H_FIXED    = (H_HEADER + H_GAP1 + H_INFO + H_GAP2 +
              H_TH + H_GAP3 + H_TOTALS + H_NOTES + H_ACCOUNT + H_FOOTER)

# Kolom tabel (total = CONTENT = 186)
COL_NO    = 10
COL_DESC  = 82
COL_QTY   = 18
COL_PRICE = 38
COL_TOT   = 38


def format_rupiah(amount: float) -> str:
    """Format angka ke Rupiah gaya Indonesia (titik sebagai pemisah ribuan)."""
    if amount == int(amount):
        return "Rp {:,}".format(int(amount)).replace(",", ".")
    return "Rp {:,.2f}".format(amount).replace(",", "X").replace(".", ",").replace("X", ".")


def save_invoice_to_db(customer, items, subtotal, discount, tax, gross, notes, pdf_path):
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO invoices (customer_name, phone_number, address, date, invoice_number,
        invoice_type, status, subtotal, discount, tax, gross_amount, notes, pdf_path)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """, (
        customer['name'], customer['phone'], customer['address'], customer['date'],
        customer['invoice_number'], customer['invoice_type'], customer['status'],
        subtotal, discount, tax, gross, notes, pdf_path
    ))
    invoice_id = cursor.lastrowid
    for item in items:
        cursor.execute("""
            INSERT INTO invoice_items (invoice_id, description, quantity, unit_price, total)
            VALUES (%s, %s, %s, %s, %s)
        """, (invoice_id, item['desc'], item['qty'], item['unit_price'], item['total']))
    conn.commit()
    conn.close()


# ─── Helpers ──────────────────────────────────────────────────────────────────
def draw_hline(pdf, x1, y, x2, color=CLR_PRIMARY, lw=0.3):
    pdf.set_draw_color(*color)
    pdf.set_line_width(lw)
    pdf.line(x1, y, x2, y)


def count_lines(pdf, text, width, font=('Arial', '', 8)):
    """Estimasi jumlah baris yang dibutuhkan teks dalam lebar tertentu (mm)."""
    pdf.set_font(*font)
    words = str(text).split()
    if not words:
        return 1
    lines, cur = 1, 0.0
    for word in words:
        w = pdf.get_string_width(word + ' ')
        if cur + w > width and cur > 0:
            lines += 1
            cur = w
        else:
            cur += w
    return lines


def label_value(pdf, lx, y, label, value,
                w_lbl=22, w_colon=8, w_val=50,
                row_h=5,
                fl=('Arial', 'B', 8), fv=('Arial', '', 8)):
    """Cetak label (right-align) | ':' (center) | value (left) agar kolom sejajar."""
    pdf.set_xy(lx, y)
    pdf.set_font(*fl)
    pdf.set_text_color(*CLR_TEXT_GRAY)
    pdf.cell(w_lbl, row_h, label, 0, 0, 'R')    # label rata kanan
    pdf.set_text_color(*CLR_TEXT_GRAY)
    pdf.cell(w_colon, row_h, ':', 0, 0, 'C')    # titik dua di posisi tetap
    pdf.set_font(*fv)
    pdf.set_text_color(*CLR_TEXT_DARK)
    pdf.cell(w_val, row_h, str(value), 0, 0, 'L')  # nilai rata kiri


# ─── Generator utama ──────────────────────────────────────────────────────────
def generate_pdf(customer, items, subtotal, discount, tax, gross, notes):
    if not os.path.exists("invoices"):
        os.makedirs("invoices")

    file_name = f"invoice_{customer['invoice_number']}.pdf"
    file_path = f"invoices/{file_name}"

    pdf = FPDF('P', 'mm', 'A4')
    pdf.add_page()
    # Non-aktifkan auto page break — kita paksa 1 halaman
    pdf.set_auto_page_break(auto=False, margin=0)
    pdf.set_margins(MARGIN, MARGIN, MARGIN)

    # ── Hitung H_INFO dinamis berdasarkan panjang alamat ─────────────────────
    # Lebar nilai alamat = col_w - label(28) - padding(3+3)
    _col_w_est   = CONTENT // 2 - 1
    _addr_val_w  = _col_w_est - 3 - 22 - 8 - 2   # lebar area nilai alamat (padding+lbl+colon+kanan)
    _addr_lines  = count_lines(pdf, customer.get('address', ''), _addr_val_w)
    _extra_h     = max(0, _addr_lines - 1) * 4.8   # tambahan tinggi per baris
    H_INFO_dyn   = H_INFO + _extra_h

    # ── Hitung tinggi baris item secara dinamis ────────────────────────────────
    n_items        = max(len(items), 1)
    h_notes_actual = H_NOTES if notes else 0
    H_FIXED_dyn    = H_FIXED + _extra_h   # sesuaikan total fixed dengan H_INFO_dyn
    available      = PAGE_H - H_FIXED_dyn + (H_NOTES - h_notes_actual)
    row_h          = max(5.5, min(9.0, available / n_items))   # antara 5.5–9 mm

    # ═══════════════════════════════════════════════════════════════════════════
    # 1. WATERMARK (layer paling bawah)
    # ═══════════════════════════════════════════════════════════════════════════
    pdf.set_text_color(232, 238, 248)
    pdf.set_font("Arial", 'B', 52)
    pdf.set_xy(10, PAGE_H // 2 - 20)
    pdf.cell(CONTENT, 30, customer['invoice_type'].upper(), 0, 0, 'C')

    # ═══════════════════════════════════════════════════════════════════════════
    # 2. HEADER BAR
    # ═══════════════════════════════════════════════════════════════════════════
    pdf.set_fill_color(*CLR_PRIMARY)
    pdf.rect(0, 0, PAGE_W, H_HEADER, 'F')
    # Aksen strip teal di bagian bawah header (cocok dengan gradasi logo)
    pdf.set_fill_color(*CLR_TEAL)
    pdf.rect(0, H_HEADER - 4, PAGE_W, 4, 'F')

    # Logo di kiri header
    if os.path.exists("logo.png"):
        pdf.image("logo.png", x=MARGIN, y=3, w=18)

    # Nama perusahaan & kontak (tengah)
    pdf.set_text_color(*CLR_WHITE)
    pdf.set_font("Arial", 'B', 12)
    pdf.set_xy(0, 4)
    pdf.cell(PAGE_W, 6, "PT HEPTACLOUD DVIPANTARA TEKNOLOGI", 0, 1, 'C')
    pdf.set_font("Arial", '', 7)
    pdf.set_xy(0, 11)
    pdf.cell(PAGE_W, 4,
             "Jl. Sunan Ampel, RT.10/RW.03, Jedongcangkring, Prambon, Sidoarjo, Jawa Timur 61264",
             0, 1, 'C')
    pdf.set_xy(0, 15)
    pdf.cell(PAGE_W, 4,
             "Phone: +62 89602022145  |  Email: admin@heptacloud-dvipantara.com",
             0, 1, 'C')

    # Judul tipe dokumen (kanan bawah header)
    pdf.set_font("Arial", 'B', 13)
    pdf.set_xy(0, 19)
    pdf.cell(PAGE_W - MARGIN - 2, 6, customer['invoice_type'].upper(), 0, 0, 'R')

    # Status badge (pojok kanan atas)
    status    = customer['status'].upper()
    s_color   = (46, 160, 67) if status == "PAID" else (220, 53, 69)
    pdf.set_fill_color(*s_color)
    pdf.rect(PAGE_W - MARGIN - 20, 3, 20, 7, 'F')
    pdf.set_font("Arial", 'B', 8)
    pdf.set_xy(PAGE_W - MARGIN - 20, 3.5)
    pdf.cell(20, 6, status, 0, 0, 'C')

    # ═══════════════════════════════════════════════════════════════════════════
    # 3. INFO CUSTOMER & INVOICE (2 kotak sejajar)
    # ═══════════════════════════════════════════════════════════════════════════
    y0     = H_HEADER + H_GAP1
    col_w  = CONTENT // 2 - 1   # ~92 mm
    rx     = MARGIN + col_w + 2
    lx     = MARGIN + 3
    rh     = 4.5
    addr_val_w = col_w - 34   # lebar area nilai alamat

    # Kotak kiri — info pelanggan (tinggi dinamis)
    pdf.set_fill_color(*CLR_SECONDARY)
    pdf.set_draw_color(*CLR_BORDER)
    pdf.set_line_width(0.2)
    pdf.rect(MARGIN, y0, col_w, H_INFO_dyn, 'FD')

    pdf.set_xy(lx, y0 + 2)
    pdf.set_font("Arial", 'B', 8)
    pdf.set_text_color(*CLR_PRIMARY)
    pdf.cell(col_w - 4, 4, "INFORMASI PELANGGAN", 0, 1, 'L')
    draw_hline(pdf, lx, pdf.get_y(), MARGIN + col_w - 2)
    pdf.ln(1.5)

    # Lebar kolom label/colon/value di kartu kiri
    _lbl_w  = 22
    _col_w2 = 8
    _val_w  = col_w - 3 - _lbl_w - _col_w2 - 2   # sisa lebar untuk nilai

    # Nama
    label_value(pdf, lx, pdf.get_y(), "Nama", customer['name'],
                w_lbl=_lbl_w, w_colon=_col_w2, w_val=_val_w, row_h=rh)
    pdf.ln(rh + 0.5)
    # Telepon
    label_value(pdf, lx, pdf.get_y(), "Telepon", customer['phone'],
                w_lbl=_lbl_w, w_colon=_col_w2, w_val=_val_w, row_h=rh)
    pdf.ln(rh + 0.5)

    # Alamat — multi_cell untuk teks panjang, kolom ':' tetap sejajar
    addr_y    = pdf.get_y()
    addr_x_lbl = lx
    addr_x_col = lx + _lbl_w
    addr_x_val = lx + _lbl_w + _col_w2
    addr_val_w  = _val_w

    pdf.set_xy(addr_x_lbl, addr_y)
    pdf.set_font("Arial", 'B', 8)
    pdf.set_text_color(*CLR_TEXT_GRAY)
    pdf.cell(_lbl_w, rh, "Alamat", 0, 0, 'R')   # label rata kanan
    pdf.cell(_col_w2, rh, ':', 0, 0, 'C')        # titik dua sejajar
    pdf.set_font("Arial", '', 8)
    pdf.set_text_color(*CLR_TEXT_DARK)
    pdf.set_xy(addr_x_val, addr_y)
    pdf.multi_cell(addr_val_w, rh, customer.get('address', ''), 0, 'L')

    # Kotak kanan — detail invoice (tinggi sama dengan kiri)
    pdf.rect(rx, y0, col_w, H_INFO_dyn, 'FD')

    pdf.set_xy(rx + 3, y0 + 2)
    pdf.set_font("Arial", 'B', 8)
    pdf.set_text_color(*CLR_PRIMARY)
    pdf.cell(col_w - 4, 4, "DETAIL INVOICE", 0, 1, 'L')
    draw_hline(pdf, rx + 3, pdf.get_y(), rx + col_w - 2)
    pdf.ln(1.5)

    # Lebar kolom label/colon/value di kartu kanan
    _rlbl_w = 28
    _rcol_w = 8
    _rval_w = col_w - 3 - _rlbl_w - _rcol_w - 2

    label_value(pdf, rx + 3, pdf.get_y(), "No. Invoice", customer['invoice_number'],
                w_lbl=_rlbl_w, w_colon=_rcol_w, w_val=_rval_w, row_h=rh)
    pdf.ln(rh + 0.5)
    label_value(pdf, rx + 3, pdf.get_y(), "Tanggal", customer['date'],
                w_lbl=_rlbl_w, w_colon=_rcol_w, w_val=_rval_w, row_h=rh)
    pdf.ln(rh + 0.5)
    label_value(pdf, rx + 3, pdf.get_y(), "Tipe", customer['invoice_type'],
                w_lbl=_rlbl_w, w_colon=_rcol_w, w_val=_rval_w, row_h=rh)
    pdf.ln(rh + 0.5)
    label_value(pdf, rx + 3, pdf.get_y(), "Status", customer['status'],
                w_lbl=_rlbl_w, w_colon=_rcol_w, w_val=_rval_w, row_h=rh)

    # ═══════════════════════════════════════════════════════════════════════════
    # 4. TABEL ITEM
    # ═══════════════════════════════════════════════════════════════════════════
    pdf.set_y(y0 + H_INFO_dyn + H_GAP2)

    # Header tabel
    pdf.set_fill_color(*CLR_PRIMARY)
    pdf.set_text_color(*CLR_WHITE)
    pdf.set_font("Arial", 'B', 8)
    pdf.set_x(MARGIN)
    pdf.cell(COL_NO,    H_TH, "#",            0, 0, 'C', True)
    pdf.cell(COL_DESC,  H_TH, "Deskripsi",    0, 0, 'L', True)
    pdf.cell(COL_QTY,   H_TH, "Qty",          0, 0, 'C', True)
    pdf.cell(COL_PRICE, H_TH, "Harga Satuan", 0, 0, 'R', True)
    pdf.cell(COL_TOT,   H_TH, "Total",        0, 1, 'R', True)

    # Baris item
    pdf.set_font("Arial", '', 8)
    pdf.set_text_color(*CLR_TEXT_DARK)
    pdf.set_draw_color(*CLR_BORDER)
    pdf.set_line_width(0.15)

    for idx, item in enumerate(items, start=1):
        fill = (idx % 2 == 0)
        pdf.set_fill_color(*(CLR_STRIPE if fill else CLR_WHITE))
        pdf.set_x(MARGIN)
        pdf.cell(COL_NO,    row_h, str(idx),                          'B', 0, 'C', fill)
        pdf.cell(COL_DESC,  row_h, item['desc'],                      'B', 0, 'L', fill)
        pdf.cell(COL_QTY,   row_h, str(item['qty']),                  'B', 0, 'C', fill)
        pdf.cell(COL_PRICE, row_h, format_rupiah(item['unit_price']), 'B', 0, 'R', fill)
        pdf.cell(COL_TOT,   row_h, format_rupiah(item['total']),      'B', 1, 'R', fill)

    draw_hline(pdf, MARGIN, pdf.get_y(), MARGIN + CONTENT, CLR_PRIMARY, 0.4)
    pdf.ln(H_GAP3)

    # ═══════════════════════════════════════════════════════════════════════════
    # 5. RINGKASAN TOTAL (rata kanan)
    # ═══════════════════════════════════════════════════════════════════════════
    tw_lbl = 48
    tw_val = COL_TOT
    tx     = MARGIN + CONTENT - tw_lbl - tw_val
    trh_n  = 6.5   # tinggi baris normal
    trh_h  = 7     # tinggi baris highlight

    def total_row(label, val_str, highlight=False):
        pdf.set_x(tx)
        if highlight:
            pdf.set_fill_color(*CLR_PRIMARY)
            pdf.set_text_color(*CLR_WHITE)
            pdf.set_font("Arial", 'B', 9)
            pdf.cell(tw_lbl, trh_h, label,   0, 0, 'R', True)
            pdf.cell(tw_val, trh_h, val_str, 0, 1, 'R', True)
        else:
            pdf.set_fill_color(*CLR_SECONDARY)
            pdf.set_text_color(*CLR_TEXT_DARK)
            pdf.set_font("Arial", '', 8)
            pdf.cell(tw_lbl, trh_n, label,   0, 0, 'R', True)
            pdf.cell(tw_val, trh_n, val_str, 0, 1, 'R', True)
        pdf.ln(0.5)

    total_row("Subtotal :",    format_rupiah(subtotal))
    # total_row("Diskon :",      format_rupiah(discount))
    # total_row("Pajak :",       f"{tax:.2f}%")
    total_row("TOTAL BAYAR :", format_rupiah(gross), highlight=True)

    pdf.ln(3)

    # ═══════════════════════════════════════════════════════════════════════════
    # 6. CATATAN (jika ada)
    # ═══════════════════════════════════════════════════════════════════════════
    if notes:
        pdf.set_x(MARGIN)
        pdf.set_font("Arial", 'B', 8)
        pdf.set_text_color(*CLR_PRIMARY)
        pdf.cell(CONTENT // 2, 4.5, "Catatan:", 0, 1, 'L')
        pdf.set_x(MARGIN)
        pdf.set_font("Arial", 'I', 8)
        pdf.set_text_color(*CLR_TEXT_GRAY)
        pdf.multi_cell(CONTENT // 2, 4.5, notes, 0)
        pdf.ln(2)

    # ═══════════════════════════════════════════════════════════════════════════
    # 7. INFORMASI PEMBAYARAN
    # ═══════════════════════════════════════════════════════════════════════════
    acc_w   = int(CONTENT * 0.62)
    acc_y   = PAGE_H - H_FOOTER - H_ACCOUNT + 2
    acc_h   = H_ACCOUNT - 4

    pdf.set_font("Arial", 'B', 9)
    pdf.set_text_color(*CLR_PRIMARY)
    pdf.set_xy(MARGIN, acc_y)
    pdf.cell(acc_w, 5, "Informasi Pembayaran", 0, 1, 'L')
    draw_hline(pdf, MARGIN, pdf.get_y(), MARGIN + acc_w, CLR_PRIMARY, 0.4)
    pdf.ln(1.5)

    pdf.set_fill_color(*CLR_SECONDARY)
    pdf.set_draw_color(*CLR_BORDER)
    pdf.set_line_width(0.2)
    box_y = pdf.get_y()
    pdf.rect(MARGIN, box_y, acc_w, acc_h - 8, 'FD')

    pdf.set_xy(MARGIN + 4, box_y + 2)
    pdf.set_font("Arial", '', 8)
    pdf.set_text_color(*CLR_TEXT_GRAY)
    pdf.cell(26, 4.5, "Bank BRI :", 0, 0, 'L')
    pdf.set_font("Arial", 'B', 8)
    pdf.set_text_color(*CLR_TEXT_DARK)
    pdf.cell(acc_w - 30, 4.5, "316301009917500", 0, 1, 'L')

    pdf.set_xy(MARGIN + 4, pdf.get_y() + 1)
    pdf.set_font("Arial", '', 8)
    pdf.set_text_color(*CLR_TEXT_GRAY)
    pdf.cell(26, 4.5, "A/N :", 0, 0, 'L')
    pdf.set_font("Arial", 'B', 8)
    pdf.set_text_color(*CLR_TEXT_DARK)
    pdf.cell(acc_w - 30, 4.5, "MUHAMMAD FADIL SANTOSO", 0, 1, 'L')

    pdf.set_xy(MARGIN + 4, pdf.get_y() + 1.5)
    pdf.set_font("Arial", 'I', 7)
    pdf.set_text_color(*CLR_TEXT_GRAY)

    # ═══════════════════════════════════════════════════════════════════════════
    # 8. FOOTER (anchor dari bawah)
    # ═══════════════════════════════════════════════════════════════════════════
    fy = PAGE_H - H_FOOTER
    draw_hline(pdf, MARGIN, fy, MARGIN + CONTENT, CLR_PRIMARY, 0.5)

    pdf.set_xy(MARGIN, fy + 2)
    pdf.set_font("Arial", 'I', 7.5)
    pdf.set_text_color(*CLR_TEXT_GRAY)
    pdf.cell(
        CONTENT, 5,
        "PT HEPTACLOUD DVIPANTARA TEKNOLOGI",
        0, 1, 'C'
    )
    pdf.set_x(MARGIN)
    pdf.set_font("Arial", '', 7)
    pdf.set_text_color(175, 175, 175)

    pdf.output(file_path)
    return file_path