"""
apply_blue_ui_v2.py  -  تحديث التصميم: مسافات ونصوص مرتبة + صورة شفافة خلف الشعار.

الاستخدام (ضعه بجانب diabetes_app.py ثم شغّله):
    python apply_blue_ui_v2.py

- يحفظ نسخة احتياطية: diabetes_app.py.bak2
- يستبدل دالة inject_auth_css() فقط ولا يلمس أي شيء آخر.
"""
import shutil
import sys

APP_FILE = "diabetes_app.py"

NEW_FUNC = r'''def inject_auth_css():
    is_dark = st.session_state.get("dark_mode", True)
    rtl = is_rtl()
    no_spacing = rtl or st.session_state.get("lang", "en") in SPACING_OFF_LANGS
    letter = "0" if no_spacing else "-.02em"
    text_side = "right" if rtl else "left"

    # The form half sits on the right; in right-to-left languages it flips.
    form_side = "left" if rtl else "right"

    if is_dark:
        backdrop = """
            radial-gradient(900px 520px at 12% -8%, rgba(37,99,235,.38), transparent 60%),
            radial-gradient(800px 520px at 100% 105%, rgba(14,165,233,.28), transparent 60%),
            #060b18
        """
        card_shadow = "0 30px 80px rgba(0,0,0,.55), 0 0 0 1px rgba(148,163,184,.10)"
    else:
        backdrop = """
            radial-gradient(900px 520px at 12% -8%, rgba(37,99,235,.20), transparent 60%),
            radial-gradient(800px 520px at 100% 105%, rgba(14,165,233,.18), transparent 60%),
            #e9f1fb
        """
        card_shadow = "0 30px 70px rgba(30,64,175,.22), 0 0 0 1px rgba(148,163,184,.25)"

    # ------------------------------------------------------------------
    # Artwork behind the logo (transparent, so the blue panel shows through).
    #   * default: a built-in medical illustration (glow, heartbeat line,
    #     drops, crosses) + a slowly turning orbit ring;
    #   * your own picture: save it next to this file as auth_art.png
    #     (or .webp / .jpg / .svg) and it is used instead of the default.
    # ------------------------------------------------------------------
    art_svg = (
        "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 460 460'>"
        "<defs>"
        "<radialGradient id='g' cx='50%' cy='50%' r='50%'>"
        "<stop offset='0' stop-color='#38bdf8' stop-opacity='.55'/>"
        "<stop offset='.6' stop-color='#2563eb' stop-opacity='.22'/>"
        "<stop offset='1' stop-color='#2563eb' stop-opacity='0'/>"
        "</radialGradient>"
        "<linearGradient id='l' x1='0' x2='1' y1='0' y2='0'>"
        "<stop offset='0' stop-color='#7dd3fc' stop-opacity='0'/>"
        "<stop offset='.22' stop-color='#7dd3fc' stop-opacity='.9'/>"
        "<stop offset='.78' stop-color='#7dd3fc' stop-opacity='.9'/>"
        "<stop offset='1' stop-color='#7dd3fc' stop-opacity='0'/>"
        "</linearGradient>"
        "</defs>"
        "<circle cx='230' cy='230' r='228' fill='url(#g)'/>"
        "<circle cx='230' cy='230' r='172' fill='none' stroke='#fff' stroke-opacity='.14'/>"
        "<path d='M6 238 H70 l10 -16 l12 34 l14 -70 l12 52 l9 -14 H310 l9 14 l12 -52 l14 70 l12 -34 l10 16 H454' "
        "fill='none' stroke='url(#l)' stroke-width='2.6' stroke-linecap='round' stroke-linejoin='round'/>"
        "<g fill='#fff' fill-opacity='.30'>"
        "<path transform='translate(74 116)' d='M0 -16 C9 -3 13 3 13 9 A13 13 0 0 1 -13 9 C-13 3 -9 -3 0 -16Z'/>"
        "<path transform='translate(392 104) scale(.8)' d='M0 -16 C9 -3 13 3 13 9 A13 13 0 0 1 -13 9 C-13 3 -9 -3 0 -16Z'/>"
        "<path transform='translate(380 356) scale(1.1)' d='M0 -16 C9 -3 13 3 13 9 A13 13 0 0 1 -13 9 C-13 3 -9 -3 0 -16Z'/>"
        "<path transform='translate(84 346) scale(.7)' d='M0 -16 C9 -3 13 3 13 9 A13 13 0 0 1 -13 9 C-13 3 -9 -3 0 -16Z'/>"
        "</g>"
        "<g stroke='#fff' stroke-opacity='.38' stroke-width='2' stroke-linecap='round'>"
        "<path d='M405 196h12M411 190v12'/>"
        "<path d='M40 190h10M45 185v10'/>"
        "<path d='M330 60h10M335 55v10'/>"
        "<path d='M120 410h10M125 405v10'/>"
        "</g>"
        "<g fill='#fff' fill-opacity='.26'>"
        "<circle cx='150' cy='70' r='2.5'/><circle cx='300' cy='400' r='2.5'/>"
        "<circle cx='430' cy='300' r='2'/><circle cx='30' cy='280' r='2'/>"
        "</g>"
        "</svg>"
    )
    orbit_svg = (
        "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 460 460'>"
        "<circle cx='230' cy='230' r='205' fill='none' stroke='#fff' stroke-opacity='.24' stroke-dasharray='3 9'/>"
        "<circle cx='435' cy='230' r='6' fill='#7dd3fc' fill-opacity='.95'/>"
        "<circle cx='127.5' cy='407.5' r='4' fill='#fff' fill-opacity='.7'/>"
        "<circle cx='127.5' cy='52.5' r='5' fill='#38bdf8' fill-opacity='.9'/>"
        "</svg>"
    )

    def _data_uri(mime, raw_bytes):
        return f"data:{mime};base64," + base64.b64encode(raw_bytes).decode()

    art_uri = _data_uri("image/svg+xml", art_svg.encode("utf-8"))
    orbit_uri = _data_uri("image/svg+xml", orbit_svg.encode("utf-8"))

    art_mask = ""
    for _fname, _mime in (
        ("auth_art.png", "image/png"),
        ("auth_art.webp", "image/webp"),
        ("auth_art.jpg", "image/jpeg"),
        ("auth_art.jpeg", "image/jpeg"),
        ("auth_art.svg", "image/svg+xml"),
    ):
        _found = None
        for _dir in (BASE_DIR, "."):
            _p = os.path.join(_dir, _fname)
            if os.path.exists(_p):
                _found = _p
                break
        if _found:
            try:
                with open(_found, "rb") as _f:
                    art_uri = _data_uri(_mime, _f.read())
                # fade the edges of a personal picture so it blends in
                art_mask = (
                    "opacity:.55;"
                    "-webkit-mask-image:radial-gradient(circle, #000 50%, transparent 72%);"
                    "mask-image:radial-gradient(circle, #000 50%, transparent 72%);"
                )
                break
            except Exception:
                pass

    st.markdown(
        f"""
        <style>
        /* ---------- page: blue backdrop ---------- */
        .stApp {{
            background: {backdrop} !important;
        }}
        header[data-testid="stHeader"] {{
            background: transparent !important;
        }}
        .block-container {{
            max-width: 1000px !important;
            padding-top: 3.4rem !important;
        }}

        /* ---------- the card ---------- */
        .st-key-auth_card {{
            border-radius: 28px;
            overflow: hidden;
            padding: 0 !important;
            border: 0 !important;
            box-shadow: {card_shadow};
            background:
                linear-gradient(var(--surface), var(--surface)) {form_side} top / 50% 100% no-repeat,
                linear-gradient(rgba(255,255,255,.05) 1px, transparent 1px) 0 0 / 100% 38px repeat-y,
                linear-gradient(90deg, rgba(255,255,255,.05) 1px, transparent 1px) 0 0 / 38px 100% repeat-x,
                radial-gradient(circle at 14% 8%, rgba(96,165,250,.45), transparent 42%),
                radial-gradient(circle at 46% 100%, rgba(14,165,233,.40), transparent 46%),
                linear-gradient(135deg, #020617 0%, #172554 55%, #075985 100%);
            animation: authRise .55s cubic-bezier(.2,.8,.2,1) both;
        }}
        @keyframes authRise {{
            from {{ opacity: 0; transform: translateY(14px); }}
            to   {{ opacity: 1; transform: none; }}
        }}
        @keyframes authOrbit {{
            to {{ transform: rotate(360deg); }}
        }}
        @media (prefers-reduced-motion: reduce) {{
            .st-key-auth_card {{ animation: none; }}
            .auth-logo-circle::after {{ animation: none !important; }}
        }}

        [data-testid="stHorizontalBlock"]:has(.st-key-auth_left) {{
            gap: 0 !important;
        }}

        @media (min-width: 641px) {{
            [data-testid="stHorizontalBlock"]:has(.st-key-auth_left) {{
                flex-wrap: nowrap !important;
                align-items: stretch !important;
            }}
            [data-testid="stHorizontalBlock"]:has(.st-key-auth_left) > [data-testid="stColumn"] {{
                flex: 1 1 0 !important;
                width: 50% !important;
                min-width: 0 !important;
            }}
            /* two-column rows inside the form (first/last name, Back/Sign up ...)
               stay side by side */
            .st-key-auth_right [data-testid="stHorizontalBlock"] {{
                flex-wrap: nowrap !important;
                gap: .8rem !important;
            }}
            .st-key-auth_right [data-testid="stHorizontalBlock"] > [data-testid="stColumn"] {{
                flex: 1 1 0 !important;
                min-width: 0 !important;
            }}
        }}

        /* ---------- welcome panel (blue) ---------- */
        .st-key-auth_left {{
            min-height: 600px;
            padding: 48px 36px;
            justify-content: center;
            align-items: center;
            text-align: center;
        }}
        .st-key-auth_left [data-testid="stMarkdownContainer"] {{
            width: 100%;
        }}
        .st-key-auth_left [data-testid="stMarkdownContainer"] p {{
            margin: 0 !important;
        }}
        .stApp .st-key-auth_left,
        .stApp .st-key-auth_left * {{
            color: #ffffff !important;
            -webkit-text-fill-color: #ffffff !important;
        }}
        .auth-welcome {{
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            text-align: center;
            width: 100%;
        }}
        .auth-pill {{
            display: inline-flex;
            align-items: center;
            gap: 8px;
            padding: 8px 16px;
            margin: 0 0 22px;
            border-radius: 999px;
            background: rgba(255,255,255,.10);
            border: 1px solid rgba(255,255,255,.22);
            backdrop-filter: blur(6px);
            font-size: .8rem;
            font-weight: 650;
            line-height: 1.2;
        }}
        .auth-welcome-title {{
            font-size: 2.35rem;
            font-weight: 800;
            line-height: 1.15;
            letter-spacing: {letter};
            text-align: center;
            margin: 0 0 14px;
        }}
        .auth-welcome-sub {{
            font-size: .97rem;
            line-height: 1.7;
            text-align: center;
            opacity: .9;
            max-width: 330px;
            margin: 0 auto 64px;
        }}

        /* ---------- logo + artwork behind it ---------- */
        .auth-logo-circle {{
            position: relative;
            isolation: isolate;
            width: 176px;
            height: 176px;
            flex: 0 0 176px;
            border-radius: 50%;
            overflow: visible;
            display: flex;
            align-items: center;
            justify-content: center;
            background: linear-gradient(135deg, #2563eb, #0ea5e9);
            border: 3px solid rgba(255,255,255,.45);
            box-shadow:
                0 0 0 12px rgba(255,255,255,.07),
                0 0 0 26px rgba(255,255,255,.04),
                0 0 60px rgba(56,189,248,.45),
                0 26px 60px rgba(2,6,23,.55);
        }}
        .auth-logo-circle::before,
        .auth-logo-circle::after {{
            content: "";
            position: absolute;
            inset: -140px;
            z-index: -1;
            pointer-events: none;
            background-position: center;
            background-repeat: no-repeat;
            background-size: contain;
        }}
        .auth-logo-circle::before {{
            background-image: url("{art_uri}");
            {art_mask}
        }}
        .auth-logo-circle::after {{
            background-image: url("{orbit_uri}");
            animation: authOrbit 90s linear infinite;
        }}
        .auth-logo-circle img {{
            width: 100%;
            height: 100%;
            object-fit: cover;   /* use "contain" if your logo gets cropped */
            border-radius: 50%;
        }}
        .auth-logo-fallback {{ font-size: 80px; }}

        /* ---------- form panel ---------- */
        .st-key-auth_right {{
            min-height: 600px;
            padding: 48px 46px 32px;
            justify-content: center;
            gap: 1rem !important;
        }}
        .st-key-auth_right [data-testid="stMarkdownContainer"] p {{
            margin: 0;
        }}
        .auth-form-title {{
            font-size: 1.7rem;
            font-weight: 800;
            letter-spacing: {letter};
            line-height: 1.25;
            margin: 0 0 20px;
            color: var(--text) !important;
            text-align: {text_side};
        }}
        .auth-form-sub {{
            font-size: .92rem;
            line-height: 1.6;
            margin: 0 0 6px;
            color: var(--muted) !important;
            text-align: {text_side};
        }}
        .auth-form-title:has(+ .auth-form-sub) {{
            margin-bottom: 6px;
        }}
        .auth-sep {{
            height: 1px;
            background: var(--border);
            margin: .4rem 0;
        }}

        /* the form itself: no extra frame inside the card */
        .st-key-auth_right [data-testid="stForm"] {{
            border: 0 !important;
            padding: 0 !important;
            box-shadow: none !important;
            background: transparent !important;
        }}
        .st-key-auth_right [data-testid="stForm"] [data-testid="stVerticalBlock"] {{
            gap: .9rem !important;
        }}

        /* ---------- inputs ---------- */
        .stApp .st-key-auth_right div[data-baseweb="input"],
        .stApp .st-key-auth_right div[data-baseweb="select"],
        .stApp .st-key-auth_right [data-testid="stTextInputRootElement"] {{
            min-height: 50px;
            border-radius: 14px !important;
        }}
        .stApp .st-key-auth_right input {{
            font-size: .95rem !important;
            padding-top: 12px !important;
            padding-bottom: 12px !important;
        }}
        .stApp .st-key-auth_right div[data-baseweb="input"]:focus-within,
        .stApp .st-key-auth_right [data-testid="stTextInputRootElement"]:focus-within,
        .stApp .st-key-auth_right div[data-baseweb="select"]:focus-within {{
            border-color: #2563eb !important;
            box-shadow: 0 0 0 4px rgba(37,99,235,.20) !important;
        }}

        /* ---------- buttons ---------- */
        .stApp .st-key-auth_right button[kind="primary"],
        .stApp .st-key-auth_right [data-testid="stBaseButton-primary"],
        .stApp .st-key-auth_right [data-testid="stBaseButton-primaryFormSubmit"] {{
            min-height: 52px !important;
            border-radius: 14px !important;
            border: 0 !important;
            background: linear-gradient(135deg, #2563eb 0%, #0ea5e9 100%) !important;
            box-shadow: 0 10px 26px rgba(37,99,235,.38) !important;
            transition: transform .15s ease, box-shadow .15s ease, filter .15s ease;
        }}
        .stApp .st-key-auth_right button[kind="primary"]:hover,
        .stApp .st-key-auth_right [data-testid="stBaseButton-primary"]:hover,
        .stApp .st-key-auth_right [data-testid="stBaseButton-primaryFormSubmit"]:hover {{
            transform: translateY(-1px);
            filter: brightness(1.06);
            box-shadow: 0 14px 32px rgba(37,99,235,.48) !important;
        }}
        .stApp .st-key-auth_right button[kind="primary"] p,
        .stApp .st-key-auth_right [data-testid="stBaseButton-primary"] p,
        .stApp .st-key-auth_right [data-testid="stBaseButton-primaryFormSubmit"] p {{
            color: #ffffff !important;
            -webkit-text-fill-color: #ffffff !important;
            font-weight: 750 !important;
            text-decoration: none !important;
        }}

        .stApp .st-key-auth_right button[kind="secondary"],
        .stApp .st-key-auth_right [data-testid="stBaseButton-secondary"] {{
            min-height: 52px !important;
            border-radius: 14px !important;
            background: rgba(37,99,235,.07) !important;
            border: 1px solid rgba(96,165,250,.45) !important;
            box-shadow: none !important;
            transition: background .15s ease, border-color .15s ease, transform .15s ease;
        }}
        .stApp .st-key-auth_right button[kind="secondary"]:hover,
        .stApp .st-key-auth_right [data-testid="stBaseButton-secondary"]:hover {{
            background: rgba(37,99,235,.15) !important;
            border-color: #3b82f6 !important;
            transform: translateY(-1px);
        }}
        .stApp .st-key-auth_right button[kind="secondary"] p,
        .stApp .st-key-auth_right [data-testid="stBaseButton-secondary"] p {{
            color: var(--text) !important;
            -webkit-text-fill-color: var(--text) !important;
            font-weight: 700 !important;
            text-decoration: none !important;
        }}

        /* quiet text links: Back / Admin Panel (grey) and switch-page (blue).
           Written after the secondary rules so they win. */
        .stApp .st-key-auth_right [class*="st-key-auth_link"] button,
        .stApp .st-key-auth_right [class*="st-key-auth_swap"] button,
        .stApp .st-key-auth_right [class*="st-key-auth_"][class*="admin"] button {{
            background: transparent !important;
            border: 0 !important;
            box-shadow: none !important;
            transform: none !important;
            min-height: 38px !important;
            width: auto !important;
            padding: 0 12px !important;
        }}
        .stApp .st-key-auth_right [class*="st-key-auth_link"] button p,
        .stApp .st-key-auth_right [class*="st-key-auth_swap"] button p,
        .stApp .st-key-auth_right [class*="st-key-auth_"][class*="admin"] button p {{
            text-decoration: none !important;
            font-size: .9rem !important;
        }}
        .stApp .st-key-auth_right [class*="st-key-auth_link"] button p,
        .stApp .st-key-auth_right [class*="st-key-auth_"][class*="admin"] button p {{
            color: var(--muted) !important;
            -webkit-text-fill-color: var(--muted) !important;
            font-weight: 650 !important;
        }}
        .stApp .st-key-auth_right [class*="st-key-auth_swap"]:not([class*="admin"]) button p {{
            color: #60a5fa !important;
            -webkit-text-fill-color: #60a5fa !important;
            font-weight: 750 !important;
        }}
        .stApp .st-key-auth_right [class*="st-key-auth_link"] button:hover,
        .stApp .st-key-auth_right [class*="st-key-auth_swap"] button:hover,
        .stApp .st-key-auth_right [class*="st-key-auth_"][class*="admin"] button:hover {{
            background: rgba(37,99,235,.10) !important;
            border-radius: 10px !important;
        }}
        .stApp .st-key-auth_right [class*="st-key-auth_link"] button:hover p,
        .stApp .st-key-auth_right [class*="st-key-auth_"][class*="admin"] button:hover p {{
            color: var(--text) !important;
            -webkit-text-fill-color: var(--text) !important;
        }}

        /* links placed alone on a row (choice page): centred, with a little air above.
           Links inside a two-column row: Back at the start, switch-page at the end. */
        .st-key-auth_right > [class*="st-key-auth_link"],
        .st-key-auth_right > [class*="st-key-auth_"][class*="admin"] {{
            display: flex;
            justify-content: center;
        }}
        .st-key-auth_right > [class*="st-key-auth_"][class*="admin"] {{
            margin-top: .5rem;
        }}
        .st-key-auth_right [data-testid="stColumn"] [class*="st-key-auth_link"] {{
            display: flex; justify-content: flex-start;
        }}
        .st-key-auth_right [data-testid="stColumn"] [class*="st-key-auth_swap"] {{
            display: flex; justify-content: flex-end;
        }}

        .st-key-auth_right .support-card {{
            background: transparent !important;
            box-shadow: none !important;
            border: 0 !important;
            border-top: 1px solid var(--border) !important;
            border-radius: 0 !important;
            padding: 16px 0 4px !important;
            margin: 8px 0 0 !important;
            text-align: center !important;
        }}

        /* ---------- phones: welcome panel on top, form below ---------- */
        @media (max-width: 640px) {{
            .block-container {{ padding: 1.4rem .6rem 2rem !important; }}
            .st-key-auth_card {{ background: var(--surface) !important; border-radius: 22px; }}
            .st-key-auth_left {{
                min-height: 0;
                padding: 30px 18px;
                background:
                    radial-gradient(circle at 15% 0%, rgba(96,165,250,.42), transparent 45%),
                    linear-gradient(135deg, #020617 0%, #172554 56%, #075985 100%);
            }}
            .auth-pill {{ margin-bottom: 14px; }}
            .auth-welcome-title {{ font-size: 1.6rem; margin-bottom: 10px; }}
            .auth-welcome-sub {{ margin-bottom: 40px; }}
            .auth-logo-circle {{
                width: 110px;
                height: 110px;
                flex-basis: 110px;
                box-shadow: 0 0 0 8px rgba(255,255,255,.07), 0 18px 40px rgba(2,6,23,.5);
            }}
            .auth-logo-circle::before,
            .auth-logo-circle::after {{ inset: -70px; }}
            .st-key-auth_right {{ min-height: 0; padding: 26px 18px 22px; }}
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )
'''


def main():
    try:
        text = open(APP_FILE, encoding="utf-8").read()
    except FileNotFoundError:
        sys.exit(f"لم أجد {APP_FILE} في هذا المجلد. ضع هذا الملف بجانبه ثم شغّله.")

    start = text.find("def inject_auth_css():")
    end = text.find("@contextmanager\ndef auth_card(", start)
    if start == -1 or end == -1:
        sys.exit("لم أجد دالة inject_auth_css() أو auth_card() في الملف. لم يتم تغيير شيء.")

    new_text = text[:start] + NEW_FUNC.rstrip() + "\n\n\n" + text[end:]
    compile(new_text, APP_FILE, "exec")  # syntax check BEFORE writing anything

    shutil.copyfile(APP_FILE, APP_FILE + ".bak2")
    open(APP_FILE, "w", encoding="utf-8", newline="\n").write(new_text)
    print("Done. Backup saved as", APP_FILE + ".bak2")


if __name__ == "__main__":
    main()