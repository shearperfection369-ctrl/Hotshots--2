import React from "react";

// Iconic Tennant Company logo: white "TENNANT" text inside a blue rounded oval.
// Vector recreation to ensure crisp render across sizes — no external dependency.
export const TennantLogo = ({ size = "md", className = "" }) => {
  const dims = {
    sm: { w: 80, h: 28, fs: 13 },
    md: { w: 110, h: 36, fs: 18 },
    lg: { w: 160, h: 52, fs: 26 },
  }[size] || { w: 110, h: 36, fs: 18 };
  return (
    <svg
      viewBox={`0 0 ${dims.w} ${dims.h}`}
      width={dims.w}
      height={dims.h}
      className={className}
      data-testid="tennant-logo"
      aria-label="Tennant Company"
    >
      <rect
        x={1}
        y={1}
        width={dims.w - 2}
        height={dims.h - 2}
        rx={dims.h / 2}
        ry={dims.h / 2}
        fill="#00A4E4"
        stroke="#005f99"
        strokeWidth={1}
      />
      <text
        x="50%"
        y="50%"
        dominantBaseline="middle"
        textAnchor="middle"
        fill="#FFFFFF"
        fontFamily="Chivo, sans-serif"
        fontWeight="900"
        fontSize={dims.fs}
        letterSpacing={dims.fs > 20 ? "1.5" : "0.8"}
      >
        TENNANT
      </text>
      <text
        x={dims.w - 6}
        y={10}
        fill="#FFFFFF"
        fontSize="6"
        fontFamily="Arial"
      >
        ®
      </text>
    </svg>
  );
};

export default TennantLogo;
