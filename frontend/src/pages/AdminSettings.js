import { useEffect, useState, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { api, fileUrl } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { Header } from "@/components/Header";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Switch } from "@/components/ui/switch";
import { ArrowLeft, Settings, Loader2, ShieldCheck, Save, Tag, Trash2, Image as ImageIcon, Plus, RefreshCw, QrCode, CreditCard, Banknote, Eye, CheckCircle2, XCircle } from "lucide-react";
import { rupiah } from "@/lib/format";
import { toast } from "sonner";

function priceHint(base, promo, promoActive) {
  const b = Number(base) || 0;
  const p = Number(promo) || 0;
  if (promoActive && p > 0 && p < b) {
    const disc = Math.round((1 - p / b) * 100);
    return `Aktif: pelanggan bayar ${rupiah(p)} (dari ${rupiah(b)}, hemat ${disc}%).`;
  }
  return `Pelanggan bayar ${rupiah(b)} (harga normal).`;
}

function isoToLocal(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  if (isNaN(d.getTime())) return "";
  const pad = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

const THEME_OPTIONS = [
  { v: "info", label: "Info", bar: "bg-blue-600" },
  { v: "promo", label: "Promo", bar: "bg-slate-900" },
  { v: "warning", label: "Peringatan", bar: "bg-red-600" },
];

const IMG_HINT = "Disarankan: 800 × 600 px (rasio 4:3) · format JPG/PNG/WebP · maks 2 MB";

function getImageDims(file) {
  return new Promise((resolve) => {
    const url = URL.createObjectURL(file);
    const img = new Image();
    img.onload = () => { URL.revokeObjectURL(url); resolve({ w: img.naturalWidth, h: img.naturalHeight }); };
    img.onerror = () => { URL.revokeObjectURL(url); resolve(null); };
    img.src = url;
  });
}

export default function AdminSettings() {
  const navigate = useNavigate();
  const { isAdmin } = useAuth();
  const [form, setForm] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (isAdmin === false) {
      navigate("/dashboard", { replace: true });
      return;
    }
    (async () => {
      try {
        const { data } = await api.get("/admin/settings");
        setForm(data);
      } catch {
        toast.error("Gagal memuat pengaturan");
      } finally {
        setLoading(false);
      }
      loadCats();
      loadManualOrders();
    })();
  }, [isAdmin, navigate]);

  const set = (k, v) => setForm((f) => ({ ...f, [k]: v }));
  const setNum = (k, v) => setForm((f) => ({ ...f, [k]: Math.max(0, Math.round(Number(v) || 0)) }));

  // ---- Work categories management ----
  const [cats, setCats] = useState([]);
  const [catBusy, setCatBusy] = useState(null);
  const [newCat, setNewCat] = useState({ name: "", imageUrl: null });
  const newFileRef = useRef(null);
  const rowFileRefs = useRef({});

  const loadCats = async () => {
    try {
      const { data } = await api.get("/work-categories");
      setCats(data);
    } catch { toast.error("Gagal memuat kategori"); }
  };

  const uploadImage = async (file) => {
    const fd = new FormData();
    fd.append("file", file);
    const { data } = await api.post("/upload", fd);
    return data.path;
  };

  const handleImagePick = async (file, onDone, busyKey) => {
    if (!file) return;
    if (!file.type.startsWith("image/")) { toast.error("File harus berupa gambar (JPG/PNG/WebP)"); return; }
    if (file.size > 2 * 1024 * 1024) { toast.error("Ukuran gambar maksimal 2 MB"); return; }
    setCatBusy(busyKey);
    try {
      const dims = await getImageDims(file);
      if (dims && (dims.w < 800 || dims.h < 600)) {
        toast.info(`Resolusi ${dims.w}×${dims.h} px lebih kecil dari saran (800×600 px). Gambar tetap diunggah.`);
      }
      const path = await uploadImage(file);
      onDone(path);
      toast.success("Gambar terunggah");
    } catch {
      toast.error("Gagal mengunggah gambar");
    } finally {
      setCatBusy(null);
    }
  };

  const saveCat = async (c) => {
    if (!c.name?.trim()) { toast.error("Nama kategori wajib diisi"); return; }
    setCatBusy(c.id);
    try {
      await api.put(`/admin/work-categories/${c.id}`, { name: c.name.trim(), imageUrl: c.imageUrl || null });
      toast.success("Kategori disimpan");
      loadCats();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Gagal menyimpan kategori");
    } finally { setCatBusy(null); }
  };

  const delCat = async (c) => {
    setCatBusy(c.id);
    try {
      await api.delete(`/admin/work-categories/${c.id}`);
      toast.success(`Kategori "${c.name}" dihapus`);
      loadCats();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Gagal menghapus kategori");
    } finally { setCatBusy(null); }
  };

  const addCat = async () => {
    if (!newCat.name.trim()) { toast.error("Nama kategori wajib diisi"); return; }
    setCatBusy("new");
    try {
      await api.post("/admin/work-categories", { name: newCat.name.trim(), imageUrl: newCat.imageUrl || null });
      toast.success("Kategori ditambahkan");
      setNewCat({ name: "", imageUrl: null });
      loadCats();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Gagal menambah kategori");
    } finally { setCatBusy(null); }
  };

  const save = async () => {
    setSaving(true);
    try {
      const { data } = await api.put("/admin/settings", form);
      setForm(data);
      toast.success("Pengaturan tersimpan");
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Gagal menyimpan");
    } finally {
      setSaving(false);
    }
  };

  // ---- Pembayaran manual (QRIS pribadi) ----
  const [manualOrders, setManualOrders] = useState([]);
  const [orderBusy, setOrderBusy] = useState(null);
  const qrisFileRef = useRef(null);

  const loadManualOrders = async () => {
    try {
      const { data } = await api.get("/admin/manual-orders?status=pending_review");
      setManualOrders(data);
    } catch { /* abaikan */ }
  };

  const reviewOrder = async (orderId, action) => {
    setOrderBusy(orderId + action);
    try {
      await api.post(`/admin/orders/${orderId}/${action}`);
      toast.success(action === "approve" ? "Pembayaran disetujui — Premium pengguna aktif" : "Pembayaran ditolak");
      loadManualOrders();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Gagal memproses order");
    } finally {
      setOrderBusy(null);
    }
  };

  const planLabel = (p) => (p === "yearly" ? "Premium Tahunan" : "Premium Bulanan");
  const fmtDate = (iso) => {
    try { return new Date(iso).toLocaleString("id-ID", { day: "2-digit", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" }); }
    catch { return "-"; }
  };

  return (
    <div className="min-h-screen bg-slate-50 pf-grain">
      <Header />
      <main className="max-w-2xl mx-auto px-4 sm:px-6 py-8" data-testid="admin-settings-page">
        <button onClick={() => navigate("/dashboard")} className="flex items-center gap-1.5 text-sm text-slate-500 hover:text-slate-900 mb-6">
          <ArrowLeft className="w-4 h-4" /> Kembali ke Dashboard
        </button>

        <div className="flex items-center gap-2.5 mb-1">
          <div className="w-9 h-9 rounded-lg bg-slate-900 flex items-center justify-center"><Settings className="w-5 h-5 text-amber-400" /></div>
          <h1 className="font-display text-2xl sm:text-3xl font-extrabold text-slate-900 tracking-tight">Pengaturan Admin</h1>
        </div>
        <p className="text-sm text-slate-500 mb-6 flex items-center gap-1.5"><ShieldCheck className="w-4 h-4 text-green-600" /> Halaman khusus admin untuk konfigurasi web.</p>

        {loading || !form ? (
          <div className="py-16 flex justify-center"><Loader2 className="w-6 h-6 animate-spin text-amber-500" /></div>
        ) : (
          <div className="space-y-5">
            <Card className="p-6 border-slate-200 bg-white space-y-4">
              <h3 className="font-display font-bold text-slate-900">Identitas & Kontak</h3>
              <div>
                <Label className="text-slate-700">Nama Aplikasi</Label>
                <Input data-testid="setting-appname" value={form.appName || ""} onChange={(e) => set("appName", e.target.value)} className="mt-1 h-11 bg-white" placeholder="ProFinance Interior" />
              </div>
              <div className="grid sm:grid-cols-2 gap-4">
                <div>
                  <Label className="text-slate-700">Email Dukungan</Label>
                  <Input data-testid="setting-email" type="email" value={form.supportEmail || ""} onChange={(e) => set("supportEmail", e.target.value)} className="mt-1 h-11 bg-white" placeholder="support@email.com" />
                </div>
                <div>
                  <Label className="text-slate-700">WhatsApp Dukungan</Label>
                  <Input data-testid="setting-whatsapp" inputMode="tel" value={form.supportWhatsapp || ""} onChange={(e) => set("supportWhatsapp", e.target.value)} className="mt-1 h-11 bg-white" placeholder="08xxxxxxxxxx" />
                </div>
              </div>
            </Card>

            <Card className="p-6 border-slate-200 bg-white space-y-4">
              <h3 className="font-display font-bold text-slate-900">Pengumuman & Mode</h3>
              <div>
                <Label className="text-slate-700">Banner Pengumuman</Label>
                <Textarea data-testid="setting-announcement" value={form.announcement || ""} onChange={(e) => set("announcement", e.target.value)} className="mt-1 bg-white" rows={2} placeholder="Contoh: Promo tahunan diskon 28% hingga akhir bulan!" />
                <p className="text-[11px] text-slate-400 mt-1">Tampil sebagai banner pengumuman di bagian atas semua halaman pengguna (Dashboard, Akun, Harga, dll). Kosongkan untuk menyembunyikan.</p>
              </div>
              <div>
                <Label className="text-slate-700">Warna Banner</Label>
                <div className="flex gap-2 mt-1.5">
                  {THEME_OPTIONS.map((t) => (
                    <button
                      key={t.v}
                      type="button"
                      data-testid={`theme-${t.v}`}
                      onClick={() => set("announcementTheme", t.v)}
                      className={`flex-1 rounded-lg border-2 px-3 py-2.5 text-xs font-semibold transition-all text-left ${
                        (form.announcementTheme || "info") === t.v
                          ? "border-slate-900 bg-slate-50 text-slate-900"
                          : "border-slate-200 bg-white text-slate-500 hover:border-slate-300"
                      }`}
                    >
                      <span className={`block h-1.5 w-9 rounded-full mb-1.5 ${t.bar}`} />
                      {t.label}
                    </button>
                  ))}
                </div>
                <p className="text-[11px] text-slate-400 mt-1">Info (biru) untuk kabar umum, Promo (gelap) untuk penawaran, Peringatan (merah) untuk hal penting.</p>
              </div>
              <div className="flex items-center justify-between rounded-lg border border-slate-200 px-4 py-3">
                <div>
                  <div className="text-sm font-medium text-slate-800">Mode Pemeliharaan</div>
                  <div className="text-[11px] text-slate-400">Nonaktifkan sementara untuk perawatan.</div>
                </div>
                <Switch data-testid="setting-maintenance" checked={!!form.maintenanceMode} onCheckedChange={(v) => set("maintenanceMode", v)} />
              </div>
            </Card>

            <Card className="p-6 border-slate-200 bg-white space-y-4">
              <div className="flex items-center gap-2">
                <Tag className="w-4 h-4 text-amber-600" />
                <h3 className="font-display font-bold text-slate-900">Harga & Promo</h3>
              </div>
              <div className="flex items-center justify-between rounded-lg border border-amber-200 bg-amber-50/60 px-4 py-3">
                <div>
                  <div className="text-sm font-medium text-slate-800">Aktifkan Harga Promo</div>
                  <div className="text-[11px] text-slate-500">Bila aktif, harga promo (jika lebih rendah) dipakai di halaman Harga & pembayaran.</div>
                </div>
                <Switch data-testid="setting-promo-active" checked={!!form.promoActive} onCheckedChange={(v) => set("promoActive", v)} />
              </div>

              <div>
                <Label className="text-slate-700">Promo Berakhir Pada (opsional)</Label>
                <Input
                  data-testid="setting-promo-ends"
                  type="datetime-local"
                  value={isoToLocal(form.promoEndsAt)}
                  onChange={(e) => set("promoEndsAt", e.target.value ? new Date(e.target.value).toISOString() : "")}
                  className="mt-1 h-11 bg-white"
                />
                <p className="text-[11px] text-slate-400 mt-1">
                  Kosongkan untuk promo tanpa batas waktu. Setelah tanggal ini promo otomatis nonaktif (harga kembali normal) dan hitung mundur tampil di halaman Harga.
                </p>
              </div>

              <div className="rounded-lg border border-slate-200 p-4 space-y-3">
                <div className="text-sm font-semibold text-slate-800">Paket Bulanan (30 hari)</div>
                <div className="grid sm:grid-cols-2 gap-4">
                  <div>
                    <Label className="text-slate-700">Harga Normal (Rp)</Label>
                    <Input data-testid="setting-monthly-price" type="number" min="0" value={form.monthlyPrice ?? 0} onChange={(e) => setNum("monthlyPrice", e.target.value)} className="mt-1 h-11 bg-white font-mono" />
                  </div>
                  <div>
                    <Label className="text-slate-700">Harga Promo (Rp)</Label>
                    <Input data-testid="setting-monthly-promo" type="number" min="0" value={form.monthlyPromo ?? 0} onChange={(e) => setNum("monthlyPromo", e.target.value)} className="mt-1 h-11 bg-white font-mono" />
                  </div>
                </div>
                <p className="text-[11px] text-slate-400">{priceHint(form.monthlyPrice, form.monthlyPromo, form.promoActive)}</p>
              </div>

              <div className="rounded-lg border border-slate-200 p-4 space-y-3">
                <div className="text-sm font-semibold text-slate-800">Paket Tahunan (365 hari)</div>
                <div className="grid sm:grid-cols-2 gap-4">
                  <div>
                    <Label className="text-slate-700">Harga Normal (Rp)</Label>
                    <Input data-testid="setting-yearly-price" type="number" min="0" value={form.yearlyPrice ?? 0} onChange={(e) => setNum("yearlyPrice", e.target.value)} className="mt-1 h-11 bg-white font-mono" />
                  </div>
                  <div>
                    <Label className="text-slate-700">Harga Promo (Rp)</Label>
                    <Input data-testid="setting-yearly-promo" type="number" min="0" value={form.yearlyPromo ?? 0} onChange={(e) => setNum("yearlyPromo", e.target.value)} className="mt-1 h-11 bg-white font-mono" />
                  </div>
                </div>
                <p className="text-[11px] text-slate-400">{priceHint(form.yearlyPrice, form.yearlyPromo, form.promoActive)}</p>
              </div>
            </Card>

            <Card className="p-6 border-slate-200 bg-white space-y-4" data-testid="payment-method-card">
              <div className="flex items-center gap-2">
                <CreditCard className="w-4 h-4 text-amber-600" />
                <h3 className="font-display font-bold text-slate-900">Metode Pembayaran</h3>
              </div>
              <div className="grid sm:grid-cols-2 gap-2">
                <button
                  type="button"
                  data-testid="paymethod-midtrans"
                  onClick={() => set("paymentMethod", "midtrans")}
                  className={`rounded-lg border-2 px-3.5 py-3 text-left transition-all ${
                    (form.paymentMethod || "midtrans") === "midtrans"
                      ? "border-slate-900 bg-slate-50"
                      : "border-slate-200 bg-white hover:border-slate-300"
                  }`}
                >
                  <div className="flex items-center gap-1.5 text-sm font-semibold text-slate-800"><CreditCard className="w-4 h-4 text-slate-500" /> Midtrans (Otomatis)</div>
                  <div className="text-[11px] text-slate-400 mt-1">QRIS/GoPay/VA via Midtrans. Premium aktif otomatis setelah lunas.</div>
                </button>
                <button
                  type="button"
                  data-testid="paymethod-manual"
                  onClick={() => set("paymentMethod", "manual")}
                  className={`rounded-lg border-2 px-3.5 py-3 text-left transition-all ${
                    form.paymentMethod === "manual"
                      ? "border-amber-500 bg-amber-50/70"
                      : "border-slate-200 bg-white hover:border-slate-300"
                  }`}
                >
                  <div className="flex items-center gap-1.5 text-sm font-semibold text-slate-800"><QrCode className="w-4 h-4 text-amber-600" /> Manual (QRIS Pribadi)</div>
                  <div className="text-[11px] text-slate-400 mt-1">Pelanggan scan QRIS Anda & unggah bukti. Anda verifikasi manual.</div>
                </button>
              </div>

              {form.paymentMethod === "manual" && (
                <div className="rounded-lg border border-amber-200 bg-amber-50/50 p-4 space-y-3" data-testid="qris-config">
                  <div>
                    <Label className="text-slate-700">Gambar QRIS Pribadi Anda</Label>
                    <div className="mt-1.5 flex items-center gap-3">
                      {form.qrisImage ? (
                        <img src={fileUrl(form.qrisImage)} alt="QRIS" data-testid="qris-preview" className="w-24 h-24 rounded-lg border border-slate-200 object-contain bg-white" />
                      ) : (
                        <div className="w-24 h-24 rounded-lg border-2 border-dashed border-slate-300 flex items-center justify-center bg-white">
                          <QrCode className="w-7 h-7 text-slate-300" />
                        </div>
                      )}
                      <div className="space-x-2">
                        <input
                          ref={qrisFileRef}
                          type="file"
                          accept="image/*"
                          className="hidden"
                          data-testid="qris-file-input"
                          onChange={(e) => { const f = e.target.files?.[0]; if (f) handleImagePick(f, (p) => set("qrisImage", p), "qris"); e.target.value = ""; }}
                        />
                        <Button type="button" size="sm" variant="outline" data-testid="qris-upload-btn" disabled={catBusy === "qris"} onClick={() => qrisFileRef.current?.click()} className="gap-1.5 border-slate-300">
                          {catBusy === "qris" ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <ImageIcon className="w-3.5 h-3.5" />}
                          {form.qrisImage ? "Ganti QRIS" : "Unggah QRIS"}
                        </Button>
                        {form.qrisImage && (
                          <Button type="button" size="sm" variant="ghost" data-testid="qris-remove-btn" onClick={() => set("qrisImage", "")} className="text-red-500 hover:text-red-600">Hapus</Button>
                        )}
                      </div>
                    </div>
                    <p className="text-[11px] text-slate-400 mt-1.5">Gambar ini ditampilkan ke pelanggan saat checkout. Format JPG/PNG, maks 2 MB.</p>
                  </div>
                  <div>
                    <Label className="text-slate-700">Catatan Instruksi (opsional)</Label>
                    <Textarea
                      data-testid="setting-payment-note"
                      value={form.paymentNote || ""}
                      onChange={(e) => set("paymentNote", e.target.value)}
                      className="mt-1 bg-white"
                      rows={2}
                      placeholder="Contoh: Scan QRIS di atas, bayar sesuai nominal, lalu unggah bukti pembayaran. Premium aktif setelah admin verifikasi (maks 1x24 jam)."
                    />
                  </div>
                  <p className="text-[11px] text-amber-700 flex items-center gap-1"><ShieldCheck className="w-3.5 h-3.5" /> Jangan lupa klik &ldquo;Simpan Pengaturan&rdquo; di bawah setelah mengubah metode/QRIS.</p>
                </div>
              )}
            </Card>

            {(form.paymentMethod === "manual" || manualOrders.length > 0) && (
              <Card className="p-6 border-slate-200 bg-white space-y-3" data-testid="manual-orders-card">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Banknote className="w-4 h-4 text-amber-600" />
                    <h3 className="font-display font-bold text-slate-900">Verifikasi Pembayaran Manual</h3>
                  </div>
                  <button onClick={loadManualOrders} className="text-slate-400 hover:text-amber-600" title="Muat ulang"><RefreshCw className="w-4 h-4" /></button>
                </div>
                {manualOrders.length === 0 ? (
                  <p className="text-sm text-slate-400" data-testid="manual-orders-empty">Tidak ada pembayaran yang menunggu verifikasi.</p>
                ) : (
                  <div className="space-y-2.5">
                    {manualOrders.map((o) => (
                      <div key={o.order_id} className="rounded-lg border border-slate-200 p-3.5" data-testid={`manual-order-${o.order_id}`}>
                        <div className="flex items-start justify-between gap-2">
                          <div className="min-w-0">
                            <div className="text-sm font-semibold text-slate-900 truncate">{o.userName || o.userEmail} <span className="font-normal text-slate-400">· {planLabel(o.plan)}</span></div>
                            <div className="text-xs text-slate-500 mt-0.5">{o.userEmail} · {fmtDate(o.created_at)}</div>
                            <div className="font-mono font-bold text-amber-700 mt-1">{rupiah(o.gross_amount)}</div>
                          </div>
                          {o.proofUrl ? (
                            <a href={fileUrl(o.proofUrl)} target="_blank" rel="noreferrer" data-testid={`proof-link-${o.order_id}`} className="inline-flex items-center gap-1 text-xs text-blue-600 hover:underline shrink-0">
                              <Eye className="w-3.5 h-3.5" /> Lihat Bukti
                            </a>
                          ) : (
                            <span className="text-[11px] text-slate-400 shrink-0">Belum ada bukti</span>
                          )}
                        </div>
                        <div className="flex gap-2 mt-2.5">
                          <Button size="sm" data-testid={`approve-order-${o.order_id}`} disabled={orderBusy === o.order_id + "approve"} onClick={() => reviewOrder(o.order_id, "approve")} className="flex-1 h-8 text-xs bg-green-600 hover:bg-green-700 text-white gap-1">
                            {orderBusy === o.order_id + "approve" ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <CheckCircle2 className="w-3.5 h-3.5" />} Setujui & Aktifkan
                          </Button>
                          <Button size="sm" variant="outline" data-testid={`reject-order-${o.order_id}`} disabled={orderBusy === o.order_id + "reject"} onClick={() => reviewOrder(o.order_id, "reject")} className="h-8 text-xs border-red-200 text-red-600 hover:bg-red-50 gap-1">
                            {orderBusy === o.order_id + "reject" ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <XCircle className="w-3.5 h-3.5" />} Tolak
                          </Button>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </Card>
            )}

            <Card className="p-6 border-slate-200 bg-white space-y-4" data-testid="work-categories-card">
              <div className="flex items-center gap-2">
                <ImageIcon className="w-4 h-4 text-amber-600" />
                <h3 className="font-display font-bold text-slate-900">Kategori Pekerjaan</h3>
              </div>
              <p className="text-[11px] text-slate-400 -mt-2">
                Kategori ini tampil di pilihan Kategori saat membuat/mengedit proyek. Setiap kategori bisa punya gambar.
              </p>

              <div className="space-y-2.5">
                {cats.map((c) => (
                  <div key={c.id} className="flex items-center gap-3 rounded-lg border border-slate-200 p-3" data-testid={`cat-row-${c.id}`}>
                    <div className="w-16 h-12 rounded-md bg-slate-100 border border-slate-200 overflow-hidden shrink-0 flex items-center justify-center">
                      {c.imageUrl ? (
                        <img src={fileUrl(c.imageUrl)} alt={c.name} className="w-full h-full object-cover" />
                      ) : (
                        <ImageIcon className="w-5 h-5 text-slate-300" />
                      )}
                    </div>
                    <Input
                      value={c.name}
                      onChange={(e) => setCats((arr) => arr.map((x) => (x.id === c.id ? { ...x, name: e.target.value } : x)))}
                      className="h-10 bg-white"
                      data-testid={`cat-name-${c.id}`}
                    />
                    <input
                      type="file" accept="image/*" className="hidden"
                      ref={(el) => { rowFileRefs.current[c.id] = el; }}
                      onChange={(e) => {
                        const f = e.target.files?.[0];
                        e.target.value = "";
                        handleImagePick(f, (path) => setCats((arr) => arr.map((x) => (x.id === c.id ? { ...x, imageUrl: path } : x))), c.id);
                      }}
                    />
                    <Button
                      size="sm" variant="outline"
                      onClick={() => rowFileRefs.current[c.id]?.click()}
                      disabled={catBusy === c.id}
                      className="shrink-0 gap-1.5 border-slate-300"
                      data-testid={`cat-image-${c.id}`}
                    >
                      {catBusy === c.id ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <RefreshCw className="w-3.5 h-3.5" />}
                      Gambar
                    </Button>
                    <Button size="sm" onClick={() => saveCat(c)} disabled={catBusy === c.id} className="shrink-0 bg-slate-900 hover:bg-slate-800 text-white" data-testid={`cat-save-${c.id}`}>
                      Simpan
                    </Button>
                    <Button size="sm" variant="outline" onClick={() => delCat(c)} disabled={catBusy === c.id} className="shrink-0 border-red-200 text-red-600 hover:bg-red-50" data-testid={`cat-delete-${c.id}`}>
                      <Trash2 className="w-3.5 h-3.5" />
                    </Button>
                  </div>
                ))}
              </div>

              <div className="rounded-lg border border-dashed border-slate-300 p-4 space-y-3 bg-slate-50/60">
                <div className="text-sm font-semibold text-slate-800">Tambah Kategori Baru</div>
                <div className="flex items-center gap-3 flex-wrap">
                  <div className="w-16 h-12 rounded-md bg-white border border-slate-200 overflow-hidden shrink-0 flex items-center justify-center">
                    {newCat.imageUrl ? (
                      <img src={fileUrl(newCat.imageUrl)} alt="baru" className="w-full h-full object-cover" />
                    ) : (
                      <ImageIcon className="w-5 h-5 text-slate-300" />
                    )}
                  </div>
                  <Input
                    value={newCat.name}
                    onChange={(e) => setNewCat((n) => ({ ...n, name: e.target.value }))}
                    placeholder="mis. Kitchen Set, Kamar Mandi"
                    className="h-10 bg-white flex-1 min-w-[180px]"
                    data-testid="new-cat-name"
                  />
                  <input
                    type="file" accept="image/*" className="hidden" ref={newFileRef}
                    onChange={(e) => {
                      const f = e.target.files?.[0];
                      e.target.value = "";
                      handleImagePick(f, (path) => setNewCat((n) => ({ ...n, imageUrl: path })), "new");
                    }}
                  />
                  <Button size="sm" variant="outline" onClick={() => newFileRef.current?.click()} disabled={catBusy === "new"} className="gap-1.5 border-slate-300" data-testid="new-cat-image">
                    {catBusy === "new" ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <ImageIcon className="w-3.5 h-3.5" />}
                    Pilih Gambar
                  </Button>
                  <Button size="sm" onClick={addCat} disabled={catBusy === "new"} className="gap-1.5 bg-amber-600 hover:bg-amber-700 text-white" data-testid="new-cat-add">
                    <Plus className="w-3.5 h-3.5" /> Tambah
                  </Button>
                </div>
                <p className="text-[11px] text-slate-400 flex items-center gap-1.5">
                  <ImageIcon className="w-3 h-3" /> {IMG_HINT}
                </p>
              </div>
            </Card>

            <Button data-testid="setting-save-btn" onClick={save} disabled={saving} className="w-full h-11 bg-slate-900 hover:bg-slate-800 text-white gap-2">
              {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />} Simpan Pengaturan
            </Button>
          </div>
        )}
      </main>
    </div>
  );
}
