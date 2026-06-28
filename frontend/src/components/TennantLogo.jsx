import React from "react";
import { useBranding } from "../lib/branding";

/**
 * BrandLogo — renders the active company's logo. For brands that ship a
 * dedicated logo asset (orisei-freight → /brand/orisei_logo.png) the PNG is
 * shown inside a gold-ringed disc. For the built-in Tennant and generated
 * brands, the original colored pill with the short_name is rendered.
 */
export const TennantLogo = ({ size = "md", className = "" }) => {
  const { brand } = useBranding();
  const isDefault = brand?.brand_id === "orisei-freight" || !brand?.brand_id;

  // Orisei custom-asset path — uses the Queen Calafia + griffin emblem.
  if (brand?.brand_id === "orisei-freight") {
    const px = { sm: 28, md: 36, lg: 52 }[size] || 36;
    return (
      <div
        className={`relative inline-flex items-center justify-center rounded-full ${className}`}
        style={{
          width: px, height: px,
          background: "#0E3A6B",
          border: "1.5px solid #C9A24A",
          boxShadow: "0 0 0 1px rgba(201,162,74,0.25), 0 4px 12px -4px rgba(14,58,107,0.6)",
        }}
        data-testid="brand-logo"
        aria-label={brand?.company_name || "Orisei Freight Solutions"}
      >
        <img
          src="/brand/orisei_logo.png"
          alt="Orisei"
          style={{ width: px - 6, height: px - 6, objectFit: "contain", borderRadius: "50%" }}
        />
      </div>
    );
  }

  const text = (brand?.short_name || "TENNANT").toUpperCase();
  const fill = isDefault ? "#00A4E4" : (brand?.primary_color || "#00A4E4");
  const stroke = isDefault ? "#005f99" : shade(fill, -25);

  // Auto-size the pill width to the text length so long brand names ("WALMART",
  // "PROCTER & GAMBLE") still fit cleanly.
  const charBudget = Math.max(text.length, 6);
  const baseW = { sm: 9.5, md: 13, lg: 18 }[size] || 13;
  const dims = {
    sm: { w: Math.round(charBudget * baseW + 16), h: 28, fs: 13 },
    md: { w: Math.round(charBudget * baseW + 22), h: 36, fs: 18 },
    lg: { w: Math.round(charBudget * baseW + 30), h: 52, fs: 26 },
  }[size] || { w: 140, h: 36, fs: 18 };

  return (
    <svg
      viewBox={`0 0 ${dims.w} ${dims.h}`}
      width={dims.w}
      height={dims.h}
      className={className}
      data-testid="brand-logo"
      aria-label={brand?.company_name || "Orisei Freight Solutions"}
    >
      <rect
        x={1} y={1}
        width={dims.w - 2} height={dims.h - 2}
        rx={dims.h / 2} ry={dims.h / 2}
        fill={fill} stroke={stroke} strokeWidth={1}
      />
      <text
        x="50%" y="50%"
        dominantBaseline="middle" textAnchor="middle"
        fill="#FFFFFF"
        fontFamily="Chivo, sans-serif"
        fontWeight="900"
        fontSize={dims.fs}
        letterSpacing={dims.fs > 20 ? "1.5" : "0.8"}
      >
        {text}
      </text>
      <text
        x={dims.w - 6} y={10}
        fill="#FFFFFF" fontSize="6" fontFamily="Arial"
      >®</text>
    </svg>
  );
};

// shade("#0071CE", -25) -> darker stroke color
function shade(hex, pct) {
  const h = hex.replace("#", "");
  if (h.length !== 6) return "#0a3a59";
  const r = parseInt(h.slice(0, 2), 16);
  const g = parseInt(h.slice(2, 4), 16);
  const b = parseInt(h.slice(4, 6), 16);
  const f = (c) => Math.max(0, Math.min(255, Math.round(c + (c * pct) / 100)));
  return "#" + [f(r), f(g), f(b)].map((x) => x.toString(16).padStart(2, "0")).join("");
}

export default TennantLogo;
