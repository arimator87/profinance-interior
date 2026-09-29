import { useEffect, useState, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { Header } from "@/components/Header";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { rupiah, fmtDate } from "@/lib/format";
import { API } from "@/lib/api";
import { toast } from "sonner";
import {
  ArrowLeft, Crown, Sparkles, Receipt, Loader2, BellRing, Clock, CheckCircle2, XCircle,
  DatabaseBackup, Download, Image as ImageIcon, FolderArchive, RotateCcw, UploadCloud,
  History, Zap,
} from "lucide-react";

const STATUS = {
  paid: { label: "Lunas", cls: "bg-green-100 text-green-700", icon: CheckCircle2 },
  pending: { label: "Menunggu", cls: "bg-amber-100 text-amber-700", icon: Clock },
  pending_review: { label: "Menunggu Verifikasi", cls: "bg-blue-100 text-blue-700", icon: Clock },
  rejected: { label: "Ditolak", cls: "bg-red-100 text-red-600", icon: XCircle },
  expire: { label: "Kedaluwarsa", cls: "bg-slate-100 text-slate-500", icon: XCircle },
  cancel: { label: "Dibatalkan", cls: "bg-slate-100 text-slate-500", icon: XCircle },
  deny: { label: "Ditolak", cls: "bg-red-100 text-red-600", icon: XCircle },
  create_failed: { label: "Gagal", cls: "bg-red-100 text-red-600", icon: XCircle },
};

const PLAN_LABEL = { monthly: "Premium Bulanan", yearly: "Premium Tahunan" };

export default function Account() {
  const navigate = useNavigate();
  const { user, isPremium } = useAuth();
  const isDemo = user?.isDemo;
  const fileRef = useRef(null);
  const [orders, setOrders] = useState([]);
  const [notifs, setNotifs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [summary, setSummary] = useState(null);
  const [backing, setBacking] = useState(false);
  const [backups, setBackups] = useState([]);
  const [running, setRunning] = useState(false);
  const [restoring, setRestoring] = useState(false);

  const loadBackups = async () => {
    try {
      const b = await api.get("/backups");
      setBackups(b.data);
    } catch { /* ignore */ }
  };

  useEffect(() => {
    (async () => {
      try {
        const [o, n, s] = await Promise.all([
          api.get("/subscription/orders"),
          api.get("/notifications"),
          api.get("/backup/summary"),
        ]);
        setOrders(o.data);
        setNotifs(n.data);
        setSummary(s.data);
      } catch { /* ignore */ } finally { setLoading(false); }
      loadBackups();
    })();
  }, []);

  const downloadBackup = async () => {
    setBacking(true);
    const tid = toast.loading("Menyiapkan backup (termasuk foto)...");
    try {
      const res = await api.get("/backup/export", { responseType: "blob" });
      const url = window.URL.createObjectURL(new Blob([res.data], { type: "application/zip" }));
      const a = document.createElement("a");
      a.href = url;
      const stamp = new Date().toISOString().slice(0, 19).replace(/[:T]/g, "-");
      a.download = `profinance-backup-${stamp}.zip`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
      toast.success("Backup berhasil diunduh ke perangkat", { id: tid });
    } catch {
      toast.error("Gagal membuat backup. Coba lagi.", { id: tid });
    } finally {
      setBacking(false);
    }
  };

  const runBackupNow = async () => {
    setRunning(true);
    const tid = toast.loading("Membuat backup tersimpan...");
    try {
      await api.post("/backup/run");
      toast.success("Backup tersimpan berhasil dibuat", { id: tid });
      loadBackups();
    } catch (e) {
      const msg = e?.response?.data?.detail || "Gagal membuat backup";
      toast.error(msg, { id: tid });
    } finally {
      setRunning(false);
    }
  };

  const downloadStored = (b) => {
    const token = localStorage.getItem("pf_token");
    const url = `${API}/backups/${b.id}/download?auth=${encodeURIComponent(token || "")}`;
    window.open(url, "_blank");
  };

  const onRestoreFile = async (e) => {
    const f = e.target.files?.[0];
    if (fileRef.current) fileRef.current.value = "";
    if (!f) return;
    if (!f.name.toLowerCase().endsWith(".zip")) {
      toast.error("Pilih file backup .zip");
      return;
    }
    setRestoring(true);
    const tid = toast.loading("Memulihkan data dari backup...");
    try {
      const fd = new FormData();
      fd.append("file", f);
      const res = await api.post("/backup/restore", fd, { headers: { "Content-Type": "multipart/form-data" } });
      const d = res.data;
      if (d.restored_projects > 0) {
        toast.success(`${d.restored_projects} proyek dipulihkan (${d.restored_transactions} transaksi, ${d.photos_restored} foto)`, { id: tid });
      } else {
        toast.success(`Tidak ada proyek baru dipulihkan (${d.skipped_projects} sudah ada)`, { id: tid });
      }
      const s = await api.get("/backup/summary");
      setSummary(s.data);
    } catch (e2) {
      const msg = e2?.response?.data?.detail || "Gagal memulihkan data";
      toast.error(msg, { id: tid });
    } finally {
      setRestoring(false);
    }
  };

  const expiry = user?.subscriptionExpiry ? new Date(user.subscriptionExpiry) : null;
  const daysLeft = expiry ? Math.ceil((expiry - new Date()) / 86400000) : null;
  const pendingManual = orders.find((o) => o.payment_method === "manual" && o.status === "pending_review");
  const rejectedManual = orders.find((o) => o.payment_method === "manual" && o.status === "rejected");

  return (
    <div className="min-h-screen bg-slate-50 pf-grain">
      <Header />
      <main className="max-w-4xl mx-auto px-4 sm:px-6 py-8" data-testid="account-page">
        <button onClick={() => navigate("/dashboard")} className="flex items-center gap-1.5 text-sm text-slate-500 hover:text-slate-900 mb-6">
          <ArrowLeft className="w-4 h-4" /> Kembali ke Dashboard
        </button>

        <h1 className="font-display text-2xl sm:text-3xl font-extrabold text-slate-900 tracking-tight mb-6">Akun & Transaksi</h1>

        {/* Subscription status */}
        <Card className={`p-6 mb-6 border ${isPremium ? "border-amber-300 bg-gradient-to-br from-amber-50 to-white" : "border-slate-200 bg-white"}`} data-testid="subscription-card">
          <div className="flex items-start justify-between gap-4 flex-wrap">
            <div>
              <div className="flex items-center gap-2 mb-1">
                {isPremium ? <Crown className="w-5 h-5 text-amber-600" /> : <Sparkles className="w-5 h-5 text-slate-400" />}
                <h2 className="font-display font-bold text-lg">{isPremium ? "Premium Pro" : "Paket Free"}</h2>
              </div>
              <p className="text-sm text-slate-500">{user?.name} · {user?.email}</p>
              {isPremium && expiry && (
                <p className="text-sm mt-2" data-testid="subscription-expiry">
                  Masa aktif s/d <b className="text-slate-900">{fmtDate(user.subscriptionExpiry)}</b>
                  {daysLeft != null && (
                    <span className={`ml-2 font-mono text-xs px-2 py-0.5 rounded-full ${daysLeft <= 7 ? "bg-red-100 text-red-600" : "bg-green-100 text-green-700"}`}>
                      {daysLeft < 0 ? "berakhir" : `${daysLeft} hari lagi`}
                    </span>
                  )}
                </p>
              )}
            </div>
            {(!isPremium || (daysLeft != null && daysLeft <= 14)) && (
              <Button data-testid="account-renew-btn" onClick={() => navigate("/pricing")} className="bg-amber-600 hover:bg-amber-700 text-white gap-1.5">
                <Crown className="w-4 h-4" /> {isPremium ? "Perpanjang" : "Upgrade Premium"}
              </Button>
            )}
          </div>
        </Card>

        {/* Status pembayaran manual (QRIS) */}
        {pendingManual && (
          <Card className="p-4 mb-6 border-blue-200 bg-blue-50/70" data-testid="manual-pending-banner">
            <div className="flex items-start gap-3">
              <div className="w-9 h-9 rounded-lg bg-blue-100 flex items-center justify-center shrink-0">
                <Clock className="w-5 h-5 text-blue-600" />
              </div>
              <div className="min-w-0">
                <h3 className="font-semibold text-blue-900 text-sm">Pembayaran sedang diverifikasi</h3>
                <p className="text-xs text-blue-700 mt-0.5">
                  Bukti pembayaran Anda untuk <b>{PLAN_LABEL[pendingManual.plan] || pendingManual.plan}</b> ({rupiah(pendingManual.gross_amount)}) telah kami terima.
                  Admin akan memverifikasi maksimal 1×24 jam. Premium otomatis aktif setelah disetujui — Anda tidak perlu membayar lagi.
                </p>
              </div>
            </div>
          </Card>
        )}
        {!pendingManual && rejectedManual && !isPremium && (
          <Card className="p-4 mb-6 border-red-200 bg-red-50/70" data-testid="manual-rejected-banner">
            <div className="flex items-start gap-3">
              <div className="w-9 h-9 rounded-lg bg-red-100 flex items-center justify-center shrink-0">
                <XCircle className="w-5 h-5 text-red-600" />
              </div>
              <div className="min-w-0 flex-1">
                <h3 className="font-semibold text-red-900 text-sm">Bukti pembayaran ditolak</h3>
                <p className="text-xs text-red-700 mt-0.5">
                  Bukti pembayaran Anda untuk <b>{PLAN_LABEL[rejectedManual.plan] || rejectedManual.plan}</b> belum dapat diverifikasi.
                  Silakan periksa kembali nominal & bukti transfer, lalu unggah ulang.
                </p>
                <Button size="sm" data-testid="manual-retry-btn" onClick={() => navigate("/pricing")} className="mt-2 h-8 text-xs bg-red-600 hover:bg-red-700 text-white gap-1">
                  <Crown className="w-3.5 h-3.5" /> Unggah Ulang Bukti
                </Button>
              </div>
            </div>
          </Card>
        )}

        <Card className="p-6 mb-6 border-slate-200 bg-white" data-testid="backup-card">
          <div className="flex items-start gap-3 mb-4">
            <div className="w-10 h-10 rounded-xl bg-amber-100 flex items-center justify-center shrink-0">
              <DatabaseBackup className="w-5 h-5 text-amber-600" />
            </div>
            <div>
              <h3 className="font-display font-bold text-lg text-slate-900">Backup Data</h3>
              <p className="text-sm text-slate-500">
                Unduh cadangan lengkap semua proyek, transaksi, tukang, progress, dan seluruh foto
                dalam satu file ZIP. Simpan di perangkat Anda, atau biarkan backup otomatis mingguan mengamankannya di cloud.
              </p>
            </div>
          </div>

          {summary && (
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 mb-5">
              {[
                { label: "Proyek", value: summary.projects },
                { label: "Transaksi", value: summary.transactions },
                { label: "Tukang", value: summary.workers },
                { label: "Item RAB", value: summary.work_items },
                { label: "Log Progress", value: summary.progress_entries },
                { label: "Foto", value: summary.photos, icon: ImageIcon },
              ].map((s) => (
                <div key={s.label} className="rounded-lg border border-slate-100 bg-slate-50 px-3 py-2">
                  <div className="flex items-center gap-1.5 text-[11px] text-slate-400 uppercase tracking-wide">
                    {s.icon && <s.icon className="w-3 h-3" />} {s.label}
                  </div>
                  <div className="font-display font-bold text-slate-900 text-lg">{s.value}</div>
                </div>
              ))}
            </div>
          )}

          <div className="flex flex-wrap items-center gap-3">
            <Button
              data-testid="backup-download-btn"
              onClick={downloadBackup}
              disabled={backing}
              className="bg-slate-900 hover:bg-slate-800 text-white gap-2"
            >
              {backing ? <Loader2 className="w-4 h-4 animate-spin" /> : <Download className="w-4 h-4" />}
              {backing ? "Menyiapkan..." : "Unduh Backup (.zip)"}
            </Button>
            {!isDemo && (
              <Button
                data-testid="backup-run-btn"
                onClick={runBackupNow}
                disabled={running}
                variant="outline"
                className="gap-2 border-slate-300"
              >
                {running ? <Loader2 className="w-4 h-4 animate-spin" /> : <Zap className="w-4 h-4 text-amber-600" />}
                Simpan Backup di Cloud
              </Button>
            )}
            <span className="inline-flex items-center gap-1.5 text-xs text-slate-400">
              <FolderArchive className="w-3.5 h-3.5" />
              Berisi data.json, data.xlsx & folder foto
            </span>
          </div>
          <p className="text-xs text-slate-400 mt-3 flex items-center gap-1.5">
            <History className="w-3.5 h-3.5" />
            Backup otomatis dibuat setiap minggu dan tersimpan aman di cloud (tersedia untuk diunduh di bawah).
          </p>
        </Card>

        {/* Stored / scheduled backups */}
        <Card className="p-6 mb-6 border-slate-200 bg-white" data-testid="stored-backups-card">
          <div className="flex items-center gap-2 mb-4">
            <History className="w-4 h-4 text-amber-600" />
            <h3 className="font-display font-bold">Backup Tersimpan (Otomatis Mingguan)</h3>
          </div>
          {backups.length === 0 ? (
            <p className="text-sm text-slate-400 py-4 text-center">
              Belum ada backup tersimpan. Backup otomatis berjalan setiap minggu, atau tekan tombol Simpan Backup di Cloud.
            </p>
          ) : (
            <div className="space-y-2">
              {backups.map((b) => (
                <div key={b.id} className="flex items-center justify-between gap-3 rounded-lg border border-slate-100 bg-slate-50 px-4 py-3" data-testid={`backup-${b.id}`}>
                  <div className="min-w-0">
                    <div className="flex items-center gap-2 text-sm font-semibold text-slate-800">
                      <FolderArchive className="w-4 h-4 text-slate-400 shrink-0" />
                      <span className="truncate">{fmtDate(b.createdAt)}</span>
                      <span className={`text-[10px] px-1.5 py-0.5 rounded-full ${b.kind === "auto" ? "bg-blue-100 text-blue-600" : "bg-amber-100 text-amber-700"}`}>
                        {b.kind === "auto" ? "Otomatis" : "Manual"}
                      </span>
                    </div>
                    <div className="text-[11px] text-slate-400 mt-0.5">
                      {b.counts?.projects || 0} proyek · {b.counts?.photos || 0} foto · {((b.size || 0) / 1024 / 1024).toFixed(2)} MB
                    </div>
                  </div>
                  <Button size="sm" variant="outline" onClick={() => downloadStored(b)} className="gap-1.5 shrink-0 border-slate-300" data-testid={`backup-dl-${b.id}`}>
                    <Download className="w-3.5 h-3.5" /> Unduh
                  </Button>
                </div>
              ))}
            </div>
          )}
        </Card>

        {/* Restore */}
        {!isDemo && (
          <Card className="p-6 mb-6 border-slate-200 bg-white" data-testid="restore-card">
            <div className="flex items-start gap-3 mb-4">
              <div className="w-10 h-10 rounded-xl bg-emerald-100 flex items-center justify-center shrink-0">
                <RotateCcw className="w-5 h-5 text-emerald-600" />
              </div>
              <div>
                <h3 className="font-display font-bold text-lg text-slate-900">Pulihkan Data</h3>
                <p className="text-sm text-slate-500">
                  Unggah file backup (.zip) untuk memulihkan proyek yang terhapus, lengkap dengan transaksi dan foto.
                  Proyek yang sudah ada tidak akan diduplikasi.
                </p>
              </div>
            </div>
            <input ref={fileRef} type="file" accept=".zip" onChange={onRestoreFile} className="hidden" data-testid="restore-input" />
            <Button
              data-testid="restore-btn"
              onClick={() => fileRef.current?.click()}
              disabled={restoring}
              className="bg-emerald-600 hover:bg-emerald-700 text-white gap-2"
            >
              {restoring ? <Loader2 className="w-4 h-4 animate-spin" /> : <UploadCloud className="w-4 h-4" />}
              {restoring ? "Memulihkan..." : "Pilih File Backup (.zip)"}
            </Button>
          </Card>
        )}

        {/* Reminders */}
        {notifs.length > 0 && (
          <Card className="p-5 mb-6 border-slate-200 bg-white" data-testid="reminders-card">
            <div className="flex items-center gap-2 mb-3"><BellRing className="w-4 h-4 text-amber-600" /><h3 className="font-display font-bold">Pengingat</h3></div>
            <div className="space-y-2">
              {notifs.map((n) => (
                <div key={n.id} className="flex items-start gap-3 rounded-lg border border-amber-100 bg-amber-50/60 px-4 py-3" data-testid={`notif-${n.id}`}>
                  <BellRing className="w-4 h-4 text-amber-600 mt-0.5 shrink-0" />
                  <div className="min-w-0">
                    <div className="text-sm font-semibold text-slate-800">{n.title}</div>
                    <div className="text-xs text-slate-500">{n.body}</div>
                    <div className="text-[11px] text-slate-400 mt-0.5">{fmtDate(n.createdAt)}</div>
                  </div>
                </div>
              ))}
            </div>
          </Card>
        )}

        {/* Transaction history */}
        <Card className="p-5 border-slate-200 bg-white" data-testid="transactions-card">
          <div className="flex items-center gap-2 mb-4"><Receipt className="w-4 h-4 text-amber-600" /><h3 className="font-display font-bold">Riwayat Transaksi</h3></div>
          {loading ? (
            <div className="py-10 flex justify-center"><Loader2 className="w-6 h-6 animate-spin text-amber-500" /></div>
          ) : orders.length === 0 ? (
            <p className="text-sm text-slate-400 py-6 text-center">Belum ada transaksi. Upgrade ke Premium untuk mulai.</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="text-slate-400 text-xs border-b border-slate-100">
                  <tr>
                    <th className="text-left font-medium py-2 pr-3">Tanggal</th>
                    <th className="text-left font-medium py-2 pr-3">Paket</th>
                    <th className="text-right font-medium py-2 pr-3">Nominal</th>
                    <th className="text-left font-medium py-2 pr-3">Status</th>
                    <th className="text-left font-medium py-2">Aktif s/d</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {orders.map((o) => {
                    const st = STATUS[o.status] || { label: o.status, cls: "bg-slate-100 text-slate-500", icon: Clock };
                    const Icon = st.icon;
                    return (
                      <tr key={o.order_id} data-testid={`order-${o.order_id}`}>
                        <td className="py-3 pr-3 text-slate-600 whitespace-nowrap">{fmtDate(o.created_at)}</td>
                        <td className="py-3 pr-3 text-slate-800">{PLAN_LABEL[o.plan] || o.plan}</td>
                        <td className="py-3 pr-3 text-right font-mono text-slate-900">{rupiah(o.gross_amount)}</td>
                        <td className="py-3 pr-3">
                          <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-medium ${st.cls}`}>
                            <Icon className="w-3 h-3" /> {st.label}
                          </span>
                        </td>
                        <td className="py-3 text-slate-500 whitespace-nowrap">{o.premium_until ? fmtDate(o.premium_until) : "—"}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </Card>
      </main>
    </div>
  );
}
