"""
Guard against the classic unreadable-artifact bug: a colour whose only
definition lives inside a media query or a [data-theme] block, so it resolves
to nothing in the un-stamped default state.

Every custom property referenced anywhere must be declared in the bare :root
block, and every property redefined for dark must also exist there.
"""
import re
import sys
import os

HERE = os.path.dirname(os.path.abspath(__file__))
INDEX = os.path.join(HERE, "..", "site", "index.html")

html = open(INDEX, encoding="utf-8").read()
styles = "\n".join(re.findall(r"<style>(.*?)</style>", html, re.S))

# The bare :root block is the first one, before any media/attribute scope.
m = re.search(r":root\s*\{(.*?)\}", styles, re.S)
if not m:
    sys.exit("no bare :root block found")
base = set(re.findall(r"(--[\w-]+)\s*:", m.group(1)))

used = set(re.findall(r"var\((--[\w-]+)", styles))
used |= set(re.findall(r'"(--[\w-]+)"', html))          # read from JS by name
used |= set(re.findall(r"var\((--[\w-]+)", html))        # inline style attributes

# A property that is only ever read with a fallback -- var(--cell, 6px) -- is a
# layout knob set on an element, not a theme token, and needs no :root default.
with_fallback = set(re.findall(r"var\((--[\w-]+)\s*,", styles))
with_fallback |= set(re.findall(r"var\((--[\w-]+)\s*,", html))
no_fallback = set(re.findall(r"var\((--[\w-]+)\s*\)", styles))
no_fallback |= set(re.findall(r"var\((--[\w-]+)\s*\)", html))
used -= (with_fallback - no_fallback)

# Layout knobs scoped to individual elements (set by a component rule or inline
# by the chart code), never inherited from :root and never theme-dependent.
ELEMENT_SCOPED = {"--cell", "--cell-gap"}
used -= ELEMENT_SCOPED

dark_blocks = re.findall(r'@media \(prefers-color-scheme: dark\).*?\{(.*?)\n\s*\}\n\s*\}',
                         styles, re.S)
dark_blocks += re.findall(r':root\[data-theme="dark"\]\s*\{(.*?)\}', styles, re.S)
dark = set()
for b in dark_blocks:
    dark |= set(re.findall(r"(--[\w-]+)\s*:", b))

missing = sorted(used - base)
dark_only = sorted(dark - base)

print(f"declared in bare :root : {len(base)}")
print(f"referenced anywhere    : {len(used)}")
print(f"redefined for dark     : {len(dark)}")

ok = True
if missing:
    ok = False
    print("\nREFERENCED BUT NEVER DECLARED IN :root")
    for v in missing:
        print("   ", v)
if dark_only:
    ok = False
    print("\nDEFINED ONLY IN A DARK SCOPE (will be empty in the default state)")
    for v in dark_only:
        print("   ", v)

unused = sorted(base - used)
if unused:
    print("\ndeclared but unused:", ", ".join(unused))

not_darkened = sorted(v for v in base
                      if v in used and v not in dark and v.startswith(
                          ("--paper", "--surface", "--rule", "--ink", "--accent", "--s", "--d-")))
if not_darkened:
    print("\nno dark override (check this is deliberate):", ", ".join(not_darkened))

print("\nOK" if ok else "\nFAIL")
sys.exit(0 if ok else 1)
