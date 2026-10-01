"""Shared visual rules for all languages and application pages."""
def inject_visual_accessibility():
    import streamlit as st
    dark = st.session_state.get('dark_mode', False)
    lang = st.session_state.get('lang', 'en')
    # Explicitly opt out of automatic browser darkening in light appearance.
    # Keep accessibility forced-color preferences enabled (no forced-color-adjust override).
    scheme = 'dark' if dark else 'only light'
    page = '#080d18' if dark else '#edf4fb'
    st.markdown(f'''<style>
    :root, html, body, #root {{color-scheme:{scheme}!important;}}
    html, body, #root {{background-color:{page}!important;}}
    .stApp, [data-testid="stAppViewContainer"], [data-testid="stMain"],
    [data-testid="stHeader"], [data-baseweb="popover"] {{color-scheme:{scheme}!important;}}
    .stApp :is(input,textarea,select,button) {{color-scheme:{scheme}!important;}}
    </style>''', unsafe_allow_html=True)
    direction = 'rtl' if lang == 'ar' else 'ltr'
    align = 'right' if lang == 'ar' else 'left'
    surface, field, text, muted, border = ('#111c30','#17243b','#f1f5f9','#b5c3d7','#425571') if dark else ('#ffffff','#ffffff','#152b49','#49617d','#b8c9de')
    st.markdown(f'''<style>
    .stApp {{ --surface:{surface}; --text:{text}; --muted:{muted}; --border:{border}; }}
    .stApp [data-testid="stMarkdownContainer"],.stApp label {{font-family:Arial,"Noto Sans", "Noto Sans Arabic", "Noto Sans Devanagari", "Microsoft YaHei",sans-serif;line-height:1.65;}}
    .stApp [data-testid="stMarkdownContainer"] {{direction:{direction};text-align:{align};}}
    .stApp [data-testid="stMarkdownContainer"] :is(h1,h2,h3,h4,p,li), .stApp label {{color:{text}!important;letter-spacing:normal!important;}}
    .stApp [data-testid="stCaptionContainer"] p {{color:{muted}!important;}}
    .stApp :is(.admin-banner,.medical-report h2,.medical-report h2+p) {{color:#fff!important;}}
    .stApp .admin-banner :is(h1,h2,p),.stApp .medical-report h2 {{color:#fff!important;-webkit-text-fill-color:#fff!important;}}
    .stApp .admin-banner .admin-kicker {{color:#b7f7df!important;}}
    .stApp .medical-report h2+p {{background:#0f233f!important;border-color:#38d5d0!important;color:#dce8f5!important;-webkit-text-fill-color:#dce8f5!important;}}
    .stApp :is(.hero,.section-card,.status-card,.notice,.support-card,.ux-hero,.medical-report,.result-card) {{border:1px solid {border}!important;border-radius:18px;padding:22px;overflow-wrap:anywhere;}}
    .stApp .medical-report>p {{background:{field};border:1px solid {border};border-radius:12px;padding:14px;line-height:1.75;}}
    .stApp .medical-report[dir="rtl"],.stApp .medical-report[dir="rtl"] :is(h2,h3,p,.medical-field) {{direction:rtl!important;text-align:right!important;}}
    .stApp .medical-report[dir="ltr"],.stApp .medical-report[dir="ltr"] :is(h2,h3,p,.medical-field) {{direction:ltr!important;text-align:left!important;}}
    .stApp .medical-grid {{direction:inherit;}}
    .stApp .medical-field {{border:1px solid {border};border-radius:12px;padding:14px;background:{field};text-align:{align};}}
    .stApp [data-testid="stForm"] {{border:1px solid {border}!important;border-radius:16px!important;padding:18px!important;background:{surface}!important;}}
    .stApp [data-testid="stForm"] [data-testid="stVerticalBlock"] {{gap:1rem!important;}}
    .stApp .st-key-auth_right [data-testid="stForm"] {{border:1px solid {border}!important;padding:18px!important;background:{surface}!important;}}
    .stApp .st-key-auth_right [data-testid="stVerticalBlock"] {{gap:.8rem!important;}}
    .stApp :is([data-testid="stTextInputRootElement"],[data-testid="stNumberInputContainer"],[data-baseweb="textarea"]) {{background:{field}!important;border:1px solid {border}!important;border-radius:12px!important;}}
    .stApp input,.stApp textarea {{background:{field}!important;color:{text}!important;-webkit-text-fill-color:{text}!important;line-height:1.5!important;}}
    .stApp textarea {{direction:{direction};text-align:{align};}}
    .stApp input {{text-align:{align};}}
    .stApp input:is([type="email"],[type="password"],[type="number"],[type="tel"]) {{direction:ltr;text-align:left;}}
    .stApp [data-baseweb="select"]>div {{background:{field}!important;color:{text}!important;border-color:{border}!important;min-height:48px;border-radius:12px!important;}}
    .stApp [data-baseweb="select"] {{direction:{direction};}}
    .stApp [data-testid="stAlert"] {{border:1px solid {border}!important;background:{surface}!important;border-radius:14px!important;}}
    .stApp button:focus-visible,.stApp input:focus-visible,.stApp textarea:focus-visible {{outline:3px solid #2185d5!important;outline-offset:3px;}}
    .stApp button[kind="primary"] p,.stApp [data-testid="stBaseButton-primary"] p,.stApp [data-testid="stBaseButton-primaryFormSubmit"] p {{color:white!important;-webkit-text-fill-color:white!important;}}
    .stApp .st-key-auth_right [class*="st-key-auth_"][class*="admin"] button,.stApp .st-key-auth_right [class*="st-key-auth_link"] button {{width:100%!important;border:1px solid {border}!important;background:{field}!important;min-height:48px!important;padding:10px 14px!important;}}
    .stApp .st-key-auth_right [class*="st-key-auth_"][class*="admin"] button p,.stApp .st-key-auth_right [class*="st-key-auth_link"] button p {{color:{text}!important;-webkit-text-fill-color:{text}!important;}}
    .stApp .st-key-auth_right :is(.st-key-auth_btn_admin,.st-key-auth_link_back) {{margin:0!important;}}
    .stApp .brand-name,.stApp .brand-tagline {{letter-spacing:normal!important;}}
    @media(max-width:640px){{.stApp .medical-grid{{grid-template-columns:1fr;}}.stApp [data-testid="stForm"]{{padding:14px!important;}}}}
    </style>''',unsafe_allow_html=True)


    if st.session_state.get('page') in ('auth','login','register'):
        control = '#262626' if dark else '#f3f5f7'
        control_text = '#f5f5f5' if dark else '#18212f'
        control_border = '#414141' if dark else '#ccd2dc'
        primary = '#ffffff' if dark else '#13243b'
        primary_text = '#111111' if dark else '#ffffff'
        target='.stApp .st-key-auth_right.st-key-auth_right.st-key-auth_right'
        st.markdown(f'''<style>
        {target} button {{width:100%!important;min-height:50px!important;padding:12px 18px!important;border-radius:12px!important;background:{control}!important;border:1px solid {control_border}!important;box-shadow:none!important;transform:none!important;}}
        {target} button p {{font-size:1rem!important;font-weight:600!important;line-height:1.4!important;color:{control_text}!important;-webkit-text-fill-color:{control_text}!important;}}
        {target} button::after {{content:none!important;}}
        {target} button:hover {{filter:brightness({'1.15' if dark else '.97'})!important;border-color:#75849b!important;transform:none!important;}}
        {target} :is([data-testid="stBaseButton-primary"],[data-testid="stBaseButton-primaryFormSubmit"]) {{background:{primary}!important;border-color:{primary}!important;box-shadow:none!important;}}
        {target} :is([data-testid="stBaseButton-primary"],[data-testid="stBaseButton-primaryFormSubmit"]) p {{color:{primary_text}!important;-webkit-text-fill-color:{primary_text}!important;}}
        {target} :is([data-testid="stTextInputRootElement"],[data-baseweb="input"],[data-baseweb="textarea"]) {{background:{control}!important;border:1px solid {control_border}!important;border-radius:12px!important;box-shadow:none!important;}}
        {target} input,{target} textarea {{background:{control}!important;color:{control_text}!important;-webkit-text-fill-color:{control_text}!important;}}
        {target} [data-baseweb="select"]>div {{background:{control}!important;color:{control_text}!important;border-color:{control_border}!important;border-radius:12px!important;}}
        {target} input::placeholder,{target} textarea::placeholder {{color:{muted}!important;-webkit-text-fill-color:{muted}!important;opacity:1;}}
        {target} :is([data-baseweb="input"],[data-baseweb="textarea"]):focus-within {{border-color:#4c9bda!important;box-shadow:0 0 0 3px #4c9bda24!important;}}
        </style>''',unsafe_allow_html=True)

    st.markdown(f'''<style>
    .stApp .policy-sentence{{font-size:.86rem;line-height:1.65;color:{muted}!important;text-align:center;margin:10px 0 0;padding:4px 0;}}
    .stApp .policy-sentence a{{color:{'#71baff' if dark else '#076ab5'}!important;text-decoration:underline;text-underline-offset:3px;}}
    .stApp .support-card{{border:1px solid {border}!important;border-radius:16px!important;padding:20px!important;background:{surface}!important;box-shadow:none!important;margin:16px 0!important;}}
    .stApp .support-card .support-title{{font-size:1.15rem!important;line-height:1.4!important;margin-bottom:8px;color:{text}!important;}}
    .stApp .support-card .support-text{{font-size:.92rem!important;line-height:1.65!important;color:{muted}!important;margin-bottom:14px;}}
    .stApp .st-key-auth_right.st-key-auth_right.st-key-auth_right .support-link{{border-radius:12px!important;white-space:normal!important;display:inline-flex!important;flex-wrap:wrap;gap:8px;justify-content:center;padding:12px 18px!important;font-size:1rem!important;}}
    .stApp .st-key-auth_right.st-key-auth_right.st-key-auth_right [data-baseweb="select"]{{background:var(--surface)!important;border:1px solid {border}!important;border-radius:12px!important;overflow:visible!important;}}
    .stApp .st-key-auth_right.st-key-auth_right.st-key-auth_right [data-baseweb="select"]>div{{border:0!important;border-radius:11px!important;box-shadow:none!important;min-height:48px!important;}}
    .stApp .st-key-auth_right.st-key-auth_right.st-key-auth_right [data-baseweb="select"] :is(div,span,input){{color:{text}!important;-webkit-text-fill-color:{text}!important;}}
    .stApp .st-key-auth_right.st-key-auth_right.st-key-auth_right [data-baseweb="select"] [data-baseweb="input"]{{border:0!important;box-shadow:none!important;min-height:0!important;}}
    .stApp .st-key-auth_right.st-key-auth_right.st-key-auth_right [data-baseweb="select"] input{{height:auto!important;min-height:0!important;padding:0!important;margin:0!important;background:transparent!important;border:0!important;border-radius:0!important;}}
    .stApp .st-key-auth_right.st-key-auth_right.st-key-auth_right [data-testid="stTextInputRootElement"] [data-baseweb="input"]{{border:0!important;background:transparent!important;box-shadow:none!important;}}
    .stApp .st-key-auth_right.st-key-auth_right.st-key-auth_right [data-testid="stTextInputRootElement"] button{{width:auto!important;min-height:0!important;border:0!important;background:transparent!important;box-shadow:none!important;transform:none!important;padding:8px 12px!important;}}
    .stApp .st-key-auth_right.st-key-auth_right.st-key-auth_right [data-testid="stTextInputRootElement"] button svg{{color:{text}!important;fill:currentColor!important;}}
    .stApp .st-key-auth_right.st-key-auth_right.st-key-auth_right :is(.st-key-auth_link_register,.st-key-auth_link_back_login) button{{width:100%!important;}}
    </style>''',unsafe_allow_html=True)

    # Streamlit's React Aria selectboxes use a group/input/button, not BaseWeb.
    # Keep the arrow compact so the form's full-width button rules cannot hide input.
    if st.session_state.get('page') in ('register', 'doctor_register'):
        target = '.stApp .st-key-auth_right.st-key-auth_right.st-key-auth_right'
        st.markdown(f'''<style>
        {target} [data-testid="stSelectbox"] [role="group"] {{
            display:flex!important;align-items:center!important;gap:0!important;
            min-height:48px!important;width:100%!important;box-sizing:border-box!important;
            background:{field}!important;border:1px solid {border}!important;
            border-radius:12px!important;overflow:hidden!important;padding:0!important;
        }}
        {target} [data-testid="stSelectbox"] input[role="combobox"] {{
            flex:1 1 0%!important;width:0!important;min-width:0!important;
            height:46px!important;margin:0!important;padding:10px 12px!important;
            border:0!important;border-radius:0!important;box-shadow:none!important;
            background:transparent!important;color:{text}!important;
            -webkit-text-fill-color:{text}!important;opacity:1!important;
            font-size:.95rem!important;line-height:1.4!important;
        }}
        {target} [data-testid="stSelectbox"] [role="group"] button {{
            flex:0 0 auto!important;width:36px!important;min-width:36px!important;
            height:46px!important;min-height:0!important;margin:0!important;
            padding:0 8px!important;border:0!important;border-radius:0!important;
            background:transparent!important;box-shadow:none!important;transform:none!important;
            color:{text}!important;
        }}
        {target} [data-testid="stSelectbox"] [role="group"]:focus-within {{
            border-color:#2185d5!important;box-shadow:0 0 0 3px #2185d524!important;
        }}
        {target} [data-testid="stSelectbox"] [role="group"] button svg {{color:{text}!important;}}
        </style>''', unsafe_allow_html=True)

    if st.session_state.get('page') == 'register':
        target = '.stApp .st-key-auth_right.st-key-auth_right.st-key-auth_right'
        st.markdown(f'''<style>
        {target} .st-key-register_form .notice {{
            padding:18px 20px!important;margin:12px 0 18px!important;
            line-height:1.75!important;font-size:.92rem!important;
            text-align:{align}!important;direction:{direction}!important;
        }}
        {target} .st-key-register_form .notice strong {{
            display:block!important;margin:0 0 8px!important;
            font-size:.95rem!important;font-weight:600!important;line-height:1.5!important;
        }}
        {target} .st-key-register_form .notice strong + br {{display:none!important;}}
        {target} .st-key-reg_accept {{margin:0 0 14px!important;padding:0 4px!important;}}
        {target} .st-key-reg_accept [data-testid="stCheckbox"] label {{
            display:flex!important;align-items:flex-start!important;
            gap:10px!important;direction:{direction}!important;
        }}
        {target} .st-key-reg_accept [data-testid="stCheckbox"] label > span {{
            flex-shrink:0!important;margin-top:3px!important;
        }}
        {target} .st-key-reg_accept [data-testid="stMarkdownContainer"] p {{
            font-size:.9rem!important;font-weight:400!important;
            line-height:1.65!important;margin:0!important;text-align:{align}!important;
        }}
        @media(max-width:640px) {{
            {target} .st-key-register_form .notice {{padding:16px!important;}}
        }}
        </style>''', unsafe_allow_html=True)

    # The profile always has a navy background, including in light appearance.
    # Its explicit palette must outrank shared markdown foreground rules.
    st.markdown('''<style>
    .stApp .st-key-profile_summary .profile-content h1.profile-heading {
        color:#f8fafc!important;-webkit-text-fill-color:#f8fafc!important;
    }
    .stApp .st-key-profile_summary .profile-content p.profile-subtitle {
        color:#d3e2f2!important;-webkit-text-fill-color:#d3e2f2!important;opacity:1!important;
    }
    .stApp .st-key-profile_summary .profile-content .profile-detail span {
        color:#b8cee8!important;-webkit-text-fill-color:#b8cee8!important;
    }
    .stApp .st-key-profile_summary .profile-content .profile-detail strong {
        color:#ffffff!important;-webkit-text-fill-color:#ffffff!important;
    }
    .stApp .st-key-profile_summary .profile-content .profile-id {
        color:#ffffff!important;-webkit-text-fill-color:#ffffff!important;
        background:#334b65!important;border-color:#60738c!important;
    }
    .stApp .st-key-profile_summary .st-key-profile_edit_toggle button {
        background:#f8fafc!important;border:1px solid #c5d5e8!important;
    }
    .stApp .st-key-profile_summary .st-key-profile_edit_toggle button p {
        color:#152b49!important;-webkit-text-fill-color:#152b49!important;
    }
    .stApp .st-key-profile_summary .st-key-profile_edit_toggle button:hover {
        background:#e0edfa!important;border-color:#83add5!important;
    }
    </style>''', unsafe_allow_html=True)

    st.markdown(f'''<style>
    .stApp :is(.st-key-care_connect_panel,[class*="st-key-care_connection_"],[class*="st-key-care_note_"]) {{
        background:{surface}!important;border:1px solid {border}!important;
        border-radius:16px!important;padding:20px!important;margin:12px 0!important;
        box-sizing:border-box!important;overflow-wrap:anywhere!important;
    }}
    .stApp :is(.st-key-care_connect_panel,[class*="st-key-care_connection_"],[class*="st-key-care_note_"]) [data-testid="stCaptionContainer"] p {{
        color:{muted}!important;-webkit-text-fill-color:{muted}!important;opacity:1!important;
    }}
    @media(max-width:640px) {{
        .stApp :is(.st-key-care_connect_panel,[class*="st-key-care_connection_"],[class*="st-key-care_note_"]) {{padding:16px!important;}}
    }}
    </style>''', unsafe_allow_html=True)

    st.markdown(f'''<style>
    .stApp .st-key-care_connect_button button:disabled {{
        background:transparent!important;border:1px solid {border}!important;
        box-shadow:none!important;opacity:.65!important;cursor:not-allowed!important;
    }}
    .stApp .st-key-care_connect_button button:disabled p {{
        color:{muted}!important;-webkit-text-fill-color:{muted}!important;
    }}
    .stApp .st-key-care_connect_button button:not(:disabled) {{
        background:#087f78!important;border:1px solid #087f78!important;
        box-shadow:none!important;opacity:1!important;
    }}
    .stApp .st-key-care_connect_button button:not(:disabled) p {{
        color:#ffffff!important;-webkit-text-fill-color:#ffffff!important;
    }}
    .stApp .st-key-care_connect_button button:not(:disabled):hover {{background:#066b65!important;}}
    </style>''', unsafe_allow_html=True)
