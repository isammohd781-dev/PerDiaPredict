"""Artwork for the start (logo) screen: original vector drawings, no external images.

Icons of diabetes care items (glucose meter, insulin pen, blood drop, tablet, test strip, …)
shown inside floating glass tiles, and a glucose curve drawn across the background.
"""
import base64

_SYMBOLS = """
<symbol id="pp-meter" viewBox="0 0 120 190">
  <rect x="34" y="2" width="22" height="40" rx="3"/>
  <line x1="40" y1="12" x2="50" y2="12"/>
  <rect x="6" y="36" width="108" height="150" rx="22"/>
  <rect x="22" y="56" width="76" height="52" rx="8"/>
  <path d="M34 90 L48 90 L54 76 L62 98 L68 84 L86 84"/>
  <circle cx="40" cy="140" r="11"/>
  <circle cx="80" cy="140" r="11"/>
  <line x1="44" y1="168" x2="76" y2="168"/>
</symbol>
<symbol id="pp-pen" viewBox="0 0 300 60">
  <rect x="4" y="14" width="70" height="32" rx="10"/>
  <line x1="60" y1="14" x2="60" y2="46"/>
  <rect x="74" y="12" width="150" height="36" rx="8"/>
  <rect x="120" y="20" width="56" height="20" rx="4"/>
  <line x1="132" y1="20" x2="132" y2="40"/><line x1="144" y1="20" x2="144" y2="40"/>
  <line x1="156" y1="20" x2="156" y2="40"/><line x1="168" y1="20" x2="168" y2="40"/>
  <rect x="224" y="18" width="34" height="24" rx="6"/>
  <line x1="258" y1="30" x2="296" y2="30"/>
</symbol>
<symbol id="pp-syringe" viewBox="0 0 260 60">
  <line x1="4" y1="10" x2="4" y2="50"/>
  <line x1="4" y1="30" x2="44" y2="30"/>
  <line x1="44" y1="16" x2="44" y2="44"/>
  <rect x="44" y="18" width="150" height="24" rx="4"/>
  <line x1="74" y1="18" x2="74" y2="28"/><line x1="98" y1="18" x2="98" y2="28"/>
  <line x1="122" y1="18" x2="122" y2="28"/><line x1="146" y1="18" x2="146" y2="28"/>
  <line x1="170" y1="18" x2="170" y2="28"/>
  <path d="M194 22 L212 26 L212 34 L194 38"/>
  <line x1="212" y1="30" x2="256" y2="30"/>
</symbol>
<symbol id="pp-capsule" viewBox="0 0 120 50">
  <rect x="4" y="4" width="112" height="42" rx="21"/>
  <line x1="60" y1="4" x2="60" y2="46"/>
  <path d="M22 18 Q28 12 36 12"/>
</symbol>
<symbol id="pp-tablet" viewBox="0 0 70 70">
  <circle cx="35" cy="35" r="30"/>
  <line x1="14" y1="35" x2="56" y2="35"/>
</symbol>
<symbol id="pp-vial" viewBox="0 0 90 170">
  <rect x="8" y="4" width="74" height="30" rx="6"/>
  <line x1="20" y1="4" x2="20" y2="34"/><line x1="32" y1="4" x2="32" y2="34"/>
  <line x1="44" y1="4" x2="44" y2="34"/><line x1="56" y1="4" x2="56" y2="34"/><line x1="68" y1="4" x2="68" y2="34"/>
  <rect x="14" y="34" width="62" height="132" rx="10"/>
  <rect x="24" y="70" width="42" height="56" rx="4"/>
  <line x1="32" y1="86" x2="58" y2="86"/><line x1="32" y1="98" x2="58" y2="98"/><line x1="32" y1="110" x2="50" y2="110"/>
</symbol>
<symbol id="pp-strip" viewBox="0 0 40 150">
  <rect x="6" y="4" width="28" height="142" rx="4"/>
  <rect x="12" y="14" width="16" height="22" rx="3"/>
  <line x1="14" y1="120" x2="14" y2="146"/><line x1="20" y1="120" x2="20" y2="146"/><line x1="26" y1="120" x2="26" y2="146"/>
</symbol>
<symbol id="pp-lancet" viewBox="0 0 70 200">
  <rect x="22" y="2" width="26" height="22" rx="5"/>
  <rect x="10" y="24" width="50" height="130" rx="20"/>
  <line x1="22" y1="60" x2="48" y2="60"/><line x1="22" y1="72" x2="48" y2="72"/>
  <path d="M18 154 L52 154 L44 186 L26 186 Z"/>
  <line x1="35" y1="186" x2="35" y2="198"/>
</symbol>
<symbol id="pp-drop" viewBox="0 0 60 80">
  <path d="M30 4 C30 4 6 34 6 52 A24 24 0 0 0 54 52 C54 34 30 4 30 4 Z"/>
  <path d="M18 54 A12 12 0 0 0 28 66"/>
</symbol>
<symbol id="pp-trend" viewBox="0 0 260 110">
  <polyline points="4,96 4,4"/><polyline points="4,106 256,106"/>
  <polyline points="16,78 52,62 86,70 120,38 156,48 190,24 226,34 250,20"/>
  <circle cx="120" cy="38" r="4"/><circle cx="190" cy="24" r="4"/>
  <line x1="16" y1="50" x2="250" y2="50" stroke-dasharray="6 8"/>
</symbol>
"""



def _uri(svg: str) -> str:
    return "data:image/svg+xml;base64," + base64.b64encode(svg.encode("utf-8")).decode("ascii")


def icon_uri(name: str, color: str) -> str:
    """One care icon as a standalone image."""
    start = _SYMBOLS.index(f'<symbol id="pp-{name}"')
    symbol = _SYMBOLS[start:_SYMBOLS.index("</symbol>", start)]
    view = symbol.split('viewBox="', 1)[1].split('"', 1)[0]
    body = symbol.split(">", 1)[1]
    return _uri(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{view}" fill="none" stroke="{color}" '
                f'stroke-width="4" stroke-linecap="round" stroke-linejoin="round">{body}</svg>')


def wave_uri(color_a: str, color_b: str) -> str:
    """Two smooth glucose curves with a target band, spanning the screen."""
    return _uri(
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 380 1440 400" preserveAspectRatio="none">'
        '<defs><linearGradient id="g" x1="0" x2="1" y1="0" y2="0">'
        f'<stop offset="0" stop-color="{color_a}" stop-opacity="0"/><stop offset=".25" stop-color="{color_a}"/>'
        f'<stop offset=".75" stop-color="{color_b}"/><stop offset="1" stop-color="{color_b}" stop-opacity="0"/>'
        '</linearGradient></defs>'
        '<path d="M0 640 C 160 600, 240 520, 380 560 S 600 700, 760 600 S 1000 430, 1140 520 S 1340 620, 1440 560" '
        'fill="none" stroke="url(#g)" stroke-width="3" opacity=".9"/>'
        '<path d="M0 700 C 200 680, 300 620, 460 650 S 700 740, 880 670 S 1120 560, 1260 610 S 1400 660, 1440 640" '
        'fill="none" stroke="url(#g)" stroke-width="1.5" opacity=".45"/>'
        '</svg>')
