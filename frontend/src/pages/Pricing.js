import { useState, useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { api, fileUrl } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { Header } from "@/components/Header";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { rupiah } from "@/lib/format";
import { motion } from "framer-motion";
import { Check, Crown, Sparkles, ArrowLeft, Loader2, ShieldCheck, Timer, QrCode, Upload, Hourglass, BadgeCheck } from "lucide-react";
import { toast } from "sonner";
import Seo from "@/components/Seo";

function fmtCountdown(ms) {
  const s = Math.max(0, Math.floor(ms / 1000));
  const d = Math.floor(s / 86400);
  const h = Math.floor((s % 86400) / 3600);
  const m = Math.floor((s % 3600) / 60);
  const sec = s % 60;
  const pad = (n) => String(n).padStart(2, "0");
  return d > 0 ? `${d} hari ${pad(h)}:${pad(m)}:${pad(sec)}` : `${pad(h)}:${pad(m)}:${pad(sec)}`;
}

const FREE = ["Proyek tanpa batas", "Cash Flow (transaksi masuk/keluar)", "Manajemen Kasbon & Pelunasan Tukang", "Indikator kesehatan finansial", "Upload foto nota"];
const PREMIUM = ["Semua fitur Free", "Progress Pekerjaan & Kurva-S", "Impor RAB dari Excel", "Portal Klien realtime + WhatsApp", "Baseline vs Revisi RAB", "Export Laporan PDF profesional", "Prioritas dukungan"];

function loadSnap(clientKey, production) {
  return new Promise((resolve, reject) => {
    if (window.snap) return resolve();
    const existing = document.getElementById("midtrans-snap");
    if (existing) existing.remove();
    const sc = document.createElement("script");
    sc.id = "midtrans-snap";
    sc.src = production ? "https://app.midtrans.com/snap/snap.js" : "https://app.sandbox.midtrans.com/snap/snap.js";
    sc.async = true;
    sc.setAttribute("data-client-key", clientKey);
    sc.onload = () => resolve();
    sc.onerror = () => reject(new Error("snap load failed"));
    document.head.appendChild(sc);
  });
}

export default function Pricing() {
  const navigate = useNavigate();
  const { isPremium, refreshUser } = useAuth();
  const [busy, setBusy] = useState(false);
  const [pricing, setPricing] = useState(null);
  const [serverOffset, setServerOffset] = useState(0);
  const [nowTick, setNowTick] = useState(Date.now());
  // ---- Pembayaran manual (QRIS pribadi) ----
  const [manualOrder, setManualOrder] = useState(null);
  const [manualOpen, setManualOpen] = useState(false);
  const [proofState, setProofState] = useState("idle"); // idle | uploading | done
  const proofRef = useRef(null);

  useEffect(() => {
    api.get("/settings/public").then((r) => {
      setPricing(r.data);
      if (r.data?.serverNow) setServerOffset(Date.parse(r.data.serverNow) - Date.now());
    }).catch(() => {});
  }, []);

  const endsAt = pricing?.promoEndsAt ? Date.parse(pricing.promoEndsAt) : null;
  const promoLive = !!pricing?.promoActive && (!endsAt || (Date.now() + serverOffset) < endsAt);
  const eff = (base, promo) => (promoLive && promo > 0 && promo < base ? promo : base);
  const mBase = pricing?.monthlyPrice ?? 149000;
  const mPromo = pricing?.monthlyPromo ?? mBase;
  const yBase = pricing?.yearlyPrice ?? 1290000;
  const yPromo = pricing?.yearlyPromo ?? yBase;
  const mEff = eff(mBase, mPromo);
  const yEff = eff(yBase, yPromo);
  const promoOn = promoLive && (mEff < mBase || yEff < yBase);
  const yearSave = mEff > 0 ? Math.round((1 - yEff / (mEff * 12)) * 100) : 0;
  const remaining = promoOn && endsAt ? Math.max(0, endsAt - (nowTick + serverOffset)) : null;

  useEffect(() => {
    if (!promoOn || !endsAt) return undefined;
    const t = setInterval(() => setNowTick(Date.now()), 1000);
    return () => clearInterval(t);
  }, [promoOn, endsAt]);

  const pollOrder = async (orderId) => {
    for (let i = 0; i < 12; i++) {
      try {
        const { data } = await api.get(`/subscription/order/${orderId}`);
        if (data.status === "paid") return true;
        if (["deny", "cancel", "expire", "create_failed"].includes(data.status)) return false;
      } catch { /* keep polling */ }
      await new Promise((r) => setTimeout(r, 2500));
    }
    return null;
  };

  const onPaid = async () => {
    await refreshUser();
    toast.success("Pembayaran berhasil! Premium aktif 🎉");
    setTimeout(() => navigate("/dashboard"), 900);
  };

  // ---- Pembayaran manual (QRIS pribadi) ----
  const manualPay = async (plan) => {
    setBusy(true);
    try {
      const { data } = await api.post("/subscription/checkout-manual", { plan });
      setManualOrder(data);
      setProofState("idle");
      setManualOpen(true);
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Gagal membuat order pembayaran");
    } finally {
      setBusy(false);
    }
  };

  const submitProof = async (file) => {
    if (!file || !manualOrder) return;
    if (!(file.type.startsWith("image/") || file.type === "application/pdf")) {
      toast.error("Bukti harus berupa gambar (JPG/PNG) atau PDF");
      return;
    }
    if (file.size > 2 * 1024 * 1024) {
      toast.error("Ukuran bukti maksimal 2 MB");
      return;
    }
    setProofState("uploading");
    try {
      const fd = new FormData();
      fd.append("file", file);
      const up = await api.post("/upload", fd);
      await api.post(`/subscription/order/${manualOrder.order_id}/proof`, { proofUrl: up.data.path });
      setProofState("done");
      toast.success("Bukti pembayaran terkirim. Menunggu verifikasi admin.");
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Gagal mengunggah bukti pembayaran");
      setProofState("idle");
    }
  };

  const checkManualStatus = async () => {
    if (!manualOrder) return;
    try {
      const { data } = await api.get(`/subscription/order/${manualOrder.order_id}`);
      if (data.status === "paid") {
        setManualOpen(false);
        await onPaid();
      } else if (data.status === "rejected") {
        toast.error("Bukti pembayaran ditolak admin. Silakan unggah ulang bukti yang benar.");
        setProofState("idle");
      } else {
        toast.info("Pembayaran masih menunggu verifikasi admin.");
      }
    } catch {
      toast.error("Gagal memeriksa status");
    }
  };

  const settle = async (orderId) => {
    const ok = await pollOrder(orderId);
    if (ok) { await onPaid(); }
    else {
      toast.info("Menunggu konfirmasi pembayaran. Premium aktif otomatis setelah dikonfirmasi.");
      setBusy(false);
    }
  };

  const upgrade = async (plan) => {
    if (pricing?.paymentMethod === "manual") {
      return manualPay(plan);
    }
    setBusy(true);
    try {
      const { data } = await api.post("/subscription/checkout", { plan });
      await loadSnap(data.client_key, data.production);
      if (!window.snap) {
        if (data.redirect_url) window.location.assign(data.redirect_url);
        return;
      }
      window.snap.pay(data.token, {
        onSuccess: () => settle(data.order_id),
        onPending: () => {
          toast.info("Pembayaran diproses. Selesaikan pembayaran QRIS/GoPay/VA Anda.");
          settle(data.order_id);
        },
        onError: () => { toast.error("Pembayaran gagal"); setBusy(false); },
        onClose: () => { setBusy(false); },
      });
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Gagal memproses pembayaran");
      setBusy(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-50 pf-grain">
      <Seo
        title="Harga & Paket Premium"
        description="Pilih paket ProFinance Interior yang sesuai kebutuhan kontraktor interior Anda. Mulai gratis selamanya, upgrade ke Premium untuk Invoice, Kurva-S, dan Portal Klien."
        keywords="harga aplikasi kontraktor, paket premium profinance, langganan aplikasi interior"
      />
      <Header />
      <main className="max-w-5xl mx-auto px-4 sm:px-6 py-10">
        <button onClick={() => navigate("/dashboard")} className="flex items-center gap-1.5 text-sm text-slate-500 hover:text-slate-900 mb-6">
          <ArrowLeft className="w-4 h-4" /> Kembali ke Dashboard
        </button>

        <div className="text-center mb-10">
          <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-amber-100 text-amber-800 text-xs font-semibold mb-3">
            <Crown className="w-3.5 h-3.5" /> Upgrade
          </span>
          <h1 className="font-display text-3xl sm:text-4xl font-extrabold text-slate-900 tracking-tight">Pilih paket yang tepat</h1>
          <p className="text-slate-500 mt-2 max-w-lg mx-auto">Mulai gratis, upgrade ke Premium untuk membuka tracking progress & laporan PDF profesional.</p>
        </div>

        <div className="grid md:grid-cols-2 gap-6 max-w-3xl mx-auto">
          <Card className="p-7 border-slate-200 bg-white">
            <div className="flex items-center gap-2 mb-1"><Sparkles className="w-5 h-5 text-slate-400" /><h3 className="font-display font-bold text-xl">Free</h3></div>
            <p className="text-slate-500 text-sm">Untuk memulai mengelola proyek.</p>
            <div className="mt-5 mb-6"><span className="font-mono font-extrabold text-4xl text-slate-900">Rp 0</span><span className="text-slate-500">/selamanya</span></div>
            <ul className="space-y-3 mb-6">
              {FREE.map((f) => (
                <li key={f} className="flex items-start gap-2.5 text-sm text-slate-700"><Check className="w-4 h-4 text-slate-400 mt-0.5 shrink-0" />{f}</li>
              ))}
            </ul>
            <Button variant="outline" className="w-full" disabled>{isPremium ? "Paket dasar" : "Paket Anda saat ini"}</Button>
          </Card>

          <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }}>
            <Card className="p-7 border-2 border-amber-500 bg-white relative shadow-lg shadow-amber-500/10 overflow-hidden">
              <div className="absolute top-0 right-0 bg-amber-500 text-white text-[11px] font-bold px-3 py-1 rounded-bl-lg">POPULER</div>
              <div className="flex items-center gap-2 mb-1"><Crown className="w-5 h-5 text-amber-600" /><h3 className="font-display font-bold text-xl">Premium Pro</h3></div>
              <p className="text-slate-500 text-sm">Kontrol penuh proyek & laporan.</p>
              {promoOn && (
                <span data-testid="promo-badge" className="inline-flex items-center gap-1 mt-3 px-2 py-0.5 rounded-full bg-red-100 text-red-600 text-[11px] font-bold">
                  PROMO SPESIAL
                </span>
              )}
              {promoOn && remaining != null && (
                <div data-testid="promo-countdown" className="mt-2 inline-flex items-center gap-1.5 rounded-lg bg-red-50 border border-red-100 px-3 py-1.5 text-xs font-semibold text-red-600">
                  <Timer className="w-3.5 h-3.5" />
                  Berakhir dalam {fmtCountdown(remaining)}
                </div>
              )}
              <div className="mt-3 mb-1 flex items-baseline gap-2 flex-wrap">
                {promoOn && mEff < mBase && (
                  <span className="font-mono text-lg text-slate-400 line-through" data-testid="monthly-base">{rupiah(mBase)}</span>
                )}
                <span className="font-mono font-extrabold text-4xl text-slate-900" data-testid="monthly-eff">{rupiah(mEff)}</span>
                <span className="text-slate-500">/bulan</span>
              </div>
              <p className="text-xs text-slate-400 mb-5">
                atau {rupiah(yEff)} / tahun{yearSave > 0 ? ` (hemat ${yearSave}%)` : ""}
              </p>
              <ul className="space-y-3 mb-6">
                {PREMIUM.map((f) => (
                  <li key={f} className="flex items-start gap-2.5 text-sm text-slate-700"><Check className="w-4 h-4 text-amber-600 mt-0.5 shrink-0" />{f}</li>
                ))}
              </ul>
              {isPremium ? (
                <Button className="w-full bg-green-600 hover:bg-green-600 text-white gap-2" disabled><Crown className="w-4 h-4" /> Premium Aktif</Button>
              ) : (
                <div className="space-y-2">
                  <Button data-testid="btn-upgrade-premium" onClick={() => upgrade("monthly")} disabled={busy} className="w-full bg-amber-600 hover:bg-amber-700 text-white gap-2">
                    {busy ? <Loader2 className="w-4 h-4 animate-spin" /> : <Crown className="w-4 h-4" />} Bayar Bulanan · {rupiah(mEff)}
                  </Button>
                  <Button data-testid="btn-upgrade-yearly" variant="outline" onClick={() => upgrade("yearly")} disabled={busy} className="w-full border-amber-300 text-amber-700 hover:bg-amber-50">
                    Bayar Tahunan · {rupiah(yEff)} (Hemat)
                  </Button>
                  {pricing?.paymentMethod === "manual" ? (
                    <p className="flex items-center justify-center gap-1.5 text-[11px] text-slate-400 pt-1" data-testid="pay-note-manual">
                      <QrCode className="w-3.5 h-3.5" /> Pembayaran manual via QRIS — Premium aktif setelah diverifikasi admin
                    </p>
                  ) : (
                    <p className="flex items-center justify-center gap-1.5 text-[11px] text-slate-400 pt-1">
                      <ShieldCheck className="w-3.5 h-3.5" /> Pembayaran aman via Midtrans — QRIS, GoPay & VA Bank
                    </p>
                  )}
                </div>
              )}
            </Card>
          </motion.div>
        </div>
      </main>

      <Dialog open={manualOpen} onOpenChange={setManualOpen}>
        <DialogContent className="bg-white max-w-sm" data-testid="manual-pay-dialog">
          <DialogHeader>
            <DialogTitle className="font-display text-xl flex items-center gap-2"><QrCode className="w-5 h-5 text-amber-600" /> Pembayaran via QRIS</DialogTitle>
          </DialogHeader>
          {manualOrder && (
            <div className="space-y-4">
              <div className="rounded-lg bg-amber-50 border border-amber-200 px-4 py-3 text-center">
                <div className="text-[11px] text-amber-700 font-medium">{manualOrder.label}</div>
                <div className="font-mono font-extrabold text-2xl text-slate-900" data-testid="manual-amount">{rupiah(manualOrder.gross_amount)}</div>
                <div className="text-[10px] text-slate-400 mt-0.5">Order: {manualOrder.order_id}</div>
              </div>

              {pricing?.qrisImage ? (
                <div className="flex justify-center">
                  <img src={fileUrl(pricing.qrisImage)} alt="QRIS Pembayaran" data-testid="qris-image" className="w-56 h-56 rounded-lg border border-slate-200 object-contain bg-white" />
                </div>
              ) : (
                <div className="rounded-lg border-2 border-dashed border-slate-200 p-6 text-center text-sm text-slate-400">
                  Gambar QRIS belum diatur admin. Silakan hubungi admin.
                </div>
              )}

              <ol className="text-xs text-slate-600 space-y-1.5 list-decimal list-inside">
                <li>Scan QRIS di atas dengan aplikasi e-wallet/m-banking Anda</li>
                <li>Bayar <b>persis</b> sebesar nominal di atas</li>
                <li>Unggah bukti pembayaran (screenshot) di bawah ini</li>
              </ol>
              {pricing?.paymentNote && (
                <p className="text-[11px] text-slate-500 bg-slate-50 rounded-lg border border-slate-200 px-3 py-2" data-testid="payment-note">{pricing.paymentNote}</p>
              )}

              {proofState === "done" ? (
                <div className="rounded-lg bg-green-50 border border-green-200 p-4 text-center space-y-2" data-testid="proof-done">
                  <BadgeCheck className="w-8 h-8 text-green-600 mx-auto" />
                  <div className="text-sm font-semibold text-green-800">Bukti terkirim!</div>
                  <p className="text-xs text-green-700 flex items-center justify-center gap-1"><Hourglass className="w-3.5 h-3.5" /> Premium aktif setelah admin memverifikasi pembayaran Anda.</p>
                  <Button size="sm" variant="outline" data-testid="check-status-btn" onClick={checkManualStatus} className="border-green-300 text-green-700 hover:bg-green-100">Cek Status Verifikasi</Button>
                </div>
              ) : (
                <div>
                  <input
                    ref={proofRef}
                    type="file"
                    accept="image/*,application/pdf"
                    className="hidden"
                    data-testid="proof-file-input"
                    onChange={(e) => { const f = e.target.files?.[0]; if (f) submitProof(f); e.target.value = ""; }}
                  />
                  <Button
                    data-testid="proof-upload-btn"
                    onClick={() => proofRef.current?.click()}
                    disabled={proofState === "uploading"}
                    className="w-full bg-amber-600 hover:bg-amber-700 text-white gap-2"
                  >
                    {proofState === "uploading" ? <Loader2 className="w-4 h-4 animate-spin" /> : <Upload className="w-4 h-4" />}
                    {proofState === "uploading" ? "Mengunggah bukti..." : "Unggah Bukti Pembayaran"}
                  </Button>
                  <p className="text-[10px] text-slate-400 text-center mt-1.5">Gambar/PDF, maks 2 MB</p>
                </div>
              )}
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
