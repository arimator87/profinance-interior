import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger, DropdownMenuSeparator, DropdownMenuLabel,
} from "@/components/ui/dropdown-menu";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Crown, LogOut, LayoutDashboard, Sparkles, Ruler, PlayCircle, Receipt, BellRing, Bell, Settings, Users, Megaphone, Newspaper } from "lucide-react";
import { toast } from "sonner";

const BANNER_THEMES = {
  info: "bg-blue-600 text-white",
  promo: "bg-slate-900 text-amber-50",
  warning: "bg-red-600 text-white",
};

export function Header() {
  const { user, logout, isPremium, isDemo, isAdmin } = useAuth();
  const navigate = useNavigate();
  const [announcement, setAnnouncement] = useState("");
  const [annTheme, setAnnTheme] = useState("info");
  const [pendingPayments, setPendingPayments] = useState(0);

  // Badge lonceng admin: jumlah pembayaran manual yang menunggu verifikasi (poll tiap 30 dtk)
  useEffect(() => {
    if (!isAdmin) return undefined;
    let active = true;
    const load = () =>
      api.get("/admin/manual-orders/count")
        .then((r) => { if (active) setPendingPayments(r.data?.count || 0); })
        .catch(() => {});
    load();
    const t = setInterval(load, 30000);
    return () => { active = false; clearInterval(t); };
  }, [isAdmin]);

  useEffect(() => {
    let active = true;
    api.get("/settings/public")
      .then((r) => {
        if (active) {
          setAnnouncement((r.data?.announcement || "").trim());
          setAnnTheme(r.data?.announcementTheme || "info");
        }
      })
      .catch(() => {});
    return () => { active = false; };
  }, []);

  const expiry = user?.subscriptionExpiry ? new Date(user.subscriptionExpiry) : null;
  const daysLeft = expiry ? Math.ceil((expiry - new Date()) / 86400000) : null;
  const dismissKey = expiry ? `pf_renew_dismiss_${user?.user_id}_${expiry.toISOString().slice(0, 10)}` : null;
  const [renewDismissed, setRenewDismissed] = useState(() => (dismissKey ? localStorage.getItem(dismissKey) === "1" : false));
  const showRenew = isPremium && !isDemo && daysLeft != null && daysLeft <= 7 && !renewDismissed;
  const dismissRenew = () => { if (dismissKey) localStorage.setItem(dismissKey, "1"); setRenewDismissed(true); };

  const initials = (user?.name || user?.email || "U")
    .split(" ").map((s) => s[0]).slice(0, 2).join("").toUpperCase();

  return (
    <header className="sticky top-0 z-40 border-b border-slate-200 bg-white/85 backdrop-blur-xl">
      {announcement && (
        <div data-testid="announcement-banner" className={`${BANNER_THEMES[annTheme] || BANNER_THEMES.info} text-xs sm:text-sm px-4 py-2 flex items-center justify-center gap-2 text-center`}>
          <Megaphone className={`w-4 h-4 shrink-0 ${annTheme === "promo" ? "text-amber-400" : "text-white/90"}`} />
          <span className="font-medium">{announcement}</span>
        </div>
      )}
      {isDemo && (
        <div data-testid="demo-banner" className="bg-blue-600 text-white text-xs sm:text-sm px-4 py-2 text-center">
          <span className="font-semibold">Mode Demo (baca-saja)</span> — Anda menjelajah dengan data contoh.{" "}
          <button data-testid="demo-register-btn" onClick={async () => { await logout(); navigate("/login"); }} className="underline font-semibold hover:text-blue-100">Daftar gratis</button>{" "}
          untuk mengelola proyek Anda.
        </div>
      )}
      {showRenew && (
        <div data-testid="renewal-banner" className="bg-amber-500 text-white text-xs sm:text-sm px-4 py-2 flex items-center justify-center gap-2 flex-wrap">
          <BellRing className="w-4 h-4 shrink-0" />
          <span>
            {daysLeft < 0 ? "Premium Anda telah berakhir." : `Premium Anda berakhir dalam ${daysLeft} hari.`}{" "}
            <button data-testid="renewal-cta" onClick={() => navigate("/pricing")} className="underline font-semibold hover:text-amber-100">Perpanjang sekarang</button>
          </span>
          <button data-testid="renewal-dismiss" onClick={dismissRenew} className="ml-2 text-white/80 hover:text-white font-semibold">✕</button>
        </div>
      )}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 h-16 flex items-center justify-between gap-4">
        <button
          data-testid="header-logo"
          onClick={() => navigate("/dashboard")}
          className="flex items-center gap-2.5 group"
        >
          <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-amber-500 to-amber-700 flex items-center justify-center shadow-sm shadow-amber-500/30 group-hover:scale-105 transition-transform">
            <Ruler className="w-5 h-5 text-white" />
          </div>
          <div className="text-left leading-tight">
            <div className="font-display font-extrabold text-slate-900 text-[15px]">ProFinance</div>
            <div className="text-[10px] tracking-widest text-amber-600 font-semibold -mt-0.5">INTERIOR</div>
          </div>
        </button>

        <div className="flex items-center gap-2 sm:gap-3">
          <span
            data-testid="tier-badge"
            className={`hidden sm:inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-semibold ${
              isDemo ? "bg-blue-100 text-blue-700" : isPremium ? "bg-amber-100 text-amber-800" : "bg-slate-100 text-slate-600"
            }`}
          >
            {isDemo ? <PlayCircle className="w-3.5 h-3.5" /> : isPremium ? <Crown className="w-3.5 h-3.5" /> : <Sparkles className="w-3.5 h-3.5" />}
            {isDemo ? "Mode Demo" : isPremium ? "Premium" : "Free"}
          </span>

          {!isPremium && (
            <Button
              data-testid="header-upgrade-btn"
              size="sm"
              onClick={() => navigate("/pricing")}
              className="bg-amber-600 hover:bg-amber-700 text-white gap-1.5"
            >
              <Crown className="w-4 h-4" /> Upgrade
            </Button>
          )}

          {isAdmin && (
            <button
              data-testid="admin-notif-bell"
              onClick={() => navigate("/admin/settings")}
              title={pendingPayments > 0 ? `${pendingPayments} pembayaran menunggu verifikasi` : "Tidak ada pembayaran menunggu verifikasi"}
              className="relative w-9 h-9 rounded-full border border-slate-200 bg-white hover:bg-slate-50 flex items-center justify-center transition-colors"
            >
              <Bell className={`w-4 h-4 ${pendingPayments > 0 ? "text-amber-600" : "text-slate-400"}`} />
              {pendingPayments > 0 && (
                <span
                  data-testid="admin-notif-badge"
                  className="absolute -top-1 -right-1 min-w-[18px] h-[18px] px-1 rounded-full bg-red-600 text-white text-[10px] font-bold flex items-center justify-center animate-pulse"
                >
                  {pendingPayments > 99 ? "99+" : pendingPayments}
                </span>
              )}
            </button>
          )}

          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <button data-testid="user-menu-trigger" className="rounded-full outline-none ring-offset-2 focus:ring-2 focus:ring-amber-500">
                <Avatar className="w-9 h-9 border border-slate-200">
                  <AvatarImage src={user?.picture} />
                  <AvatarFallback className="bg-slate-900 text-white text-xs font-semibold">{initials}</AvatarFallback>
                </Avatar>
              </button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-60 bg-white">
              <DropdownMenuLabel className="flex flex-col">
                <span className="font-semibold text-slate-900 truncate">{user?.name || "Pengguna"}</span>
                <span className="text-xs text-slate-500 font-normal truncate">{user?.email}</span>
              </DropdownMenuLabel>
              <DropdownMenuSeparator />
              <DropdownMenuItem data-testid="menu-dashboard" onClick={() => navigate("/dashboard")}>
                <LayoutDashboard className="w-4 h-4 mr-2" /> Dashboard
              </DropdownMenuItem>
              <DropdownMenuItem data-testid="menu-account" onClick={() => navigate("/account")}>
                <Receipt className="w-4 h-4 mr-2" /> Akun & Transaksi
              </DropdownMenuItem>
              <DropdownMenuItem data-testid="menu-pricing" onClick={() => navigate("/pricing")}>
                <Crown className="w-4 h-4 mr-2" /> Paket & Upgrade
              </DropdownMenuItem>
              {isAdmin && (
                <>
                  <DropdownMenuItem data-testid="menu-admin-settings" onClick={() => navigate("/admin/settings")}>
                    <Settings className="w-4 h-4 mr-2" /> Pengaturan Admin
                  </DropdownMenuItem>
                  <DropdownMenuItem data-testid="menu-admin-users" onClick={() => navigate("/admin/users")}>
                    <Users className="w-4 h-4 mr-2" /> Manajemen Pengguna
                  </DropdownMenuItem>
                  <DropdownMenuItem data-testid="menu-admin-articles" onClick={() => navigate("/admin/articles")}>
                    <Newspaper className="w-4 h-4 mr-2" /> Kelola Blog & Artikel
                  </DropdownMenuItem>
                </>
              )}
              <DropdownMenuSeparator />
              <DropdownMenuItem data-testid="menu-logout" onClick={async () => { await logout(); navigate("/login"); }} className="text-red-600 focus:text-red-600">
                <LogOut className="w-4 h-4 mr-2" /> Keluar
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </div>
    </header>
  );
}
