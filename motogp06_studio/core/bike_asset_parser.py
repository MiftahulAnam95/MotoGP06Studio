"""Placeholder jujur: format aset model motor MotoGP06 PSP BELUM dianalisis.
Penggantian model butuh pemahaman mesh, material, tekstur, skeleton, dan referensi (Tahap 4)."""

class AssetFormatNotMapped(NotImplementedError):
    pass

def list_models(*_a, **_k):
    raise AssetFormatNotMapped("Format aset model belum dipetakan. Perlu sampel file (lihat docs/FORMAT_NOTES.md).")
