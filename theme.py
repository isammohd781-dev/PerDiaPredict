"""PerdiaPredict visual system — the single stylesheet for every page.

Direction: a clinic intake form and a lab result slip. Cool neutral page, white
panels with one hairline border, solid buttons, no gradients, glows or shadows,
sentence-case labels. One spacing scale (4 / 8 / 12 / 16 / 24 / 32 px), fields 48px.
The result card is the one emphasised element.

All earlier styling layers were removed in favour of this file, so selectors
here do not have to fight each other with !important chains.
"""

PALETTES = {
    "light": {
        "page": "#F3F5F4", "surface": "#FFFFFF", "sunken": "#F7F9F8",
        "ink": "#1C2A33", "muted": "#5B6B75", "line": "#D4DBDF", "line_strong": "#B4BFC5",
        "primary": "#0F6B5C", "primary_hover": "#0B5549", "primary_ink": "#FFFFFF", "primary_soft": "#E3F0EC",
        "danger": "#B3261E", "danger_soft": "#FBECEA", "success": "#1E7B46", "success_soft": "#E7F4EC",
        "warn_ink": "#7A4300", "warn_soft": "#FFF4E2", "warn_line": "#EBC584",
        "info_ink": "#22475E", "info_soft": "#EAF2F7", "info_line": "#C3D6E2",
        "focus": "rgba(15,107,92,.30)", "avatar": "#DCE6E3", "avatar_ink": "#365049",
    },
    "dark": {
        "page": "#11181C", "surface": "#182227", "sunken": "#141C20",
        "ink": "#E3E9EC", "muted": "#9DADB5", "line": "#2B3940", "line_strong": "#40525B",
        "primary": "#4FB8A3", "primary_hover": "#6ACBB7", "primary_ink": "#0C1A17", "primary_soft": "#1B3430",
        "danger": "#F08A80", "danger_soft": "#3A1F1C", "success": "#6CCB93", "success_soft": "#17301F",
        "warn_ink": "#F5C77E", "warn_soft": "#33260F", "warn_line": "#6B4F1E",
        "info_ink": "#A9CDE3", "info_soft": "#172A35", "info_line": "#2C4A5C",
        "focus": "rgba(79,184,163,.38)", "avatar": "#24343A", "avatar_ink": "#A7C4BC",
    },
}

FONT = ('"Segoe UI", "Noto Sans", "Noto Sans Arabic", "Noto Sans Devanagari", '
        '"Microsoft YaHei", "PingFang SC", system-ui, -apple-system, sans-serif')


def css(dark: bool = False, rtl: bool = False) -> str:
    p = PALETTES["dark" if dark else "light"]
    tokens = "\n".join(f"  --pp-{k.replace('_', '-')}: {v};" for k, v in p.items())
    start, end = ("right", "left") if rtl else ("left", "right")
    direction = "rtl" if rtl else "ltr"
    sheet = f"""
:root {{
{tokens}
  --pp-font: {FONT};
  --pp-r-control: 8px;
  --pp-r-panel: 12px;
  --pp-field-h: 48px;
  /* Streamlit's fixed top bar. Page content starts below it so the first button is never cut off. */
  --pp-top-bar: 3.75rem;
  color-scheme: {"dark" if dark else "light"};
}}

/* ---------- Page ---------- */
html, body, .stApp, [data-testid="stAppViewContainer"] {{
  background: var(--pp-page) !important; color: var(--pp-ink);
  max-width: 100%; overflow-x: hidden;
}}
/* Font on text elements only: spans keep their own family so Streamlit's icon font is untouched */
.stApp, .stApp :is(p, li, label, input, textarea, button, select, h1, h2, h3, h4, [data-testid="stMarkdownContainer"]) {{ font-family: var(--pp-font); }}
.stApp :is(p, li, label, span) {{ color: var(--pp-ink); }}
.stApp {{ font-size: 16px; line-height: 1.6; }}
[data-testid="stMain"], [data-testid="stMainBlockContainer"] {{ background: transparent !important; }}
header[data-testid="stHeader"] {{ background: var(--pp-page) !important; box-shadow: none; height: var(--pp-top-bar) !important; min-height: var(--pp-top-bar) !important; }}
[data-testid="stDecoration"] {{ display: none !important; }}
.block-container, [data-testid="stMainBlockContainer"] {{
  max-width: 920px !important; padding: calc(var(--pp-top-bar) + 24px) 1.25rem 3rem !important;
}}
[data-testid="stMain"] [data-testid="stMarkdownContainer"] {{ direction: {direction}; text-align: {start}; }}
[data-testid="stVerticalBlock"] {{ gap: 16px; }}
/* Streamlit pulls every markdown block up by 1rem to cancel a paragraph margin. That made
   text sit almost on top of the next button. Remove both, so the 16px gap is real everywhere. */
.stApp [data-testid="stMarkdownContainer"] {{ margin-bottom: 0 !important; }}
.stApp [data-testid="stMarkdownContainer"] > :last-child, .stApp [data-testid="stMarkdownContainer"] > p:last-child {{ margin-bottom: 0 !important; }}
.stApp [data-testid="stMarkdownContainer"] p {{ margin: 0 0 8px; }}

/* Headings: sentence case, no tracking, one weight */
.stApp :is(h1, h2, h3, h4) {{
  font-family: var(--pp-font) !important; color: var(--pp-ink) !important;
  letter-spacing: 0 !important; text-transform: none !important; font-weight: 650 !important;
}}
.stApp h1 {{ font-size: 1.625rem !important; line-height: 1.25 !important; padding: 0 0 4px !important; }}
.stApp h2 {{ font-size: 1.3125rem !important; line-height: 1.3 !important; padding: 0 !important; }}
.stApp h3 {{ font-size: 1.125rem !important; line-height: 1.35 !important; padding: 0 !important; }}
.stApp [data-testid="stCaptionContainer"], .stApp [data-testid="stCaptionContainer"] p {{
  color: var(--pp-muted) !important; font-size: .875rem; line-height: 1.55;
}}
.stApp a {{ color: var(--pp-primary); text-underline-offset: 3px; }}
.stApp [data-testid="stMarkdownContainer"] hr, .stApp hr {{
  border: 0 !important; border-top: 1px solid var(--pp-line) !important; margin: 8px 0 !important; opacity: 1 !important;
}}

/* Invisible helper frames (Enter navigation, session timer) take no space in the layout */
.stApp [data-testid="stElementContainer"]:has(iframe[height="0"]) {{ position: absolute !important; width: 0 !important; height: 0 !important; margin: 0 !important; overflow: hidden !important; }}

/* ---------- Header bar ---------- */
[data-testid="stHorizontalBlock"]:has(.brand) {{
  background: var(--pp-surface); border: 1px solid var(--pp-line); border-radius: var(--pp-r-panel);
  padding: 10px 14px; gap: 12px !important; align-items: center !important; flex-wrap: nowrap !important;
  margin-bottom: 8px;
}}
[data-testid="stHorizontalBlock"]:has(.brand) > [data-testid="stColumn"]:nth-child(1) {{ flex: 1 1 auto !important; width: auto !important; min-width: 0 !important; }}
[data-testid="stHorizontalBlock"]:has(.brand) > [data-testid="stColumn"]:nth-child(2) {{ flex: 0 0 auto !important; width: auto !important; min-width: 120px !important; }}
[data-testid="stHorizontalBlock"]:has(.brand) > [data-testid="stColumn"]:nth-child(3) {{ flex: 0 0 44px !important; width: 44px !important; min-width: 44px !important; }}
.brand {{ display: flex; align-items: center; gap: 12px; min-width: 0; }}
.brand-icon {{ width: 40px; height: 40px; flex: 0 0 40px; border-radius: 10px; overflow: hidden;
  background: var(--pp-avatar); display: grid; place-items: center; color: var(--pp-avatar-ink); font-weight: 700; }}
.brand-icon img {{ width: 100%; height: 100%; object-fit: cover; }}
.brand-name {{ font-size: 1.0625rem; font-weight: 650; line-height: 1.25; color: var(--pp-ink) !important; }}
.brand-tagline {{ font-size: .8125rem; line-height: 1.35; color: var(--pp-muted) !important; }}

/* ---------- Panels (forms and grouped content) ---------- */
[data-testid="stForm"], .st-key-patient_card, .st-key-profile_editor [data-testid="stForm"],
.st-key-admin_menu, .st-key-care_connect_panel, [class*="st-key-care_connection_"], [class*="st-key-care_note_"],
div[data-testid="stVerticalBlockBorderWrapper"]:has(> div > [data-testid="stVerticalBlock"]) {{
  background: var(--pp-surface); border: 1px solid var(--pp-line) !important; border-radius: var(--pp-r-panel) !important;
  box-shadow: none !important;
}}
[data-testid="stForm"], .st-key-patient_card {{ padding: 24px !important; }}
.st-key-admin_menu, .st-key-care_connect_panel, [class*="st-key-care_connection_"], [class*="st-key-care_note_"] {{ padding: 16px 20px !important; }}

.section-title {{ font-size: 1.125rem; font-weight: 650; line-height: 1.35; color: var(--pp-ink) !important; margin: 0; }}
.section-subtitle {{ font-size: .875rem; line-height: 1.55; color: var(--pp-muted) !important; margin: 0; }}
.section-card {{ background: var(--pp-surface); border: 1px solid var(--pp-line); border-radius: var(--pp-r-panel); padding: 20px 24px; }}
/* Keep a heading's note attached to it rather than a full gap away */
[data-testid="stElementContainer"]:has(.section-title) + [data-testid="stElementContainer"]:has(:is([data-testid="stCaptionContainer"], .section-subtitle)),
[data-testid="stElementContainer"]:has(.section-subtitle) + [data-testid="stElementContainer"]:has([data-testid="stCaptionContainer"]) {{
  margin-top: -10px;
}}

/* ---------- Fields ---------- */
.stApp [data-testid="stWidgetLabel"] {{ min-height: 0 !important; margin: 0 0 6px !important; }}
.stApp [data-testid="stWidgetLabel"] p {{
  font-size: .875rem !important; font-weight: 600 !important; line-height: 1.4 !important; color: var(--pp-ink) !important;
}}
.stApp :is([data-testid="stTextInputRootElement"], [data-testid="stNumberInputContainer"], [data-testid="stTextAreaRootElement"],
           div[data-baseweb="select"] > div, [data-testid="stSelectbox"] [role="group"], [data-testid="stMultiSelect"] [role="group"]) {{
  background: var(--pp-surface) !important; border: 1px solid var(--pp-line-strong) !important;
  border-radius: var(--pp-r-control) !important; box-shadow: none !important; box-sizing: border-box !important;
  transition: border-color .12s ease, box-shadow .12s ease;
}}
.stApp :is([data-testid="stTextInputRootElement"], [data-testid="stNumberInputContainer"],
           div[data-baseweb="select"] > div, [data-testid="stSelectbox"] [role="group"]) {{ min-height: var(--pp-field-h) !important; }}
.stApp :is([data-testid="stTextInputRootElement"], [data-testid="stNumberInputContainer"], [data-testid="stTextAreaRootElement"]) [data-baseweb] {{
  background: transparent !important; border: 0 !important; box-shadow: none !important;
}}
.stApp div[data-baseweb="select"] > div * {{ background: transparent !important; }}
.stApp :is([data-testid="stTextInputRootElement"], [data-testid="stNumberInputContainer"], [data-testid="stTextAreaRootElement"],
           div[data-baseweb="select"] > div, [data-testid="stSelectbox"] [role="group"]):hover {{ border-color: var(--pp-muted) !important; }}
.stApp :is([data-testid="stTextInputRootElement"], [data-testid="stNumberInputContainer"], [data-testid="stTextAreaRootElement"],
           div[data-baseweb="select"] > div, [data-testid="stSelectbox"] [role="group"]):focus-within {{
  border-color: var(--pp-primary) !important; box-shadow: 0 0 0 3px var(--pp-focus) !important;
}}
.stApp :is(input, textarea) {{
  background: transparent !important; color: var(--pp-ink) !important; -webkit-text-fill-color: var(--pp-ink) !important;
  caret-color: var(--pp-primary); font-size: .9375rem !important; line-height: 1.5 !important;
}}
.stApp input {{ padding: 0 12px !important; text-align: {start}; }}
.stApp textarea {{ padding: 10px 12px !important; line-height: 1.6 !important; direction: {direction}; text-align: {start}; }}
.stApp input:is([type="email"], [type="password"], [type="number"], [type="tel"]) {{ direction: ltr; text-align: left; }}
.stApp :is(input, textarea)::placeholder {{ color: var(--pp-muted) !important; -webkit-text-fill-color: var(--pp-muted) !important; opacity: .85 !important; }}
.stApp input:-webkit-autofill {{ -webkit-box-shadow: 0 0 0 1000px var(--pp-surface) inset !important; -webkit-text-fill-color: var(--pp-ink) !important; }}
.stApp div[data-baseweb="select"] :is(div, span, input), .stApp [data-testid="stSelectbox"] [role="group"] :is(input, span) {{
  color: var(--pp-ink) !important; -webkit-text-fill-color: var(--pp-ink) !important;
}}
.stApp :is([data-testid="stSelectbox"], [data-testid="stNumberInputContainer"], [data-testid="stTextInputRootElement"]) button {{
  background: transparent !important; border: 0 !important; box-shadow: none !important; min-height: 0 !important;
  color: var(--pp-muted) !important; width: auto !important;
}}
.stApp [data-testid="stSelectbox"] [role="group"] {{ display: flex; align-items: center; padding: 0 !important; }}
.stApp [data-testid="stSelectbox"] [role="group"] input {{ flex: 1 1 0; min-width: 0; caret-color: transparent; }}
.stApp :is(svg) {{ color: inherit; }}

/* ---------- Buttons inside fields (password eye, number steppers, select arrow) ---------- */
/* Streamlit's "Press Enter to apply" hint sits on top of the text and the eye button */
.stApp [data-testid="InputInstructions"] {{ display: none !important; }}
.stApp :is([data-testid="stTextInputRootElement"], [data-testid="stNumberInputContainer"]) {{
  display: flex !important; align-items: stretch !important; overflow: hidden;
}}
.stApp :is([data-testid="stTextInputRootElement"], [data-testid="stNumberInputContainer"]) > div:first-child {{
  flex: 1 1 auto !important; min-width: 0 !important; height: auto !important;
}}
.stApp [data-testid="stTextInputRootElement"] [data-baseweb="base-input"] {{ display: flex !important; align-items: center !important; height: 100%; }}
.stApp :is([data-testid="stTextInputRootElement"], [data-testid="stNumberInputContainer"]) input {{ height: auto !important; min-height: calc(var(--pp-field-h) - 2px); }}
/* Password show / hide: a centred 36px square at the end of the field, on both sides in Arabic */
.stApp [data-testid="stTextInputRootElement"] button {{
  display: inline-flex !important; align-items: center !important; justify-content: center !important;
  flex: 0 0 36px !important; width: 36px !important; height: 36px !important; min-width: 36px !important;
  padding: 0 !important; margin: 0 6px !important; border-radius: 6px !important; align-self: center !important;
  color: var(--pp-muted) !important;
}}
.stApp [data-testid="stTextInputRootElement"] button:hover {{ background: var(--pp-sunken) !important; color: var(--pp-ink) !important; }}
.stApp [data-testid="stTextInputRootElement"] button svg {{ width: 20px !important; height: 20px !important; }}
.stApp [data-testid="stTextInputRootElement"] button:focus-visible {{ outline-offset: -2px !important; }}
/* Number field − / +: two equal full-height buttons with a hairline divider */
.stApp [data-testid="stNumberInputContainer"] > div:not(:first-child) {{
  display: flex !important; align-items: stretch !important; flex: 0 0 auto !important; height: auto !important;
}}
.stApp [data-testid="stNumberInputContainer"] button:is([data-testid="stNumberInputStepDown"], [data-testid="stNumberInputStepUp"]) {{
  display: inline-flex !important; align-items: center !important; justify-content: center !important;
  width: 44px !important; min-width: 44px !important; height: auto !important; align-self: stretch !important;
  padding: 0 !important; margin: 0 !important; border-radius: 0 !important;
  border-inline-start: 1px solid var(--pp-line) !important; color: var(--pp-ink) !important;
}}
.stApp [data-testid="stNumberInputContainer"] button:is([data-testid="stNumberInputStepDown"], [data-testid="stNumberInputStepUp"]):hover:not(:disabled) {{
  background: var(--pp-sunken) !important;
}}
.stApp [data-testid="stNumberInputContainer"] button:is([data-testid="stNumberInputStepDown"], [data-testid="stNumberInputStepUp"]):disabled {{ opacity: .4 !important; }}
.stApp [data-testid="stNumberInputContainer"] button svg {{ width: 16px !important; height: 16px !important; }}
.stApp [data-testid="stNumberInputContainer"] button:focus-visible {{ outline-offset: -2px !important; }}
/* Select: text and the arrow / clear icons share one centred row */
.stApp div[data-baseweb="select"] > div {{ display: flex !important; align-items: center !important; padding-inline: 4px 8px !important; }}
.stApp div[data-baseweb="select"] svg {{ flex: 0 0 auto; width: 20px; height: 20px; color: var(--pp-muted) !important; }}
/* The (?) help icon stays on the label's line */
.stApp [data-testid="stWidgetLabel"] {{ display: flex !important; align-items: center !important; gap: 6px; }}
.stApp [data-testid="stWidgetLabel"] [data-testid="stTooltipIcon"] {{ display: inline-flex; align-items: center; margin: 0 !important; }}
/* A button placed in a row beside fields matches the field height, so both line up */
.stApp [data-testid="stHorizontalBlock"]:has(:is(input, [data-baseweb="select"])) > [data-testid="stColumn"] [data-testid^="stBaseButton-"] {{
  min-height: var(--pp-field-h) !important;
}}
/* File picker: the Browse button sits centred in its drop area */
.stApp [data-testid="stFileUploaderDropzone"] {{
  display: flex; align-items: center; justify-content: space-between; gap: 12px; flex-wrap: wrap;
  border: 1px dashed var(--pp-line-strong) !important; border-radius: var(--pp-r-control) !important; background: var(--pp-sunken) !important;
}}
.stApp [data-testid="stFileUploaderDropzone"] [data-testid^="stBaseButton-"] {{ min-height: 40px; margin: 0 !important; }}

/* Dropdown menus */
div[data-baseweb="popover"] :is(ul, [role="listbox"]), [data-testid="stSelectboxVirtualDropdown"], [role="listbox"] {{
  background: var(--pp-surface) !important; border: 1px solid var(--pp-line) !important; border-radius: var(--pp-r-control);
}}
[role="option"], div[data-baseweb="popover"] li {{ background: var(--pp-surface) !important; color: var(--pp-ink) !important; }}
[role="option"] *, div[data-baseweb="popover"] li * {{ color: var(--pp-ink) !important; -webkit-text-fill-color: var(--pp-ink) !important; background: transparent !important; }}
[role="option"]:is(:hover, [aria-selected="true"], [data-focused]), div[data-baseweb="popover"] li:hover {{ background: var(--pp-primary-soft) !important; }}

/* Checkbox, radio, toggle */
.stApp [data-testid="stCheckbox"] label {{ align-items: flex-start; gap: 10px; }}
.stApp :is([data-testid="stCheckbox"], [data-testid="stRadio"]) [data-testid="stMarkdownContainer"] p {{ font-size: .9375rem; line-height: 1.55; margin: 0; }}

/* ---------- Buttons ---------- */
.stApp [data-testid^="stBaseButton-"] {{
  min-height: 44px; padding: 8px 18px !important; border-radius: var(--pp-r-control) !important;
  font-weight: 600 !important; box-shadow: none !important; transform: none !important;
  transition: background-color .12s ease, border-color .12s ease, color .12s ease;
}}
.stApp [data-testid^="stBaseButton-"] p {{ font-size: .9375rem !important; font-weight: 600 !important; line-height: 1.3 !important; margin: 0; }}
.stApp :is([data-testid="stBaseButton-secondary"], [data-testid="stBaseButton-secondaryFormSubmit"]) {{
  background: var(--pp-surface) !important; border: 1px solid var(--pp-line-strong) !important; color: var(--pp-ink) !important;
}}
.stApp :is([data-testid="stBaseButton-secondary"], [data-testid="stBaseButton-secondaryFormSubmit"]) :is(p, span) {{
  color: var(--pp-ink) !important; -webkit-text-fill-color: var(--pp-ink) !important;
}}
.stApp :is([data-testid="stBaseButton-secondary"], [data-testid="stBaseButton-secondaryFormSubmit"]):hover {{
  background: var(--pp-sunken) !important; border-color: var(--pp-muted) !important;
}}
.stApp :is([data-testid="stBaseButton-primary"], [data-testid="stBaseButton-primaryFormSubmit"]) {{
  background: var(--pp-primary) !important; border: 1px solid var(--pp-primary) !important; color: var(--pp-primary-ink) !important;
}}
.stApp :is([data-testid="stBaseButton-primary"], [data-testid="stBaseButton-primaryFormSubmit"]) :is(p, span) {{
  color: var(--pp-primary-ink) !important; -webkit-text-fill-color: var(--pp-primary-ink) !important;
}}
.stApp :is([data-testid="stBaseButton-primary"], [data-testid="stBaseButton-primaryFormSubmit"]):hover {{
  background: var(--pp-primary-hover) !important; border-color: var(--pp-primary-hover) !important;
}}
.stApp [data-testid^="stBaseButton-"]:disabled {{ opacity: .5 !important; cursor: not-allowed; }}
/* Permanent account deletion is the one red action */
.stApp .st-key-delete_account_actions [data-testid="stBaseButton-primaryFormSubmit"] {{
  background: var(--pp-danger) !important; border-color: var(--pp-danger) !important;
}}
.stApp .st-key-delete_account_actions [data-testid="stBaseButton-primaryFormSubmit"] :is(p, span) {{
  color: var(--pp-surface) !important; -webkit-text-fill-color: var(--pp-surface) !important;
}}
.stApp .st-key-delete_account_actions [data-testid="stBaseButton-primaryFormSubmit"]:hover {{ filter: brightness(.92); }}
.stApp .st-key-open_delete_account [data-testid^="stBaseButton-"] :is(p, span) {{ color: var(--pp-danger) !important; -webkit-text-fill-color: var(--pp-danger) !important; }}
.stApp :is(button, input, textarea, a, [role="radio"], [role="checkbox"]):focus-visible {{
  outline: 2px solid var(--pp-primary) !important; outline-offset: 2px !important;
}}
/* Text-style links inside the sign-in panel (Back, switch between sign in / create account) */
.stApp :is([class*="st-key-auth_link"], .st-key-gate_back) [data-testid^="stBaseButton-"] {{
  background: transparent !important; border-color: transparent !important; min-height: 36px; padding: 4px 8px !important;
}}
.stApp :is([class*="st-key-auth_link"], .st-key-gate_back) [data-testid^="stBaseButton-"] p {{ color: var(--pp-primary) !important; -webkit-text-fill-color: var(--pp-primary) !important; }}
.stApp :is([class*="st-key-auth_link"], .st-key-gate_back) [data-testid^="stBaseButton-"]:hover {{ background: var(--pp-primary-soft) !important; }}

/* ---------- Day / night button: same 44px icon square on every page ---------- */
.stApp [class*="st-key-pp_theme_"] {{ display: flex; flex-direction: row; justify-content: flex-end; width: 100%; }}
.stApp [class*="st-key-pp_theme_"] [data-testid="stElementContainer"], .stApp [class*="st-key-pp_theme_"] .stButton {{ width: auto !important; }}
.stApp [class*="st-key-pp_theme_"] [data-testid^="stBaseButton-"] {{
  width: 44px !important; min-width: 44px !important; height: 44px !important; min-height: 44px !important;
  padding: 0 !important; display: inline-grid !important; place-items: center !important;
  background: var(--pp-surface) !important; border: 1px solid var(--pp-line-strong) !important; color: var(--pp-ink) !important;
}}
.stApp [class*="st-key-pp_theme_"] [data-testid^="stBaseButton-"]:hover {{ background: var(--pp-sunken) !important; border-color: var(--pp-muted) !important; }}
.stApp [class*="st-key-pp_theme_"] [data-testid^="stBaseButton-"] :is(span, svg) {{ color: var(--pp-ink) !important; font-size: 20px !important; margin: 0 !important; }}
/* Sign-in card: product name on the left, day/night button on the right of the same row */
.stApp [data-testid="stHorizontalBlock"]:has(.auth-head) {{ flex-wrap: nowrap !important; align-items: center !important; gap: 12px !important; }}
.stApp [data-testid="stHorizontalBlock"]:has(.auth-head) > [data-testid="stColumn"]:first-child {{ flex: 1 1 auto !important; width: auto !important; min-width: 0 !important; }}
.stApp [data-testid="stHorizontalBlock"]:has(.auth-head) > [data-testid="stColumn"]:last-child {{ flex: 0 0 44px !important; width: 44px !important; min-width: 44px !important; }}
.auth-head {{ margin-bottom: 0; }}

/* ---------- Messages ---------- */
.stApp [data-testid="stAlertContainer"], .stApp [data-testid="stAlert"] > div {{ border-radius: var(--pp-r-control) !important; }}
.stApp [data-testid="stAlertContainer"]:has([data-testid="stAlertContentInfo"]) {{ background: var(--pp-info-soft) !important; border: 1px solid var(--pp-info-line); }}
.stApp [data-testid="stAlertContainer"]:has([data-testid="stAlertContentWarning"]) {{ background: var(--pp-warn-soft) !important; border: 1px solid var(--pp-warn-line); }}
.stApp [data-testid="stAlertContainer"]:has([data-testid="stAlertContentError"]) {{ background: var(--pp-danger-soft) !important; border: 1px solid var(--pp-danger); }}
.stApp [data-testid="stAlertContainer"]:has([data-testid="stAlertContentSuccess"]) {{ background: var(--pp-success-soft) !important; border: 1px solid var(--pp-success); }}
.stApp [data-testid="stAlertContainer"] :is(p, span) {{ color: var(--pp-ink) !important; }}
.status-card {{ display: block; padding: 12px 16px; border-radius: var(--pp-r-control); background: var(--pp-info-soft);
  border: 1px solid var(--pp-info-line); color: var(--pp-info-ink) !important; font-size: .875rem; line-height: 1.55; }}
.notice {{ padding: 14px 16px; border-radius: var(--pp-r-control); background: var(--pp-warn-soft); border: 1px solid var(--pp-warn-line);
  color: var(--pp-warn-ink) !important; font-size: .875rem; line-height: 1.65; }}
.notice * {{ color: var(--pp-warn-ink) !important; }}
.notice strong {{ display: block; margin-bottom: 4px; font-weight: 650; }}
.notice strong + br {{ display: none; }}

/* ---------- Other widgets ---------- */
.stApp [data-testid="stExpander"] {{ border: 1px solid var(--pp-line) !important; border-radius: var(--pp-r-panel) !important;
  background: var(--pp-surface) !important; overflow: hidden; }}
.stApp [data-testid="stExpander"] :is(details, summary) {{ background: transparent !important; border: 0 !important; }}
.stApp [data-testid="stExpander"] summary:hover {{ background: var(--pp-sunken) !important; }}
.stApp [data-testid="stExpander"] summary p {{ font-weight: 600; }}
.stApp [data-testid="stMetric"] {{ background: var(--pp-surface); border: 1px solid var(--pp-line); border-radius: var(--pp-r-panel); padding: 14px 16px; }}
.stApp [data-testid="stMetricLabel"] p {{ color: var(--pp-muted) !important; font-size: .875rem !important; }}
.stApp [data-testid="stMetricValue"] {{ color: var(--pp-ink) !important; font-size: 1.75rem !important; font-weight: 650; }}
.stApp [data-testid="stFileUploaderDropzone"] {{ background: var(--pp-sunken) !important; border: 1px dashed var(--pp-line-strong) !important; border-radius: var(--pp-r-control) !important; }}
.stApp [data-testid="stTabs"] [role="tab"] p {{ font-weight: 600; }}
.stApp [data-testid="stDataFrame"] {{ border: 1px solid var(--pp-line); border-radius: var(--pp-r-control); }}
.stApp [data-testid="stProgress"] [role="progressbar"] > div > div > div {{ background: var(--pp-primary) !important; }}
div[data-baseweb="tooltip"] > div, [data-testid="stTooltipContent"] {{ background: var(--pp-ink) !important; color: var(--pp-surface) !important; border-radius: 6px !important; }}
div[data-baseweb="tooltip"] *, [data-testid="stTooltipContent"] * {{ color: var(--pp-surface) !important; -webkit-text-fill-color: var(--pp-surface) !important; background: transparent !important; }}

/* Dialogs */
[data-testid="stDialog"] [role="dialog"] {{
  background: var(--pp-surface) !important; color: var(--pp-ink) !important; border: 1px solid var(--pp-line) !important;
  border-radius: var(--pp-r-panel) !important; padding: 24px !important; width: min(520px, calc(100vw - 32px)) !important;
  box-shadow: 0 12px 40px rgba(0,0,0,.18) !important;
}}
[data-testid="stDialog"] [role="dialog"] h2 {{ font-size: 1.25rem !important; padding-bottom: 8px !important; }}

/* ---------- Sign-in, registration ---------- */
.st-key-auth_card, .st-key-registration_card {{
  max-width: 460px; margin: 24px auto 0; background: var(--pp-surface);
  border: 1px solid var(--pp-line); border-radius: var(--pp-r-panel); padding: 32px 32px 24px !important;
}}
.st-key-registration_card {{ max-width: 720px; }}
.st-key-auth_right {{ gap: 16px; }}
.auth-head {{ display: flex; align-items: center; gap: 12px; margin-bottom: 4px; }}
.auth-head img, .auth-head .auth-logo-fallback {{ width: 44px; height: 44px; border-radius: 10px; object-fit: cover; flex: 0 0 44px;
  background: var(--pp-avatar); display: grid; place-items: center; font-weight: 700; color: var(--pp-avatar-ink); }}
.auth-head .auth-product {{ font-size: .9375rem; font-weight: 650; color: var(--pp-ink); line-height: 1.3; }}
.auth-head .auth-product span {{ display: block; font-size: .8125rem; font-weight: 400; color: var(--pp-muted); }}
.auth-form-title {{ font-size: 1.5rem; font-weight: 650; line-height: 1.3; color: var(--pp-ink) !important; margin: 8px 0 0; text-align: {start}; }}
.auth-form-sub {{ font-size: .9375rem; line-height: 1.55; color: var(--pp-muted) !important; margin: 4px 0 0; }}
.st-key-auth_right [data-testid="stForm"] {{ border: 0 !important; padding: 0 !important; background: transparent; }}
.st-key-auth_right [data-testid="stHorizontalBlock"] {{ gap: 16px !important; }}
/* Registration: numbered steps are a real sequence, so they keep their numbers */
.reg-section {{ display: flex; align-items: center; gap: 10px; border-top: 1px solid var(--pp-line); padding-top: 20px; margin-top: 12px; }}
.reg-section-first {{ border-top: 0; padding-top: 0; margin-top: 0; }}
.reg-step {{ display: inline-grid; place-items: center; width: 24px; height: 24px; border-radius: 50%; flex: 0 0 24px;
  background: var(--pp-primary-soft); color: var(--pp-primary); font-size: .75rem; font-weight: 700; }}
.reg-section-title {{ font-size: 1.0625rem; font-weight: 650; color: var(--pp-ink); }}
.reg-field-title {{ font-size: .875rem; font-weight: 600; line-height: 1.4; color: var(--pp-ink); margin: 0; }}
[data-testid="stElementContainer"]:has(.reg-field-title) {{ margin-bottom: -10px; }}
/* Day / month / year stay on one row, also on phones */
.stApp [data-testid="stHorizontalBlock"]:has(.st-key-reg_day) {{ flex-wrap: nowrap !important; gap: 8px !important; }}
.stApp [data-testid="stHorizontalBlock"]:has(.st-key-reg_day) > [data-testid="stColumn"] {{ flex: 1 1 0 !important; width: auto !important; min-width: 0 !important; }}
.support-card {{ border-top: 1px solid var(--pp-line); padding-top: 16px; margin-top: 4px; }}
.support-title {{ font-weight: 650; font-size: .9375rem; color: var(--pp-ink) !important; }}
.support-text {{ color: var(--pp-muted) !important; font-size: .875rem; line-height: 1.55; margin: 2px 0 10px; }}
.stApp a.support-link {{ display: inline-flex; align-items: center; gap: 6px; min-height: 40px; padding: 8px 14px;
  border: 1px solid var(--pp-line-strong); border-radius: var(--pp-r-control); color: var(--pp-ink) !important;
  text-decoration: none !important; font-weight: 600; font-size: .9375rem; }}
.stApp a.support-link:hover {{ background: var(--pp-sunken); }}
.policy-sentence {{ font-size: .8125rem; line-height: 1.6; color: var(--pp-muted) !important; text-align: center; margin: 8px 0 0; }}
.policy-sentence a {{ color: var(--pp-primary) !important; }}

/* ---------- Language gate (was a gradient hero) ---------- */
.hero {{ padding: 0 0 8px; }}
.hero h1 {{ font-size: 1.75rem !important; margin: 4px 0 6px !important; }}
.hero p {{ color: var(--pp-muted) !important; max-width: 62ch; margin: 0; }}
.pill {{ display: inline-block; margin-bottom: 4px; font-size: .8125rem; color: var(--pp-muted) !important; padding: 2px 10px;
  border: 1px solid var(--pp-line); border-radius: 999px; background: var(--pp-surface); }}

/* ---------- Patient profile summary ---------- */
.st-key-profile_summary {{ background: var(--pp-surface); border: 1px solid var(--pp-line); border-radius: var(--pp-r-panel); padding: 20px 24px; }}
.profile-avatar {{ width: 88px; height: 88px; border-radius: 50%; display: grid; place-items: center; overflow: hidden;
  background: var(--pp-avatar); color: var(--pp-avatar-ink); margin: 0 auto 12px; }}
.profile-avatar svg {{ width: 52px; height: 52px; }}
.profile-name-row {{ display: flex; flex-wrap: wrap; align-items: baseline; gap: 4px 12px; margin-bottom: 4px; }}
.profile-heading {{ font-size: 1.375rem !important; margin: 0 !important; padding: 0 !important; }}
.profile-id {{ font-size: .8125rem; color: var(--pp-muted) !important; unicode-bidi: isolate; }}
.profile-subtitle {{ color: var(--pp-muted) !important; font-size: .875rem; margin: 0 0 14px !important; }}
.profile-grid {{ display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px 24px; }}
.profile-detail {{ display: flex; flex-direction: column; gap: 2px; min-width: 0; }}
.profile-detail span {{ font-size: .8125rem; color: var(--pp-muted) !important; }}
.profile-detail strong {{ font-size: .9375rem; font-weight: 600; color: var(--pp-ink) !important; overflow-wrap: anywhere; unicode-bidi: plaintext; }}
/* Numbers, phone numbers and dates keep their own direction inside Arabic text */
.result-meta, .medical-field strong, .profile-id {{ unicode-bidi: plaintext; }}
.profile-edit-avatar {{ width: 104px; height: 104px; border-radius: 50%; object-fit: cover; display: block; margin: 8px auto;
  background: var(--pp-avatar); border: 1px solid var(--pp-line); }}
.profile-edit-description {{ color: var(--pp-muted) !important; margin: -8px 0 8px; }}
.st-key-profile_editor h3 {{ margin: 0 !important; }}

/* ---------- Screening result: the one emphasised element, styled as a lab slip ---------- */
.result-card {{ background: var(--pp-surface); border: 1px solid var(--pp-line); border-{start}: 4px solid var(--pp-line-strong);
  border-radius: var(--pp-r-panel); padding: 20px 24px; }}
.result-high {{ border-{start}-color: var(--pp-danger); }}
.result-low {{ border-{start}-color: var(--pp-success); }}
.result-label {{ font-size: .875rem; color: var(--pp-muted) !important; }}
.result-meta {{ font-size: .8125rem; color: var(--pp-muted) !important; margin-top: 2px; }}
.result-title {{ font-size: 1.25rem; font-weight: 650; margin: 10px 0 2px; color: var(--pp-ink) !important; }}
.result-high .result-title {{ color: var(--pp-danger) !important; }}
.result-low .result-title {{ color: var(--pp-success) !important; }}
.score {{ font-size: 3rem; font-weight: 650; line-height: 1.1; color: var(--pp-ink) !important; font-variant-numeric: tabular-nums; }}
.score-caption {{ font-size: .875rem; color: var(--pp-muted) !important; }}
.result-scale {{ position: relative; height: 8px; border-radius: 4px; background: var(--pp-sunken); border: 1px solid var(--pp-line); margin: 14px 0 12px; max-width: 420px; }}
.result-scale-fill {{ position: absolute; inset-block: 0; inset-inline-start: 0; border-radius: 4px; background: var(--pp-line-strong); }}
.result-high .result-scale-fill {{ background: var(--pp-danger); }}
.result-low .result-scale-fill {{ background: var(--pp-success); }}
.result-scale-mark {{ position: absolute; top: -5px; bottom: -5px; width: 2px; background: var(--pp-ink); }}

/* ---------- Medical report (on screen) ---------- */
.medical-report {{ background: var(--pp-surface); border: 1px solid var(--pp-line); border-radius: var(--pp-r-panel); padding: 24px; margin: 8px 0; }}
.medical-report h2 {{ display: flex; align-items: center; font-size: 1.25rem !important; margin: 0 !important; }}
.medical-report h2 + p {{ color: var(--pp-muted) !important; font-size: .875rem; margin: 2px 0 8px; padding-bottom: 12px; border-bottom: 1px solid var(--pp-line); }}
.medical-report h3 {{ font-size: 1rem !important; margin: 20px 0 8px !important; color: var(--pp-ink) !important; }}
.medical-report p {{ white-space: pre-wrap; overflow-wrap: anywhere; line-height: 1.65; }}
.medical-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 1px; background: var(--pp-line); border: 1px solid var(--pp-line); border-radius: var(--pp-r-control); overflow: hidden; }}
.medical-field {{ background: var(--pp-surface); padding: 10px 14px; }}
.medical-field span {{ display: block; font-size: .8125rem; color: var(--pp-muted) !important; margin-bottom: 2px; }}
.medical-field strong {{ display: block; font-weight: 600; color: var(--pp-ink) !important; overflow-wrap: anywhere; }}
.medical-result {{ font-size: 1.5rem; font-weight: 650; padding: 12px 16px; background: var(--pp-sunken); border-radius: var(--pp-r-control);
  display: flex; align-items: baseline; gap: 12px; flex-wrap: wrap; }}
.medical-result-label {{ font-size: 1rem; font-weight: 600; color: var(--pp-muted); }}
.medical-report[dir="rtl"], .medical-report[dir="rtl"] :is(h2, h3, p, .medical-field) {{ direction: rtl; text-align: right; }}
.medical-report[dir="ltr"], .medical-report[dir="ltr"] :is(h2, h3, p, .medical-field) {{ direction: ltr; text-align: left; }}

/* ---------- Admin / doctor page headings (were gradient banners) ---------- */
.admin-banner, .ux-hero {{ padding: 4px 0 8px; margin: 8px 0; border-bottom: 1px solid var(--pp-line); }}
.stApp .admin-banner :is(h1,h2,p), .stApp .ux-hero :is(h1, h2, p) {{ margin: 0 !important; }}
.admin-banner p, .ux-hero p {{ color: var(--pp-muted) !important; margin-top: 4px !important; }}
.admin-kicker {{ font-size: .8125rem; color: var(--pp-muted) !important; margin-bottom: 4px; }}
.st-key-admin_menu [data-testid="stRadio"] label {{ padding: 6px 0; }}

.footer {{ text-align: center; color: var(--pp-muted) !important; font-size: .8125rem; line-height: 1.6; padding: 24px 0 4px; }}

/* ---------- Small screens ---------- */
@media (max-width: 640px) {{
  .block-container, [data-testid="stMainBlockContainer"] {{ padding: calc(var(--pp-top-bar) + 12px) .75rem 2rem !important; }}
  [data-testid="stForm"], .st-key-patient_card {{ padding: 16px !important; }}
  .st-key-auth_card, .st-key-registration_card {{ padding: 20px 16px !important; margin-top: 8px; }}
  [data-testid="stHorizontalBlock"]:has(.brand) {{ padding: 8px 10px; }}
  .brand-tagline {{ display: none; }}
  .profile-grid {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
  .medical-grid {{ grid-template-columns: 1fr; }}
  .score {{ font-size: 2.5rem; }}
}}
@media (prefers-reduced-motion: reduce) {{ * {{ transition: none !important; animation: none !important; }} }}

/* ---------- Dialogs ----------
   Streamlit renders dialogs outside .stApp, so page rules did not reach them (dark text on a
   dark panel, white Cancel button in dark mode). Every page rule is applied to dialogs too. */
[data-testid="stDialog"] [role="dialog"] :is(p, li, label, span, [data-testid="stMarkdownContainer"]) {{ color: var(--pp-ink); font-family: var(--pp-font); }}
[data-testid="stDialog"] [role="dialog"] [data-testid="stVerticalBlockBorderWrapper"] {{
  background: var(--pp-sunken) !important; border: 1px solid var(--pp-line) !important; border-radius: var(--pp-r-control) !important;
}}
[data-testid="stDialog"] [role="dialog"] [data-testid="stVerticalBlockBorderWrapper"] strong {{ color: var(--pp-ink) !important; font-weight: 650; }}
[data-testid="stDialog"] [role="dialog"] button[aria-label="Close"] {{ color: var(--pp-muted) !important; }}
[data-testid="stDialog"] [role="dialog"] button[aria-label="Close"]:hover {{ color: var(--pp-ink) !important; background: var(--pp-sunken) !important; }}
"""
    # Apply every page rule to dialogs as well.
    return sheet.replace(".stApp ", ':is(.stApp, [data-testid="stDialog"]) ')


def inject(st):
    """Write the stylesheet once per render. Call before any page content."""
    dark = bool(st.session_state.get("dark_mode", False))
    lang = st.session_state.get("lang", "en")
    st.markdown("<style>" + css(dark, lang == "ar") + "</style>", unsafe_allow_html=True)


TOGGLE_HELP = {
    "en": ("Switch to dark mode", "Switch to light mode"), "ar": ("التبديل إلى الوضع الليلي", "التبديل إلى الوضع النهاري"),
    "fr": ("Passer en mode sombre", "Passer en mode clair"), "es": ("Cambiar a modo oscuro", "Cambiar a modo claro"),
    "de": ("Dunkelmodus", "Hellmodus"), "tr": ("Koyu moda geç", "Açık moda geç"),
    "hi": ("डार्क मोड पर जाएँ", "लाइट मोड पर जाएँ"), "pt": ("Mudar para modo escuro", "Mudar para modo claro"),
    "ru": ("Тёмная тема", "Светлая тема"), "zh": ("切换到深色模式", "切换到浅色模式"),
}


def _flip(st):
    dark = not st.session_state.get("dark_mode", False)
    st.session_state["dark_mode"] = dark
    try:
        st.query_params["theme"] = "dark" if dark else "light"
    except Exception:
        pass


def toggle_button(st, key):
    """The one day/night control used on every page: a 44px icon button with a tooltip."""
    dark = bool(st.session_state.get("dark_mode", False))
    to_dark, to_light = TOGGLE_HELP.get(st.session_state.get("lang"), TOGGLE_HELP["en"])
    with st.container(key="pp_theme_" + key):
        st.button("", key=key, icon=":material/light_mode:" if dark else ":material/dark_mode:",
                  help=to_light if dark else to_dark, on_click=_flip, args=(st,))
