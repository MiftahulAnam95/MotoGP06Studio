"""Eksperimen 1 (read-only): analisis kemunculan nama rider. Jalankan: python experiments/names_occurrences.py MOTOGP.DAT"""
import re, sys, hashlib, difflib
path = sys.argv[1]
d = open(path, "rb").read()
NAMES = [b"Valentino ROSSI", b"Nicky HAYDEN", b"Colin EDWARDS", b"Max BIAGGI", b"Loris CAPIROSSI"]
def hx(b): return b.hex(" ")
def asc(b): return "".join(chr(c) if 32 <= c < 127 else "." for c in b)
print(f"file={path} size={len(d)} sha256={hashlib.sha256(d).hexdigest()}")
for n in NAMES:
    offs = [m.start() for m in re.finditer(re.escape(n), d)]
    print(f"\n== {n.decode()}: {len(offs)} kemunculan: {[hex(o) for o in offs]}")
    print("   jarak antar kemunculan:", [offs[i+1]-offs[i] for i in range(len(offs)-1)])
    print("   offset mod 2048:", [o % 2048 for o in offs])
rossi = [m.start() for m in re.finditer(b"Valentino ROSSI", d)]
print("\n### Konteks Valentino ROSSI (24 byte sebelum / sesudah)")
for o in rossi:
    print(f"0x{o:X}  before[{hx(d[o-24:o])}]  after[{hx(d[o+15:o+15+24])}]")
    print(f"        before='{asc(d[o-24:o])}' after='{asc(d[o+15:o+39])}'")
# 1) apakah pasangan kemunculan punya konteks identik? hitung prefix/suffix identik antar pasangan
print("\n### Kesamaan byte antar kemunculan (dari nama ke belakang / ke depan)")
def common_after(a, b):
    i = 0
    while a+i < len(d) and b+i < len(d) and d[a+i] == d[b+i]: i += 1
    return i
def common_before(a, b):
    i = 0
    while a-i-1 >= 0 and d[a-i-1] == d[b-i-1]: i += 1
    return i
print("pasangan (i,j): sama_ke_depan / sama_ke_belakang")
for i in range(len(rossi)):
    print(i, [(common_after(rossi[i], rossi[j]), common_before(rossi[i], rossi[j])) for j in range(len(rossi))])
# 2) urutan nama setelah ROSSI: ekstrak string ASCII panjang >=3 pada 1500 byte setelah tiap kemunculan
print("\n### Urutan string ASCII (>=3) 700 byte setelah tiap kemunculan")
seqs = []
for o in rossi:
    s = [m.group().decode() for m in re.finditer(rb"[ -~]{3,}", d[o:o+700])]
    seqs.append(s); print(hex(o), s[:40])
# 3) jarak dari ROSSI ke nama berikutnya (HAYDEN) per kemunculan
print("\n### Jarak ROSSI -> HAYDEN / Honda per kemunculan")
for o in rossi:
    h = d.find(b"HAYDEN", o); hd = d.find(b"Honda", o)
    print(hex(o), "HAYDEN +", h - o, " Honda +", hd - o)
# 4) rentang yang berisi tabel: dari 'strID' terdekat sebelum, ke 'ROSSI' terakhir kemunculan blok
print("\n### Posisi 'strID' dan 'nEntrant' (kandidat awal header field)")
print("strID:", [hex(m.start()) for m in re.finditer(b"strID", d)][:40])
print("nEntrant/Entrant:", [hex(m.start()) for m in re.finditer(b"Entrant", d)][:40])
# 5) tabel selang antar blok: bandingkan 2 blok pertama secara byte demi byte
a, b = rossi[0], rossi[1]
for width in (0x400,):
    sa, sb = d[a-0x140:a-0x140+width], d[b-0x140:b-0x140+width]
    sm = difflib.SequenceMatcher(None, sa, sb, autojunk=False)
    print(f"\n### Blok#0 vs blok#1 (window {width:#x} mulai 0x140 sebelum nama): rasio kemiripan={sm.ratio():.3f}")
    for tag, i1, i2, j1, j2 in sm.get_opcodes()[:40]:
        if tag != "equal": print(f"  {tag:8s} A[{i1:#x}:{i2:#x}]={hx(sa[i1:i2][:12])}  B[{j1:#x}:{j2:#x}]={hx(sb[j1:j2][:12])}")
