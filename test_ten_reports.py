import test_reports as base
from report_locale import EXTRA_VALUES,report_language
from pathlib import Path
from io import BytesIO
from pypdf import PdfReader
for lang in EXTRA_VALUES:
    report={**base.report,'Language':lang}
    assert report_language(report)==lang
    data=base.ns['generate_pdf_report'](report,answers=base.answers)
    Path('tmp/pdfs/report_'+lang+'.pdf').write_bytes(data)
    text=' '.join(p.extract_text() for p in PdfReader(BytesIO(data)).pages)
    assert EXTRA_VALUES[lang][1] in text,(lang,text)
# Exercise the language page using the complete source with synthetic adapters.
import test_experience as e
from streamlit.testing.v1 import AppTest
languages={'en':'English','ar':'العربية','fr':'Français','es':'Español','de':'Deutsch','tr':'Türkçe','hi':'हिन्दी','pt':'Português','ru':'Русский','zh':'简体中文'}
prefix=e.prefix.replace("t.LANGUAGES={'en':{'native':'English','rtl':False}}","t.LANGUAGES="+repr({k:{'native':v,'rtl':k=='ar'} for k,v in languages.items()}))
app=AppTest.from_string(prefix+e.source,default_timeout=20).run()
app.session_state['page']='language';app.session_state['choosing_language']=True;app.run()
assert not app.exception,app.exception
keys={b.key for b in app.button}
assert {'lang_'+lang for lang in languages}<=keys
assert not keys.intersection({'open_program_policy','open_privacy_policy'})
app.session_state['page']='auth';app.run()
assert any('policy-sentence' in m.value and 'policy=privacy' in m.value for m in app.markdown)
print('PASS: ten-language selection retained, no policies on language page, auth policy links retained, five additional PDF label sets and fonts.')
