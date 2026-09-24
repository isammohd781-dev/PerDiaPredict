c = open('diabetes_app.py', encoding='utf-8').read()

checks = {
    '1.  ACCOUNT_FIELDS gender     ': '"gender",' in c and '"Gender",' in c,
    '2.  _rows_from_sheet          ': '"gender": get(raw' in c,
    '3.  _save_rows widths         ': '[7, 16, 16, 32, 13, 10, 60' in c,
    '4.  _import_old_sqlite        ': '"gender": "",' in c,
    '5.  create_user gender        ': 'password: str, gender: str' in c,
    '6.  authenticate gender       ': 'row.get("gender", "")' in c,
    '7.  admin table gender        ': '"Gender": r.get' in c,
    '8.  register gender field     ': 'key="reg_gender"' in c,
    '9.  main gender locked        ': 'key="basic_gender_locked"' in c,
    '10. cleanup session           ': 'pop("basic_gender"' in c,
}

print("=" * 45)
print("  فحص التعديلات في diabetes_app.py")
print("=" * 45)
for name, ok in checks.items():
    print(("  ✅ " if ok else "  ❌ ") + name)
print("=" * 45)
total = sum(checks.values())
print(f"  النتيجة: {total} / {len(checks)} تعديل موجود")
print("=" * 45)