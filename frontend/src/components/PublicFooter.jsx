import React from "react";
import { Link } from "react-router-dom";

/**
 * Shared public-site footer.
 */
export default function PublicFooter({ brand }) {
  return (
    <footer className="border-t border-white/5 bg-[#080F1B]">
      <div className="max-w-7xl mx-auto px-6 py-8 flex flex-col md:flex-row items-center justify-between gap-4 text-xs text-slate-500">
        <div className="flex items-center gap-3">
          <img src={brand?.logo_url || "/brand/orisei_logo.png"} alt="Orisei" className="h-6 w-6" />
          <span>{brand?.company_name || "Orisei Freight Solutions LLC"} · Minneapolis · Saint Paul · Minnesota</span>
        </div>
        <div className="flex items-center gap-5 font-mono uppercase tracking-wider">
          <Link to="/services" className="hover:text-white">Services</Link>
          <Link to="/lanes" className="hover:text-white">Lanes</Link>
          <Link to="/about" className="hover:text-white">About</Link>
          <Link to="/contact" className="hover:text-white">Contact</Link>
        </div>
        <div className="font-mono uppercase tracking-wider">
          © {new Date().getFullYear()} · MC# pending · BMC-84 surety bond
        </div>
      </div>
    </footer>
  );
}
