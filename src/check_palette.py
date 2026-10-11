"""
Check the chart palette against the documented gates, in both themes.

The data-viz guidance is explicit that colourblind separation is computable and
should never be judged by eye. Its bundled validator was not available here, so
the gates are implemented directly:

  * adjacent-pair separation under simulated CVD  >= 8   (OKLab dE x100)
  * adjacent-pair separation for normal vision    >= 15  (hard floor)
  * each series colour against its own surface    >= 3:1 (WCAG contrast)

CVD simulation uses the Vienot, Brettel & Mollon (1999) dichromat projection in
linear LMS, which is the standard construction these thresholds assume.
"""
import itertools
import sys

# Series colours actually used by the charts, per theme, with the surface they
# are drawn on.
THEMES = {
    "light": {
        "surface": "#ffffff",
        "series": [("blue", "#256abf"), ("orange", "#eb6834"), ("green", "#036603")],
    },
    "dark": {
        "surface": "#161b22",
        "series": [("blue", "#3987e5"), ("orange", "#eb6834"), ("green", "#2fc48c")],
    },
}

CVD_TARGET = 8.0
NORMAL_FLOOR = 15.0
CONTRAST_FLOOR = 3.0


def hex_to_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))


def srgb_to_linear(c):
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def linear_to_srgb(c):
    c = max(0.0, min(1.0, c))
    return 12.92 * c if c <= 0.0031308 else 1.055 * (c ** (1 / 2.4)) - 0.055


def to_linear(rgb):
    return tuple(srgb_to_linear(c) for c in rgb)


def oklab(rgb_lin):
    r, g, b = rgb_lin
    l = 0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b
    m = 0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b
    s = 0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b
    l_, m_, s_ = l ** (1 / 3) if l > 0 else 0, m ** (1 / 3) if m > 0 else 0, \
        s ** (1 / 3) if s > 0 else 0
    return (
        0.2104542553 * l_ + 0.7936177850 * m_ - 0.0040720468 * s_,
        1.9779984951 * l_ - 2.4285922050 * m_ + 0.4505937099 * s_,
        0.0259040371 * l_ + 0.7827717662 * m_ - 0.8086757660 * s_,
    )


def delta_e(a, b):
    """OKLab Euclidean distance, x100, which is the scale the gates use."""
    la, aa, ba = oklab(a)
    lb, ab, bb = oklab(b)
    return 100 * ((la - lb) ** 2 + (aa - ab) ** 2 + (ba - bb) ** 2) ** 0.5


# Vienot/Brettel/Mollon dichromat simulation, on linear RGB.
def _rgb_to_lms(r, g, b):
    return (17.8824 * r + 43.5161 * g + 4.11935 * b,
            3.45565 * r + 27.1554 * g + 3.86714 * b,
            0.0299566 * r + 0.184309 * g + 1.46709 * b)


def _lms_to_rgb(l, m, s):
    return (0.0809444479 * l - 0.1305044090 * m + 0.1167211717 * s,
            -0.0102485335 * l + 0.0540193266 * m - 0.1136147082 * s,
            -0.0003652969 * l - 0.0041216147 * m + 0.6935115601 * s)


def simulate(rgb_lin, kind):
    l, m, s = _rgb_to_lms(*rgb_lin)
    if kind == "protanopia":
        l = 2.02344 * m - 2.52581 * s
    elif kind == "deuteranopia":
        m = 0.494207 * l + 1.24827 * s
    elif kind == "tritanopia":
        s = -0.395913 * l + 0.801109 * m
    r, g, b = _lms_to_rgb(l, m, s)
    return tuple(max(0.0, min(1.0, c)) for c in (r, g, b))


def rel_luminance(rgb_lin):
    r, g, b = rgb_lin
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a_lin, b_lin):
    la, lb = rel_luminance(a_lin), rel_luminance(b_lin)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def main():
    ok = True
    for theme, cfg in THEMES.items():
        surface = to_linear(hex_to_rgb(cfg["surface"]))
        series = [(n, to_linear(hex_to_rgb(h)), h) for n, h in cfg["series"]]
        print(f"\n=== {theme} (surface {cfg['surface']}) ===")

        print(" contrast against surface")
        for name, lin, hx in series:
            c = contrast(lin, surface)
            flag = "ok  " if c >= CONTRAST_FLOOR else "WARN"
            if c < CONTRAST_FLOOR:
                ok = False
            print(f"   {flag} {name:<7} {hx}  {c:.2f}:1")

        print(" pair separation (all pairs)")
        for (n1, c1, h1), (n2, c2, h2) in itertools.combinations(series, 2):
            normal = delta_e(c1, c2)
            sims = {k: delta_e(simulate(c1, k), simulate(c2, k))
                    for k in ("protanopia", "deuteranopia", "tritanopia")}
            worst_k = min(sims, key=sims.get)
            worst = sims[worst_k]
            bad = normal < NORMAL_FLOOR or worst < CVD_TARGET
            if bad:
                ok = False
            flag = "FAIL" if bad else "ok  "
            print(f"   {flag} {n1}/{n2:<7} normal {normal:5.1f}  "
                  f"worst CVD {worst:5.1f} ({worst_k})")

    print("\nPASS" if ok else "\nFAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
