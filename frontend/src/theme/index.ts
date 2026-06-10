/**
 * Design tokens — Creator Noir.
 * Source of truth: /app/design_guidelines.json
 */
export const colors = {
  bg: "#09090B",
  surface1: "#18181B",
  surface2: "#27272A",
  surface3: "#3F3F46",
  primary: "#FF4433",
  primaryMuted: "rgba(255, 68, 51, 0.2)",
  aiAccent: "#00E5FF",
  aiAccentMuted: "rgba(0, 229, 255, 0.15)",
  textHigh: "#FFFFFF",
  textMedium: "#A1A1AA",
  textLow: "#52525B",
  border: "#27272A",
  borderFocus: "#FF4433",
  danger: "#FF4433",
  success: "#00FF66",
  warning: "#FFD60A",
  viral: {
    highText: "#00FF66",
    highBg: "rgba(0, 255, 102, 0.15)",
    highBorder: "#00FF66",
    medText: "#FFD60A",
    medBg: "rgba(255, 214, 10, 0.15)",
    medBorder: "#FFD60A",
    lowText: "#FF4433",
    lowBg: "rgba(255, 68, 51, 0.15)",
    lowBorder: "#FF4433",
  },
};

export const spacing = {
  xs: 4,
  sm: 8,
  md: 12,
  lg: 16,
  xl: 20,
  xxl: 24,
  xxxl: 32,
  screenPadding: 20,
};

export const radius = { sm: 8, md: 12, lg: 16, xl: 20, pill: 999 };

// Use system font with weight; design guidelines allow this fallback.
export const typography = {
  h1: { fontFamily: "System", fontSize: 36, lineHeight: 44, letterSpacing: -1, fontWeight: "800" as const },
  h2: { fontFamily: "System", fontSize: 28, lineHeight: 34, letterSpacing: -0.5, fontWeight: "800" as const },
  h3: { fontFamily: "System", fontSize: 20, lineHeight: 28, fontWeight: "700" as const },
  body: { fontFamily: "System", fontSize: 16, lineHeight: 24, fontWeight: "400" as const },
  bodyMed: { fontFamily: "System", fontSize: 16, lineHeight: 24, fontWeight: "600" as const },
  label: { fontFamily: "System", fontSize: 14, lineHeight: 20, fontWeight: "500" as const },
  chip: { fontFamily: "System", fontSize: 14, lineHeight: 20, letterSpacing: 0.2, fontWeight: "600" as const },
  caption: { fontFamily: "System", fontSize: 12, lineHeight: 16, fontWeight: "500" as const },
  overline: {
    fontFamily: "System",
    fontSize: 11,
    lineHeight: 16,
    letterSpacing: 1.5,
    fontWeight: "800" as const,
    textTransform: "uppercase" as const,
  },
};
