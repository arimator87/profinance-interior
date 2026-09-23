import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, workersPdfUrl, workerPdfUrl } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription,
  AlertDialogFooter, AlertDialogHeader, AlertDialogTitle, AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import { Plus, HardHat, Loader2, Trash2, Wallet, HandCoins, CheckCircle2, Pencil, FileDown, Lock } from "lucide-react";
import { rupiah } from "@/lib/format";
import { toast } from "sonner";

export function TukangTab({ project, workers, onChange }) {
  const { isPremium } = useAuth();
  const navigate = useNavigate();
  const [addOpen, setAddOpen] = useState(false);
  const [form, setForm] = useState({ name: "", borongan: "" });
  const [editWorkerId, setEditWorkerId] = useState(null);
  const [busy, setBusy] = useState(false);
  const [payOpen, setPayOpen] = useState(false);
  const [payWorker, setPayWorker] = useState(null);
  const [payType, setPayType] = useState("kasbon");
  const [payAmount, setPayAmount] = useState("");

  const openAdd = () => { setEditWorkerId(null); setForm({ name: "", borongan: "" }); setAddOpen(true); };
  const openEdit = (w) => { setEditWorkerId(w.id); setForm({ name: w.name, borongan: String(w.borongan || "") }); setAddOpen(true); };

  const saveWorker = async () => {
    if (!form.name) return toast.error("Nama tukang wajib diisi");
    setBusy(true);
    try {
      const payload = { name: form.name, borongan: parseInt(form.borongan || 0, 10) };
      if (editWorkerId) {
        await api.put(`/workers/${editWorkerId}`, payload);
        toast.success("Data tukang diperbarui");
      } else {
        await api.post(`/projects/${project.id}/workers`, payload);
        toast.success("Tukang ditambahkan");
      }
      setAddOpen(false); setEditWorkerId(null); setForm({ name: "", borongan: "" }); onChange();
    } catch { toast.error("Gagal menyimpan data tukang"); } finally { setBusy(false); }
  };

  const openPay = (w, type) => { setPayWorker(w); setPayType(type); setPayAmount(""); setPayOpen(true); };

  const doPay = async () => {
    if (!payAmount || parseInt(payAmount, 10) <= 0) return toast.error("Jumlah harus lebih dari 0");
    setBusy(true);
    try {
      await api.post(`/workers/${payWorker.id}/pay`, { type: payType, amount: parseInt(payAmount, 10) });
      toast.success(payType === "kasbon" ? "Kasbon dicatat" : "Pelunasan dicatat");
      setPayOpen(false); onChange();
    } catch { toast.error("Gagal mencatat"); } finally { setBusy(false); }
  };

  const remove = async (id) => {
    try { await api.delete(`/workers/${id}`); toast.success("Tukang dihapus"); onChange(); }
    catch { toast.error("Gagal menghapus"); }
  };

  const openPdf = (url) => {
    if (!isPremium) {
      toast.error("Laporan PDF tukang adalah fitur Premium");
      navigate("/pricing");
      return;
    }
    window.open(url, "_blank");
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <h3 className="font-display font-bold text-lg text-slate-900">Kasbon & Tukang</h3>
        <div className="flex items-center gap-2">
          {workers.length > 0 && (
            <Button data-testid="btn-workers-pdf" size="sm" variant="outline" onClick={() => openPdf(workersPdfUrl(project.id))} className="gap-1.5 border-amber-300 text-amber-700 hover:bg-amber-50">
              <FileDown className="w-4 h-4" /> PDF Semua {!isPremium && <Lock className="w-3 h-3 text-amber-500" />}
            </Button>
          )}
          <Button data-testid="btn-add-tukang" size="sm" onClick={openAdd} className="bg-amber-600 hover:bg-amber-700 text-white gap-1.5">
            <Plus className="w-4 h-4" /> Tukang
          </Button>
        </div>
      </div>

      {workers.length === 0 ? (
        <Card className="p-10 text-center border-dashed border-2 bg-white/50">
          <HardHat className="w-10 h-10 text-slate-300 mx-auto mb-3" />
          <p className="text-slate-500 text-sm">Belum ada tukang. Tambahkan pekerja & nilai borongan.</p>
        </Card>
      ) : (
        <div className="grid sm:grid-cols-2 gap-4">
          {workers.map((w) => {
            const paidPct = w.borongan > 0 ? Math.min(100, (w.totalDibayar / w.borongan) * 100) : 0;
            const lunas = w.sisaHutang <= 0 && w.borongan > 0;
            return (
              <Card data-testid={`worker-card-${w.id}`} key={w.id} className="p-4 border-slate-200 bg-white">
                <div className="flex items-start justify-between gap-2">
                  <div className="flex items-center gap-2.5 min-w-0">
                    <div className="w-9 h-9 rounded-lg bg-amber-100 flex items-center justify-center shrink-0"><HardHat className="w-5 h-5 text-amber-600" /></div>
                    <div className="min-w-0">
                      <div className="font-semibold text-slate-900 truncate">{w.name}</div>
                      <div className="text-xs text-slate-500">Borongan {rupiah(w.borongan)}</div>
                    </div>
                  </div>
                  <div className="flex items-center gap-1.5 shrink-0">
                    <button data-testid={`pdf-worker-${w.id}`} title="Unduh laporan PDF tukang ini" onClick={() => openPdf(workerPdfUrl(w.id))} className="text-slate-300 hover:text-amber-600"><FileDown className="w-4 h-4" /></button>
                    <button data-testid={`edit-worker-${w.id}`} onClick={() => openEdit(w)} className="text-slate-300 hover:text-amber-600"><Pencil className="w-4 h-4" /></button>
                    <AlertDialog>
                      <AlertDialogTrigger asChild><button data-testid={`delete-worker-${w.id}`} className="text-slate-300 hover:text-red-500"><Trash2 className="w-4 h-4" /></button></AlertDialogTrigger>
                      <AlertDialogContent className="bg-white">
                        <AlertDialogHeader><AlertDialogTitle>Hapus tukang?</AlertDialogTitle><AlertDialogDescription>Data tukang akan dihapus (transaksi kasbon tetap tersimpan di cash flow).</AlertDialogDescription></AlertDialogHeader>
                        <AlertDialogFooter><AlertDialogCancel>Batal</AlertDialogCancel><AlertDialogAction onClick={() => remove(w.id)} className="bg-red-600 hover:bg-red-700">Hapus</AlertDialogAction></AlertDialogFooter>
                      </AlertDialogContent>
                    </AlertDialog>
                  </div>
                </div>

                <div className="mt-3.5 grid grid-cols-3 gap-2 text-center">
                  <div className="rounded-lg bg-slate-50 p-2"><div className="text-[10px] text-slate-400">Kasbon</div><div className="font-mono font-semibold text-xs text-slate-800">{rupiah(w.totalKasbon)}</div></div>
                  <div className="rounded-lg bg-slate-50 p-2"><div className="text-[10px] text-slate-400">Pelunasan</div><div className="font-mono font-semibold text-xs text-slate-800">{rupiah(w.totalPelunasan)}</div></div>
                  <div className="rounded-lg p-2" style={{ background: lunas ? "#DCFCE7" : "#FEF3C7" }}><div className="text-[10px] text-slate-500">Sisa Hutang</div><div className="font-mono font-bold text-xs" style={{ color: lunas ? "#15803D" : "#B45309" }}>{rupiah(w.sisaHutang)}</div></div>
                </div>

                <Progress value={paidPct} className="h-1.5 mt-3" />
                <div className="flex items-center justify-between mt-1"><span className="text-[11px] text-slate-400">{paidPct.toFixed(0)}% terbayar</span>{lunas && <span className="inline-flex items-center gap-1 text-[11px] text-green-600 font-medium"><CheckCircle2 className="w-3 h-3" /> Lunas</span>}</div>

                <div className="flex gap-2 mt-3">
                  <Button data-testid={`worker-kasbon-${w.id}`} size="sm" variant="outline" onClick={() => openPay(w, "kasbon")} className="flex-1 gap-1.5 text-xs h-8"><HandCoins className="w-3.5 h-3.5" /> Bayar Kasbon</Button>
                  <Button data-testid={`worker-pelunasan-${w.id}`} size="sm" onClick={() => openPay(w, "pelunasan")} className="flex-1 gap-1.5 text-xs h-8 bg-slate-900 hover:bg-slate-800 text-white"><Wallet className="w-3.5 h-3.5" /> Pelunasan</Button>
                </div>
              </Card>
            );
          })}
        </div>
      )}

      <Dialog open={addOpen} onOpenChange={setAddOpen}>
        <DialogContent className="bg-white max-w-sm">
          <DialogHeader><DialogTitle className="font-display text-xl">{editWorkerId ? "Edit Data Tukang" : "Tambah Tukang"}</DialogTitle></DialogHeader>
          <div className="space-y-3.5">
            <div><Label>Nama Tukang</Label><Input data-testid="worker-name-input" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="Pak Slamet" className="mt-1" /></div>
            <div><Label>Nilai Borongan (Rp)</Label><Input data-testid="worker-borongan-input" type="number" value={form.borongan} onChange={(e) => setForm({ ...form, borongan: e.target.value })} placeholder="45000000" className="mt-1 font-mono" /></div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setAddOpen(false)}>Batal</Button>
            <Button data-testid="worker-submit-button" onClick={saveWorker} disabled={busy} className="bg-amber-600 hover:bg-amber-700 text-white">{busy ? <Loader2 className="w-4 h-4 animate-spin" /> : (editWorkerId ? "Simpan Perubahan" : "Simpan")}</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={payOpen} onOpenChange={setPayOpen}>
        <DialogContent className="bg-white max-w-sm">
          <DialogHeader><DialogTitle className="font-display text-xl">{payType === "kasbon" ? "Bayar Kasbon" : "Pelunasan Upah"}</DialogTitle></DialogHeader>
          <p className="text-sm text-slate-500 -mt-2">Untuk <b>{payWorker?.name}</b>. Akan dicatat sebagai pengeluaran di Cash Flow.</p>
          <div><Label>Jumlah (Rp)</Label><Input data-testid="pay-amount-input" type="number" value={payAmount} onChange={(e) => setPayAmount(e.target.value)} placeholder="0" className="mt-1 font-mono" /></div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setPayOpen(false)}>Batal</Button>
            <Button data-testid="pay-submit-button" onClick={doPay} disabled={busy} className="bg-amber-600 hover:bg-amber-700 text-white">{busy ? <Loader2 className="w-4 h-4 animate-spin" /> : "Catat"}</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
