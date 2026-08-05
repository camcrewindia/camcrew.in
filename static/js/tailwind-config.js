/* ═══════════════════════════════════════════════════════════════════
   Camcrew Studio — Shared Tailwind Configuration
   Edit here and every page picks up the change automatically.
   ═══════════════════════════════════════════════════════════════════ */
tailwind.config = {
    darkMode: "class",
    theme: {
        extend: {
            colors: {
                "obsidian-base":               "#0A0A0B",
                "charcoal-surface":            "#161618",
                "background":                  "#0d1515",
                "surface":                     "#0d1515",
                "surface-dim":                 "#0d1515",
                "surface-bright":              "#333b3b",
                "surface-variant":             "#2e3637",
                "surface-container-lowest":    "#080f10",
                "surface-container-low":       "#151d1e",
                "surface-container":           "#192122",
                "surface-container-high":      "#232b2c",
                "surface-container-highest":   "#2e3637",
                "surface-tint":                "#00dbe9",
                "on-background":               "#dce4e5",
                "on-surface":                  "#dce4e5",
                "on-surface-variant":          "#b9cacb",
                "inverse-surface":             "#dce4e5",
                "inverse-on-surface":          "#2a3233",
                "primary":                     "#dbfcff",
                "primary-container":           "#00f0ff",
                "primary-fixed":               "#7df4ff",
                "primary-fixed-dim":           "#00dbe9",
                "on-primary":                  "#00363a",
                "on-primary-container":        "#006970",
                "on-primary-fixed":            "#002022",
                "on-primary-fixed-variant":    "#004f54",
                "inverse-primary":             "#006970",
                "secondary":                   "#ebb2ff",
                "secondary-container":         "#b600f8",
                "secondary-fixed":             "#f8d8ff",
                "secondary-fixed-dim":         "#ebb2ff",
                "on-secondary":                "#520072",
                "on-secondary-container":      "#fff6fc",
                "on-secondary-fixed":          "#320047",
                "on-secondary-fixed-variant":  "#74009f",
                "tertiary":                    "#f9f5f5",
                "tertiary-container":          "#dcd9d8",
                "tertiary-fixed":              "#e5e2e1",
                "tertiary-fixed-dim":          "#c8c6c5",
                "on-tertiary":                 "#313030",
                "on-tertiary-container":       "#605f5e",
                "on-tertiary-fixed":           "#1c1b1b",
                "on-tertiary-fixed-variant":   "#474646",
                "error":                       "#ffb4ab",
                "error-container":             "#93000a",
                "on-error":                    "#690005",
                "on-error-container":          "#ffdad6",
                "outline":                     "#849495",
                "outline-variant":             "#3b494b",
                "glass-stroke":                "rgba(255, 255, 255, 0.12)",
                "neon-blue-glow":              "rgba(0, 240, 255, 0.4)",
                "neon-purple-glow":            "rgba(188, 19, 254, 0.4)"
            },
            borderRadius: {
                "DEFAULT": "0.25rem",
                "lg":      "0.5rem",
                "xl":      "0.75rem",
                "full":    "9999px"
            },
            spacing: {
                "stack-xs":       "0.5rem",
                "stack-md":       "1.5rem",
                "stack-xl":       "4rem",
                "gutter":         "24px",
                "margin-mobile":  "20px",
                "margin-desktop": "80px"
            },
            fontFamily: {
                "body-md":          ["Plus Jakarta Sans"],
                "body-lg":          ["Plus Jakarta Sans"],
                "headline-md":      ["Plus Jakarta Sans"],
                "label-caps":       ["Plus Jakarta Sans"],
                "display-lg":       ["Plus Jakarta Sans"],
                "display-lg-mobile":["Plus Jakarta Sans"]
            },
            fontSize: {
                "body-md":          ["16px", { lineHeight: "1.5",  fontWeight: "400" }],
                "body-lg":          ["18px", { lineHeight: "1.6",  fontWeight: "400" }],
                "headline-md":      ["24px", { lineHeight: "1.3",  fontWeight: "600" }],
                "label-caps":       ["12px", { lineHeight: "1",    letterSpacing: "0.1em",  fontWeight: "700" }],
                "display-lg":       ["48px", { lineHeight: "1.1",  letterSpacing: "-0.02em", fontWeight: "700" }],
                "display-lg-mobile":["32px", { lineHeight: "1.2",  letterSpacing: "-0.02em", fontWeight: "700" }]
            }
        }
    }
};
