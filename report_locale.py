"""Report labels shared by HTML, individual PDFs and combined reports."""
from pathlib import Path
KEYS = ['PATIENT SCREENING REPORT','PATIENT INFORMATION','RISK ASSESSMENT','REPORTED SYMPTOMS','PATIENT NOTES / ADDITIONAL SYMPTOMS','RECOMMENDATION','SCREENING ANSWERS','Patient ID','Patient name','Age / Gender','Marital status','Phone','Country','Assessment date','Recorded diabetes type','Hospital / clinic','Care information','Patient-reported location','SCREENING RESULT','ESTIMATED RISK','Question','Answer','Not recorded','Not assigned','No additional notes provided.','Glucose reading','Model version','Educational screening estimate. This result is not a medical diagnosis.','Patient notes and additional questions are included for reference and do not change the model score.','Educational screening. This report is not a medical diagnosis.']
VALUES = {
'ar':['تقرير فحص المريض','بيانات المريض','تقييم الخطر','الأعراض المذكورة','ملاحظات المريض والأعراض الإضافية','التوصية','إجابات الفحص','الرقم التعريفي للمريض','اسم المريض','العمر / الجنس','الحالة الاجتماعية','الهاتف','الدولة','تاريخ التقييم','نوع السكري المذكور','المستشفى / العيادة','بيانات الرعاية','الموقع حسب إفادة المريض','نتيجة الفحص','تقدير الخطر','السؤال','الإجابة','غير مسجل','غير محدد','لم تُضف ملاحظات.','قراءة السكر','إصدار النموذج','هذا تقدير تعليمي للفحص وليس تشخيصًا طبيًا.','تُدرج الملاحظات والأسئلة الإضافية للرجوع إليها ولا تغيّر نتيجة النموذج.','فحص تعليمي. هذا التقرير ليس تشخيصًا طبيًا.'],
'es':['INFORME DE EVALUACIÓN DEL PACIENTE','INFORMACIÓN DEL PACIENTE','EVALUACIÓN DEL RIESGO','SÍNTOMAS INDICADOS','NOTAS DEL PACIENTE / SÍNTOMAS ADICIONALES','RECOMENDACIÓN','RESPUESTAS DE LA EVALUACIÓN','ID del paciente','Nombre del paciente','Edad / Género','Estado civil','Teléfono','País','Fecha de evaluación','Tipo de diabetes indicado','Hospital / clínica','Información de atención','Ubicación indicada por el paciente','RESULTADO DE LA EVALUACIÓN','RIESGO ESTIMADO','Pregunta','Respuesta','Sin registrar','Sin asignar','No se añadieron notas.','Lectura de glucosa','Versión del modelo','Estimación educativa. Este resultado no es un diagnóstico médico.','Las notas y preguntas adicionales se incluyen como referencia y no cambian la puntuación del modelo.','Evaluación educativa. Este informe no es un diagnóstico médico.'],
'hi':['रोगी की जांच रिपोर्ट','रोगी की जानकारी','जोखिम का आकलन','बताए गए लक्षण','रोगी के नोट्स / अतिरिक्त लक्षण','सुझाव','जांच के उत्तर','रोगी की पहचान संख्या','रोगी का नाम','उम्र / लिंग','वैवाहिक स्थिति','फ़ोन','देश','आकलन की तारीख','बताया गया मधुमेह का प्रकार','अस्पताल / क्लिनिक','देखभाल की जानकारी','रोगी द्वारा बताया गया स्थान','जांच का परिणाम','अनुमानित जोखिम','प्रश्न','उत्तर','दर्ज नहीं है','निर्धारित नहीं है','कोई अतिरिक्त नोट नहीं दिया गया।','ग्लूकोज़ का स्तर','मॉडल का संस्करण','यह शैक्षिक आकलन है, चिकित्सा निदान नहीं।','नोट्स और अतिरिक्त प्रश्न केवल संदर्भ के लिए हैं और मॉडल के स्कोर को नहीं बदलते।','शैक्षिक जांच। यह रिपोर्ट चिकित्सा निदान नहीं है।'],
'zh':['患者筛查报告','患者信息','风险评估','报告的症状','患者备注 / 其他症状','建议','筛查回答','患者编号','患者姓名','年龄 / 性别','婚姻状况','电话','国家','评估日期','报告的糖尿病类型','医院 / 诊所','照护信息','患者报告的位置','筛查结果','估计风险','问题','回答','未记录','未指定','未提供其他备注。','血糖读数','模型版本','本结果为教育性筛查估计，不属于医学诊断。','备注和其他问题仅供参考，不改变模型评分。','教育性筛查。本报告不属于医学诊断。']}
LABELS={lang:dict(zip(KEYS,values)) for lang,values in VALUES.items()}


def report_language(report, default='en'):
    if report.get('Language') in ('en','ar','fr','es','de','tr','hi','pt','ru','zh'):
        return report['Language']
    return default if default in ('en','ar','fr','es','de','tr','hi','pt','ru','zh') else 'en'


def text(value, lang):
    return LABELS.get(lang,{}).get(str(value),value)


def localize_html(markup,lang):
    import re
    # Translate report headings and fixed explanatory paragraphs, not patient notes.
    markup=re.sub(r'<h3>([^<>]+)</h3>',lambda m:'<h3>'+str(text(m.group(1),lang))+'</h3>',markup)
    for value in ('PATIENT SCREENING REPORT','Educational screening. This report is not a medical diagnosis.'):
        markup=markup.replace('<p>'+value+'</p>','<p>'+str(text(value,lang))+'</p>')
    return markup


def unicode_markup(value,default_font):
    """Font runs preserve patient notes in all supported scripts."""
    import re
    from html import escape
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    if re.search(r'[\u2e80-\u9fff\uf900-\ufaff]',value) and 'ReportChinese' not in pdfmetrics.getRegisteredFontNames():
        path=Path(__file__).resolve().parent/'fonts'/'NotoSansSC-Regular.ttf'
        if not path.exists(): raise RuntimeError('Missing bundled Chinese font: fonts/NotoSansSC-Regular.ttf')
        pdfmetrics.registerFont(TTFont('ReportChinese',str(path)))
    if re.search(r'[\u0900-\u097f]',value) and 'ReportHindi' not in pdfmetrics.getRegisteredFontNames():
        path=Path(__file__).resolve().parent/'fonts'/'NotoSansDevanagari-Regular.ttf'
        if not path.exists(): raise RuntimeError('Missing bundled Hindi font: fonts/NotoSansDevanagari-Regular.ttf')
        pdfmetrics.registerFont(TTFont('ReportHindi',str(path)))
    runs=re.split(r'([\u2e80-\u9fff\uf900-\ufaff]+|[\u0900-\u097f][\u0900-\u097f ]*)',value)
    out=[]
    for run in runs:
        if not run:continue
        font='ReportChinese' if re.search(r'[\u2e80-\u9fff\uf900-\ufaff]',run) else ('ReportHindi' if re.search(r'[\u0900-\u097f]',run) else default_font)
        out.append('<font name="'+font+'">'+escape(run).replace('\n','<br/>')+'</font>')
    return ''.join(out)
ACTIVITY_KEYS=['PATIENT ACTIVITY RECORD','Authority','Request reference','Medical permit','Approved by','Purpose','Generated UTC','Time / source','Action / actor / details','No recorded events','Contains recorded application events only. It is not proof of all user actions or legal authorization.']
ACTIVITY_VALUES={
'ar':['سجل نشاط المريض','الجهة الطالبة','مرجع الطلب','التصريح الطبي','الموافق على التصريح','الغرض','وقت الإنشاء UTC','الوقت / المصدر','الإجراء / المستخدم / التفاصيل','لا توجد أحداث مسجلة','يتضمن الأحداث المسجلة في التطبيق فقط ولا يثبت جميع الإجراءات أو وجود تصريح قانوني.'],
'es':['REGISTRO DE ACTIVIDAD DEL PACIENTE','Autoridad','Referencia de solicitud','Permiso médico','Aprobado por','Finalidad','Generado UTC','Hora / fuente','Acción / usuario / detalles','No hay eventos registrados','Incluye solo eventos registrados en la aplicación; no demuestra todas las acciones ni autorización legal.'],
'hi':['रोगी की गतिविधि का रिकॉर्ड','प्राधिकरण','अनुरोध का संदर्भ','चिकित्सा अनुमति','स्वीकृत करने वाला','उद्देश्य','बनाने का समय UTC','समय / स्रोत','कार्रवाई / उपयोगकर्ता / विवरण','कोई घटना दर्ज नहीं है','केवल ऐप में दर्ज घटनाएं शामिल हैं। यह सभी कार्रवाइयों या कानूनी अनुमति का प्रमाण नहीं है।'],
'zh':['患者活动记录','请求机构','请求编号','医疗许可','批准人','用途','生成时间 UTC','时间 / 来源','操作 / 用户 / 详情','没有记录的事件','仅包含应用中记录的事件，不能证明所有操作或法律授权。']}
for _lang,_values in ACTIVITY_VALUES.items(): LABELS[_lang].update(zip(ACTIVITY_KEYS,_values))
EXTRA_VALUES={
'fr':['RAPPORT DE DÉPISTAGE DU PATIENT','INFORMATIONS DU PATIENT','ÉVALUATION DU RISQUE','SYMPTÔMES SIGNALÉS','NOTES DU PATIENT / SYMPTÔMES SUPPLÉMENTAIRES','RECOMMANDATION','RÉPONSES AU DÉPISTAGE','Identifiant du patient','Nom du patient','Âge / Sexe','Situation familiale','Téléphone','Pays','Date de l’évaluation','Type de diabète déclaré','Hôpital / clinique','Informations de suivi','Lieu déclaré par le patient','RÉSULTAT DU DÉPISTAGE','RISQUE ESTIMÉ','Question','Réponse','Non renseigné','Non attribué','Aucune note supplémentaire.','Glycémie','Version du modèle','Estimation éducative de dépistage. Ce résultat ne constitue pas un diagnostic médical.','Les notes et questions supplémentaires sont fournies à titre indicatif et ne modifient pas le score du modèle.','Dépistage éducatif. Ce rapport ne constitue pas un diagnostic médical.'],
'de':['SCREENINGBERICHT DES PATIENTEN','PATIENTENINFORMATIONEN','RISIKOBEWERTUNG','ANGEGEBENE SYMPTOME','PATIENTENNOTIZEN / ZUSÄTZLICHE SYMPTOME','EMPFEHLUNG','SCREENINGANTWORTEN','Patienten-ID','Name des Patienten','Alter / Geschlecht','Familienstand','Telefon','Land','Bewertungsdatum','Angegebener Diabetes-Typ','Krankenhaus / Praxis','Betreuungsinformationen','Vom Patienten angegebener Ort','SCREENINGERGEBNIS','GESCHÄTZTES RISIKO','Frage','Antwort','Nicht erfasst','Nicht zugewiesen','Keine zusätzlichen Notizen.','Blutzuckerwert','Modellversion','Screeningschätzung zu Bildungszwecken. Dieses Ergebnis ist keine medizinische Diagnose.','Notizen und zusätzliche Fragen dienen als Referenz und ändern den Modellwert nicht.','Screening zu Bildungszwecken. Dieser Bericht ist keine medizinische Diagnose.'],
'tr':['HASTA TARAMA RAPORU','HASTA BİLGİLERİ','RİSK DEĞERLENDİRMESİ','BİLDİRİLEN BELİRTİLER','HASTA NOTLARI / EK BELİRTİLER','ÖNERİ','TARAMA YANITLARI','Hasta kimliği','Hasta adı','Yaş / Cinsiyet','Medeni durum','Telefon','Ülke','Değerlendirme tarihi','Bildirilen diyabet türü','Hastane / klinik','Takip bilgileri','Hastanın bildirdiği konum','TARAMA SONUCU','TAHMİNİ RİSK','Soru','Yanıt','Kaydedilmedi','Atanmadı','Ek not verilmedi.','Kan şekeri değeri','Model sürümü','Eğitim amaçlı tarama tahmini. Bu sonuç tıbbi tanı değildir.','Notlar ve ek sorular bilgi için eklenir ve model puanını değiştirmez.','Eğitim amaçlı tarama. Bu rapor tıbbi tanı değildir.'],
'pt':['RELATÓRIO DE RASTREIO DO PACIENTE','INFORMAÇÕES DO PACIENTE','AVALIAÇÃO DO RISCO','SINTOMAS RELATADOS','NOTAS DO PACIENTE / SINTOMAS ADICIONAIS','RECOMENDAÇÃO','RESPOSTAS DO RASTREIO','ID do paciente','Nome do paciente','Idade / Sexo','Estado civil','Telefone','País','Data da avaliação','Tipo de diabetes indicado','Hospital / clínica','Informações de acompanhamento','Local indicado pelo paciente','RESULTADO DO RASTREIO','RISCO ESTIMADO','Pergunta','Resposta','Não registado','Não atribuído','Sem notas adicionais.','Leitura de glicose','Versão do modelo','Estimativa educativa de rastreio. Este resultado não é um diagnóstico médico.','As notas e perguntas adicionais são incluídas como referência e não alteram a pontuação do modelo.','Rastreio educativo. Este relatório não é um diagnóstico médico.'],
'ru':['ОТЧЁТ О СКРИНИНГЕ ПАЦИЕНТА','ИНФОРМАЦИЯ О ПАЦИЕНТЕ','ОЦЕНКА РИСКА','УКАЗАННЫЕ СИМПТОМЫ','ПРИМЕЧАНИЯ ПАЦИЕНТА / ДОПОЛНИТЕЛЬНЫЕ СИМПТОМЫ','РЕКОМЕНДАЦИЯ','ОТВЕТЫ НА ВОПРОСЫ СКРИНИНГА','Идентификатор пациента','Имя пациента','Возраст / Пол','Семейное положение','Телефон','Страна','Дата оценки','Указанный тип диабета','Больница / клиника','Информация о наблюдении','Место, указанное пациентом','РЕЗУЛЬТАТ СКРИНИНГА','ОЦЕНКА РИСКА','Вопрос','Ответ','Не указано','Не назначено','Дополнительных примечаний нет.','Уровень глюкозы','Версия модели','Учебная оценка скрининга. Этот результат не является медицинским диагнозом.','Примечания и дополнительные вопросы приведены для справки и не меняют оценку модели.','Учебный скрининг. Этот отчёт не является медицинским диагнозом.']}
EXTRA_ACTIVITY={
'fr':['HISTORIQUE D’ACTIVITÉ DU PATIENT','Autorité','Référence de la demande','Autorisation médicale','Approuvé par','Objet','Créé UTC','Heure / source','Action / utilisateur / détails','Aucun événement enregistré','Contient uniquement les événements enregistrés dans l’application. Ne prouve pas toutes les actions ni une autorisation légale.'],
'de':['AKTIVITÄTSPROTOKOLL DES PATIENTEN','Behörde','Anfragereferenz','Medizinische Genehmigung','Genehmigt von','Zweck','Erstellt UTC','Zeit / Quelle','Aktion / Benutzer / Details','Keine Ereignisse erfasst','Enthält nur erfasste Anwendungsereignisse. Kein Nachweis aller Handlungen oder einer rechtlichen Genehmigung.'],
'tr':['HASTA ETKİNLİK KAYDI','Yetkili kurum','Talep referansı','Tıbbi izin','Onaylayan','Amaç','Oluşturulma UTC','Zaman / kaynak','İşlem / kullanıcı / ayrıntılar','Kayıtlı olay yok','Yalnızca kayıtlı uygulama olaylarını içerir. Tüm eylemlerin veya yasal yetkinin kanıtı değildir.'],
'pt':['REGISTO DE ATIVIDADE DO PACIENTE','Autoridade','Referência do pedido','Autorização médica','Aprovado por','Finalidade','Gerado UTC','Hora / fonte','Ação / utilizador / detalhes','Sem eventos registados','Contém apenas eventos registados na aplicação. Não comprova todas as ações nem autorização legal.'],
'ru':['ЖУРНАЛ АКТИВНОСТИ ПАЦИЕНТА','Орган','Номер запроса','Медицинское разрешение','Кем одобрено','Цель','Создано UTC','Время / источник','Действие / пользователь / сведения','События не зарегистрированы','Содержит только зарегистрированные события приложения. Не доказывает все действия или законность разрешения.']}
for _lang,_values in EXTRA_VALUES.items():
    if len(_values)!=len(KEYS):raise ValueError('Incomplete report labels: '+_lang)
    LABELS[_lang]=dict(zip(KEYS,_values))
    LABELS[_lang].update(zip(ACTIVITY_KEYS,EXTRA_ACTIVITY[_lang]))
