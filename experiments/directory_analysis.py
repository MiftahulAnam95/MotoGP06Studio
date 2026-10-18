"""Eksperimen 2 (READ-ONLY): pencarian direktori/pointer/struktur container di MOTOGP.DAT.
Jalankan: python experiments/directory_analysis.py MOTOGP.DAT > reports/directory_analysis.txt
Butuh numpy. File dibuka mode 'r' (memmap), tidak pernah ditulis."""
import sys, os, re, struct, zlib, hashlib, subprocess, collections
import numpy as np

PATH = sys.argv[1]
SEC = 2048
mm = np.memmap(PATH, dtype=np.uint8, mode="r")
SIZE = len(mm)
raw = memoryview(mm)          # tampilan read-only
def B(a, n): 
    assert 0 <= a and a + n <= SIZE, f"rentang luar batas {a:#x}+{n}"
    return bytes(raw[a:a + n])
def hx(b): return b.hex(" ")
def asc(b): return "".join(chr(c) if 32 <= c < 127 else "." for c in b)
def H(t): print(f"\n{'='*8} {t} {'='*8}")

print(f"file={PATH} size={SIZE} sectors={SIZE/SEC}")
sha = hashlib.sha256()
for i in range(0, SIZE, 1 << 24): sha.update(raw[i:i + (1 << 24)])
print("sha256", sha.hexdigest())

# ---------------------------------------------------------------- A. reproduksibilitas
H("A. Reproduksibilitas eksperimen 1")
here = os.path.dirname(os.path.abspath(__file__))
prev = os.path.join(here, "..", "reports", "names_occurrences.txt")
out = subprocess.run([sys.executable, os.path.join(here, "names_occurrences.py"), PATH], capture_output=True, text=True).stdout
if os.path.exists(prev):
    old = open(prev).read()
    print("hasil ulang identik dengan reports/names_occurrences.txt:", out == old)
    if out != old:
        import difflib
        for l in list(difflib.unified_diff(old.splitlines(), out.splitlines(), lineterm=""))[:30]: print("  ", l)
else:
    print("laporan lama tidak ditemukan")

# ---------------------------------------------------------------- C. PNG
H("C. Verifikasi PNG (chunk walk + CRC)")
data_for_find = bytes(raw)  # 137 MB; aman untuk RAM 4 GB
sig = b"\x89PNG\r\n\x1a\n"
cands = [m.start() for m in re.finditer(re.escape(sig), data_for_find)]
pngs, fails = [], []
for o in cands:
    p, ok, why, w, h = o + 8, True, "", 0, 0
    nchunks = 0
    while True:
        if p + 12 > SIZE: ok, why = False, "terpotong"; break
        ln, typ = struct.unpack(">I", data_for_find[p:p+4])[0], data_for_find[p+4:p+8]
        if ln > SIZE or p + 12 + ln > SIZE: ok, why = False, f"panjang chunk {ln} tak wajar @{p:#x}"; break
        crc = struct.unpack(">I", data_for_find[p+8+ln:p+12+ln])[0]
        if zlib.crc32(data_for_find[p+4:p+8+ln]) & 0xFFFFFFFF != crc: ok, why = False, f"CRC salah chunk {typ!r} @{p:#x}"; break
        if typ == b"IHDR": w, h = struct.unpack(">II", data_for_find[p+8:p+16])
        nchunks += 1; p += 12 + ln
        if typ == b"IEND": break
        if nchunks > 5000: ok, why = False, "terlalu banyak chunk"; break
    (pngs if ok else fails).append((o, p, w, h, nchunks) if ok else (o, why))
print(f"kandidat signature={len(cands)} valid_penuh(CRC+IEND)={len(pngs)} gagal={len(fails)}")
for f in fails: print("  GAGAL", hex(f[0]), f[1])
dims = collections.Counter((w, h) for _, _, w, h, _ in pngs); print("dimensi:", dict(dims))
al = [x for x in pngs if x[0] % SEC == 0]
print(f"offset awal selaras 2048: {len(al)}/{len(pngs)}; tidak selaras: {[hex(x[0]) for x in pngs if x[0] % SEC]}")
print(f"offset AKHIR selaras 2048: {sum(1 for x in pngs if x[1] % SEC == 0)}/{len(pngs)} (akhir = offset setelah IEND+CRC)")
rows = []
for i, (o, e, w, h, nc) in enumerate(pngs):
    nxt = pngs[i + 1][0] if i + 1 < len(pngs) else None
    pad = 0
    while e + pad < SIZE and raw[e + pad] == 0 and pad < 8192: pad += 1
    up = -(-e // SEC) * SEC
    rows.append((i, o, e - o, w, h, e, pad, up, nxt, B(o - 8, 8) if o >= 8 else b""))
print("\n idx  start     len    WxH      end       zero_pad  align_up(end)  next_start  gap_to_next  before8")
for r in rows:
    i, o, ln, w, h, e, pad, up, nxt, bf = r
    print(f"{i:4d} {o:#9x} {ln:7d} {w:4d}x{h:<4d} {e:#9x} {pad:6d}   {up:#9x}   {('%#x' % nxt) if nxt else '-':>9} {(nxt - e) if nxt else 0:10d}  {hx(bf)}")
packed = sum(1 for r in rows if r[8] and r[8] == r[7]); contig = sum(1 for r in rows if r[8])
print(f"\nPNG berikutnya tepat di align_up(akhir): {packed}/{contig} pasangan berurutan")
gapc = collections.Counter(( (r[8]-r[7]) if r[8] else None) for r in rows)
print("selisih next_start - align_up(end) (sektor 2048 byte) terbanyak:", [(k//SEC if k is not None else None, v) for k, v in gapc.most_common(8)])
nonz = 0
for r in rows:
    i, o, ln, w, h, e, pad, up, nxt, bf = r
    if nxt and nxt - e <= 65536 and any(raw[e:min(nxt, e + 65536)][pad:] ) : nonz += 1
print("PNG yang di antara akhirnya dan PNG berikutnya (<=64 KiB) ada byte non-nol setelah padding nol awal:", nonz)
runs = []
for r in rows:
    if runs and r[1] - runs[-1][-1][5] <= 65536: runs[-1].append(r)
    else: runs.append([r])
print("kelompok PNG berdekatan (<=64 KiB antar PNG):", [(hex(g[0][1]), len(g)) for g in runs])
print("\nAnalisis modul: 144x80 & aset kecil:", [(hex(r[1]), r[3], r[4], r[2]) for r in rows if (r[3], r[4]) != (480, 272)][:12])

# ---------------------------------------------------------------- peta sektor
H("Peta sektor (kelas per sektor 2048)")
nsec = SIZE // SEC
png_cov = np.zeros(nsec + 1, dtype=bool)
for o, e, *_ in pngs: png_cov[o // SEC:(e - 1) // SEC + 1] = True
sectors = np.asarray(mm[:nsec * SEC]).reshape(nsec, SEC)
zero = ~sectors.any(axis=1)
cls = np.where(zero, "Z", np.where(png_cov[:nsec], "P", "D"))
print("jumlah sektor: zero=%d png=%d data_lain=%d" % ((cls == "Z").sum(), (cls == "P").sum(), (cls == "D").sum()))
runs2 = []; s = 0
for i in range(1, nsec + 1):
    if i == nsec or cls[i] != cls[s]: runs2.append((cls[s], s, i - s)); s = i
print("jumlah run kelas:", len(runs2))
print("run non-D / run panjang: ", [(c, hex(a * SEC), n) for c, a, n in runs2 if c != 'D' and n >= 8][:40])
print("5 run D terpanjang:", [(hex(a * SEC), n) for c, a, n in sorted([r for r in runs2 if r[0]=='D'], key=lambda r: -r[2])[:5]])
first_png_sec = min(o for o, *_ in pngs) // SEC
print("PNG pertama pada sektor", first_png_sec, "; PNG terakhir berakhir sektor", max(e for _, e, *_ in pngs) // SEC)
print("sektor terakhir non-zero:", int(np.nonzero(~zero)[0].max()), "dari", nsec - 1, "; sektor zero setelah itu:", int(nsec - 1 - np.nonzero(~zero)[0].max()))

# ---------------------------------------------------------------- D. pencarian pointer
H("D1. Pencarian nilai-jangkar (offset/sektor PNG) di seluruh file")
png_starts = sorted(o for o, *_ in pngs if o % SEC == 0)
anchors_byte = np.array(png_starts, dtype=np.uint64)
anchors_sec = np.array([o // SEC for o in png_starts], dtype=np.uint64)
def lut(vals, n):
    t = np.zeros(n, dtype=bool); t[np.asarray(vals, dtype=np.int64)] = True; return t
LUT_OFF = lut(anchors_byte, SIZE + 1)
LUT_SEC = lut(anchors_sec, nsec + 1)
def hits(arr, table):
    m = arr < len(table)
    idx = np.nonzero(m)[0]
    h = idx[table[arr[idx].astype(np.int64)]]
    return h
def cluster(pos, step, win, minhits):
    pos = np.sort(pos); out = []; i = 0
    while i < len(pos):
        j = i
        while j + 1 < len(pos) and pos[j + 1] - pos[j] <= win: j += 1
        if j - i + 1 >= minhits: out.append((int(pos[i]), int(pos[j]), j - i + 1))
        i = j + 1
    return out
def view(dtype, phase, byteorder):
    n = (SIZE - phase) // np.dtype(dtype).itemsize
    a = np.frombuffer(mm, dtype=np.dtype(dtype).newbyteorder(byteorder), count=n, offset=phase)
    return a
summary = []
for name, table, dtypes in [("offset_byte", LUT_OFF, ["u4"]), ("sektor_idx", LUT_SEC, ["u4", "u2"])]:
    for dt in dtypes:
        for bo in "<>":
            tot = 0; cl_all = []
            for ph in range(0, 4 if dt == "u4" else 2):
                a = view(dt, ph, bo)
                h = hits(a, table)
                tot += len(h)
                sz = a.dtype.itemsize
                cl_all += [(ph, *c) for c in cluster(h.astype(np.int64) * sz + ph, sz, 64, 4)]
            summary.append((name, dt, bo, tot, cl_all))
            print(f"{name:11s} {dt} {'LE' if bo=='<' else 'BE'}: total_hit={tot}  klaster(>=4 hit dalam 64B)={len(cl_all)}  contoh={[(f'{c[1]:#x}-{c[2]:#x}',c[3]) for c in cl_all[:6]]}")
print("(Catatan: untuk u32 byte-offset, hit acak diharapkan ~", round((SIZE/4)*len(png_starts)/2**32 * 4, 2), "; sektor_idx lebih banyak acak karena nilai kecil umum.)")

H("D2. Run nilai u32 menaik (kandidat tabel offset) dan pasangan (offset,panjang)")
cand_tables = []
for bo in "<>":
    for ph in range(4):
        a = view("u4", ph, bo).astype(np.int64)
        ok = (a > 0) & (a < SIZE)
        asc_ = a[1:] > a[:-1]
        good = ok[1:] & ok[:-1] & asc_
        # run >= 8 entri menaik berturut-turut
        k = 7
        r = good[:len(good) - k + 1].copy()
        for s_ in range(1, k): r &= good[s_:len(good) - k + 1 + s_]
        idx = np.nonzero(r)[0]
        start = None; last = None
        for i in idx:
            if start is None: start = last = i
            elif i == last + 1: last = i
            else: cand_tables.append((bo, ph, int(start), int(last) + k + 1)); start = last = i
        if start is not None: cand_tables.append((bo, ph, int(start), int(last) + k + 1))
print(f"run menaik >=8 entri (u32, semua fase/endian): {len(cand_tables)}")
tab = []
for bo, ph, s_, e_ in cand_tables:
    a = view("u4", ph, bo)[s_:e_].astype(np.int64)
    sec_al = int((a % SEC == 0).sum()); tgt_png = int(sum(1 for v in a if v in set(png_starts)))
    tab.append((e_ - s_, bo, ph, s_ * 4 + ph, sec_al, tgt_png, a[:4].tolist()))
tab.sort(reverse=True)
print("panjang  endian  fase  offset_awal  n_selaras2048  n_target_PNG  4_nilai_pertama")
for t in tab[:25]: print(f"{t[0]:7d}  {'LE' if t[1]=='<' else 'BE'}     {t[2]}  {t[3]:#10x}  {t[4]:9d}  {t[5]:9d}   {t[6]}")
print("total target PNG tepat oleh semua run:", sum(t[5] for t in tab), "; run dengan >=3 target PNG:", sum(1 for t in tab if t[5] >= 3))
# pasangan (offset,panjang) dengan off_i+len_i <= off_{i+1}
pair_found = []
for bo in "<>":
    for ph in range(4):
        a = view("u4", ph, bo).astype(np.int64)
        n = len(a) - 3
        p = (a[:n] > 0) & (a[:n] < SIZE) & (a[1:n+1] > 0) & (a[1:n+1] < (1 << 24)) & (a[:n] + a[1:n+1] <= a[2:n+2]) & (a[2:n+2] < SIZE)
        k = 6
        r = p[:len(p) - 2 * k].copy()
        for s_ in range(1, k): r &= p[2 * s_:len(p) - 2 * k + 2 * s_]
        idx = np.nonzero(r)[0]
        if len(idx): pair_found.append((bo, ph, len(idx), [f"{(int(i)*4+ph):#x}" for i in idx[:5]]))
print("kandidat pasangan (offset,panjang) menaik >=6 entri:", pair_found if pair_found else "tidak ada")

# ---------------------------------------------------------------- B. area sekitar tabel rider
H("B. Area di sekitar tabel rider (strID / Entrant)")
strid = [m.start() for m in re.finditer(b"strID", data_for_find)]
print("strID:", [hex(x) for x in strid])
print("jarak antar strID:", [strid[i+1] - strid[i] for i in range(len(strid)-1)])
for o in strid:
    pre = B(max(0, o - 48), min(48, o))
    print(f"\n@{o:#x}  mod2048={o % SEC}\n   48B sebelum: {hx(pre)}\n   ascii      : {asc(pre)}")
    print(f"   64B sesudah: {asc(B(o, 64))}")
    # nilai integer 16/32 bit yang sama dengan jarak/ukuran blok di sekitar
    nxts = [x for x in strid if x > o]
    dist = (nxts[0] - o) if nxts else None
    seg = B(max(0, o - 32), min(32, o))
    found = []
    for off in range(len(seg) - 1):
        v16 = seg[off] | seg[off+1] << 8; w16 = seg[off] << 8 | seg[off+1]
        if dist and (abs(v16 - dist) <= 16 or abs(w16 - dist) <= 16): found.append(("u16", off - len(seg), v16, w16))
    for off in range(len(seg) - 3):
        v = struct.unpack_from("<I", seg, off)[0]; w = struct.unpack_from(">I", seg, off)[0]
        if dist and (abs(v - dist) <= 16 or abs(w - dist) <= 16): found.append(("u32", off - len(seg), v, w))
    print(f"   jarak_ke_strID_berikut={dist}; nilai di 32B sebelumnya yang mendekati jarak (+-16): {found}")
# blok antara strID terakhir grup dan awal blok berikutnya
print("\nUrutan field header pertama pada tiap strID (ASCII 160B):")
for o in strid: print(f"  {o:#x}: {asc(B(o, 160))}")

H("B2. Perbandingan struktur grup A vs B (14 strID)")
gA = [x for x in strid if 0x94000 <= x < 0x99000]; gB = [x for x in strid if 0x9cc00 <= x < 0xa0000]
print("grup A:", [hex(x) for x in gA], "\ngrup B:", [hex(x) for x in gB])
print("byte pertama header (16B) A vs B:", hx(B(gA[0], 16)), "|", hx(B(gB[0], 16)))
print("byte tepat sebelum header A0 / B0 (16B):", hx(B(gA[0]-16, 16)), "|", hx(B(gB[0]-16, 16)))
print("area akhir grup A (setelah blok terakhir, 96B @ strID_A4+4801):", hx(B(gA[-1] + 4800, 96)))
print("area akhir grup B (96B @ strID_B4+3040):", hx(B(gB[-1] + 3040, 96)))
print("ASCII region tabel lain: 0x9bf0a..0x9c4a0:", asc(B(0x9bf0a, 0x300)))

H("B3. Apakah ada nilai yang menunjuk ke posisi blok tabel rider (0x93xxx-0xa3xxx)?")
targets = set(strid) | {0x56e}
LUT_T = lut(sorted(targets), SIZE + 1)
for bo in "<>":
    for dt, ph_n in (("u4", 4), ("u2", 2)):
        if dt == "u2": continue
        tot = []
        for ph in range(ph_n):
            a = view(dt, ph, bo); h = hits(a, LUT_T)
            tot += [(int(i) * 4 + ph, int(a[i])) for i in h]
        print(f"{'LE' if bo=='<' else 'BE'} u32 yang sama dengan offset strID/0x56E: {len(tot)} hit:", [(hex(p), hex(v)) for p, v in tot[:10]])
sec_targets = sorted({t // SEC for t in targets}); LUT_S2 = lut(sec_targets, nsec + 1)
print("nilai sektor strID:", [hex(x) for x in sec_targets])
for bo in "<>":
    tot = []
    for ph in range(4):
        a = view("u4", ph, bo); h = hits(a, LUT_S2); tot += [(int(i) * 4 + ph, int(a[i])) for i in h]
    print(f"{'LE' if bo=='<' else 'BE'} u32 = indeks sektor blok strID: {len(tot)} hit (sektor nilai kecil, banyak kebetulan)")

H("E. Pembantahan/validasi kandidat")
# E1: run menaik dengan selisih konstan = deret aritmetika (bukan pointer)
const = nonconst = 0; nonconst_list = []
for bo, ph, s_, e_ in cand_tables:
    a = view("u4", ph, bo)[s_:e_].astype(np.int64); d_ = np.diff(a)
    if (d_ == d_[0]).all(): const += 1
    else: nonconst += 1; nonconst_list.append((e_ - s_, bo, ph, s_ * 4 + ph, a[:3].tolist()))
print(f"E1 run menaik: deret aritmetika (selisih konstan)={const}; non-konstan={nonconst}")
nonconst_list.sort(reverse=True)
print("   10 run non-konstan terpanjang:", [(n, 'LE' if bo=='<' else 'BE', f'{o:#x}', v) for n, bo, ph, o, v in nonconst_list[:10]])
pngset = set(png_starts)
print("E1b run dengan >=3 target PNG (detail):")
for n, bo, ph, o, sel, tp, first in tab:
    if tp >= 3:
        a = view("u4", ph, bo)[(o - ph)//4:(o - ph)//4 + n].astype(np.int64)
        print(f"   {n} entri {'LE' if bo=='<' else 'BE'} @{o:#x}: selisih unik={sorted(set(np.diff(a).tolist()))[:5]} target_PNG={[hex(int(v)) for v in a if int(v) in pngset][:6]} awal={a[:4].tolist()}")
# E2: klaster 'sektor_idx u32 LE': lihat pasangan nilai di sekitarnya
print("E2 klaster sektor_idx u32 LE (isi 8 u32 pertama):")
for name, dt, bo, tot, cl in summary:
    if name == "sektor_idx" and dt == "u4" and bo == "<":
        for ph, a0, a1, n in cl:
            v = np.frombuffer(mm, dtype="<u4", count=8, offset=a0 - a0 % 4 if ph == 0 else a0)
            print(f"   {a0:#x}-{a1:#x} n={n}: u32={v.tolist()}; sebagai float32 pasangan={[round(float(x),2) for x in v.view('<f4')[1::2]]}")
        same = len({bytes(raw[a0 - 0x20:a0 + 0x60]) for ph, a0, a1, n in cl})
        print(f"   jumlah isi unik (128 byte sekitar klaster): {same} dari {len(cl)} klaster -> {'identik semua (blok data berulang)' if same == 1 else 'berbeda'}")
# E3: hit LE offset strID periodik
h3 = [(0x690589 + k * 0x480000) for k in range(7)]
print("E3 hit u32=0x9FCAD pada alamat berjarak tetap 0x480000 (= 2304 sektor):", all(raw[a:a+4] == bytes([0xAD,0xFC,0x09,0x00]) for a in h3 if a + 4 <= SIZE), "-> pola berulang di data periodik, bukan pointer")

H("E4. Tabel offset menaik di dalam aliran bertoken (kandidat kuat, sub-sistem suara)")
seq = bytes.fromhex("80150300a01c0300302603009" + "02e0300f0360300e03f0300")
occ = [m.start() for m in re.finditer(re.escape(seq), data_for_find)]
print("urutan literal 6 u32 (0x31580,0x31CA0,0x32630,0x32E90,0x336F0,0x33FE0) ditemukan di:", [hex(x) for x in occ])
offs = [0x31580, 0x31ca0, 0x32630, 0x32e90, 0x336f0, 0x33fe0, 0x36160, 0x36a50, 0x372b0, 0x37b10, 0x38370, 0x38bd0, 0x394c0, 0x39d20]
print("nilai u32 yang terbaca literal pada urutan di atas -> semua kelipatan 16:", all(o % 16 == 0 for o in offs), "| menaik:", offs == sorted(offs), "| < ukuran file:", max(offs) < SIZE)
print("P(14 nilai acak seluruhnya kelipatan 16) = 16^-14 = %.2e (hanya 14 nilai terbaca utuh; 0x34840 dan 3 entri sesudahnya terpotong token)" % (16.0 ** -14))
fr = (np.asarray(mm[1::16]) == 2)
rr = []; st = None
for i, v in enumerate(fr):
    if v and st is None: st = i
    if (not v) and st is not None:
        if i - st >= 512: rr.append((st * 16, (i - st)))
        st = None
print("run >=512 frame 16-byte berturut-turut dengan byte[1]==0x02 (offset, jumlah frame):", [(hex(a), n) for a, n in rr][:12])
print("target tabel pertama/terakhir di dalam run tersebut:", [(hex(o), any(a <= o < a + n * 16 for a, n in rr)) for o in (offs[0], offs[-1])])
print("Tafsir alternatif 'nilai x 256' (menunjuk PNG): target tepat pada awal PNG =", sum((o * 256) in pngset for o in offs[6:]), "dari 8 nilai (0x36160..0x39D20) ->", "ditolak sebagai pemetaan konsisten (5/8 bukan awal PNG)")
print("Salinan urutan 36 byte (9 nilai) pada 0x524851B dan 0x672C8A7: isi konteks identik 64 byte ->", B(0x524851b-16, 80) == B(0x672c8a7-16, 80))

H("E5. Analisis hit nilai offset-PNG (u32 LE) yang melebihi ekspektasi acak")
hl = []
for ph in range(4):
    a = view("u4", ph, "<"); h = hits(a, LUT_OFF)
    hl += [(int(i) * 4 + ph, int(a[i])) for i in h]
vals = collections.Counter(v for _, v in hl)
print(f"hit LE={len(hl)}; nilai berbeda={len(vals)}; fase 0={sum(1 for p_, _ in hl if p_ % 4 == 0)}")
print("nilai terbanyak:", [(hex(v), n) for v, n in vals.most_common(6)])
print("posisi hit per 16 MiB:", dict(collections.Counter(p_ >> 24 for p_, _ in hl)))
low = sum(1 for _, v in hl if v % 0x10000 == 0 or (v & 0xFF) == 0)
print("hit dengan byte rendah nol (nilai bulat, mudah kebetulan):", low)
pos_sorted = sorted(p_ for p_, _ in hl)
print("jarak antar hit berurutan (10 pertama):", [pos_sorted[i+1]-pos_sorted[i] for i in range(10)])
gaps = collections.Counter(pos_sorted[i+1]-pos_sorted[i] for i in range(len(pos_sorted)-1))
print("jarak antar-hit paling sering:", gaps.most_common(5))

H("RINGKASAN OTOMATIS")
print("PNG valid penuh:", len(pngs), "| selaras awal:", len(al), "| berurutan rapat (next=align_up(end)):", packed, "/", contig)
print("kandidat tabel menaik:", len(tab), "| dengan >=3 target PNG:", sum(1 for t in tab if t[5] >= 3))
