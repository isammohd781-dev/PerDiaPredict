"""diagnose.py — shows the actual structure of diabetes_app.py"""

import re
import sys

# Force UTF-8 output on Windows so Arabic text in the file doesn't crash.
sys.stdout.reconfigure(encoding="utf-8")

with open("diabetes_app.py", encoding="utf-8") as f:
    content = f.read()


def show(title, pattern, flags=0):
    print("\n" + "=" * 70)
    print(title)
    print("=" * 70)
    m = re.search(pattern, content, flags)
    if m:
        line = content[:m.start()].count("\n") + 1
        print(f"LINE {line}:")
        print(m.group())
    else:
        print("NOT FOUND")


# 1) Gender options
print("=" * 70)
print("1) GENDER_OPTIONS / SEX_AT_BIRTH_OPTIONS / GENDER_IDENTITY_OPTIONS")
print("=" * 70)
found = False
for m in re.finditer(r'(GENDER_OPTIONS|SEX_AT_BIRTH_OPTIONS|GENDER_IDENTITY_OPTIONS)\s*=\s*\[[^\]]*\]', content):
    found = True
    line = content[:m.start()].count("\n") + 1
    print(f"\nLINE {line}:")
    print(m.group())
if not found:
    print("NOT FOUND")

# 2) gender_label
show("2) gender_label function",
     r'def gender_label\([^)]*\)[^:]*:.*?(?=\ndef |\n@|\nclass )',
     re.DOTALL)

# 3) ACCOUNT_FIELDS
show("3) ACCOUNT_FIELDS",
     r'ACCOUNT_FIELDS\s*=\s*\[.*?\]',
     re.DOTALL)

# 4) ACCOUNT_HEADERS
show("4) ACCOUNT_HEADERS",
     r'ACCOUNT_HEADERS\s*=\s*\[.*?\]',
     re.DOTALL)

# 5) reg fields
print("\n" + "=" * 70)
print("5) Registration fields (reg_*)")
print("=" * 70)
reg_keys = re.findall(r'key="(reg_[a-z_]+)"', content)
for k in reg_keys:
    print(" -", k)
if not reg_keys:
    print("NOT FOUND")

# 6) basic fields
print("\n" + "=" * 70)
print("6) Main page fields (basic_*)")
print("=" * 70)
basic_keys = re.findall(r'key="(basic_[a-z_]+)"', content)
for k in basic_keys:
    print(" -", k)
if not basic_keys:
    print("NOT FOUND")

# 7) create_user
show("7) create_user signature",
     r'def create_user\([^)]*\)[^:]*:',
     re.DOTALL)

# 8) _save_rows widths
show("8) _save_rows widths",
     r'widths\s*=\s*\[[\d,\s]+\]')

# 9) age field
show("9) Age field on main page",
     r'age = st\.(number_input|text_input)\([^)]*\)',
     re.DOTALL)

# 10) authenticate return
show("10) authenticate return dict",
     r'return \{[^}]*"gender"[^}]*\}, "ok"',
     re.DOTALL)

# 11) build_report signature
show("11) build_report signature",
     r'def build_report\([^)]*\)[^:]*:',
     re.DOTALL)

print("\n" + "=" * 70)
print("DONE. Copy the full output.")
print("=" * 70)