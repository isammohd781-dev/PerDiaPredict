"""Public policy pages describing the actual development-stage application."""
from html import escape
VERSION='2026-10-01.1'
LABELS={
'en':('Program policy','Privacy policy','Read our','and','Back','Development version','Updated 1 October 2026','Deployment details','Not configured for this development deployment','Contents'),
'ar':('سياسة البرنامج','سياسة الخصوصية','اقرأ','و','العودة','نسخة قيد التطوير','آخر تحديث: 1 أكتوبر 2026','بيانات الجهة المشغّلة','لم يُحدَّد لهذه النسخة التطويرية','المحتويات'),
'es':('Política del programa','Política de privacidad','Lee nuestra','y','Volver','Versión en desarrollo','Actualizado el 1 de octubre de 2026','Datos de la instalación','No configurado para esta instalación de desarrollo','Contenido'),
'hi':('कार्यक्रम की नीति','गोपनीयता नीति','पढ़ें','और','वापस','विकासाधीन संस्करण','अपडेट: 1 अक्टूबर 2026','स्थापना की जानकारी','इस विकासाधीन स्थापना के लिए निर्धारित नहीं','विषय सूची'),
'zh':('程序使用政策','隐私政策','请阅读','和','返回','开发版本','更新于 2026 年 10 月 1 日','部署信息','此开发部署尚未配置','目录')}

TERMS={
'en':'''Purpose and development status|PerdiaPredict provides educational diabetes screening, saved reports and patient/doctor follow-up tools. This version is under development and intended for local testing with synthetic information. It is not represented as approved for public clinical deployment. A future release requires the operator to complete clinical, security and applicable regulatory reviews.
Medical limitations and emergencies|A risk estimate is not a diagnosis, prescription, treatment plan or guarantee that a disease is present or absent. Low scores do not exclude illness. Consult a qualified clinician about symptoms and decisions. This application does not provide emergency monitoring; use appropriate local emergency services when needed.
How the estimate works|The trained screening pipeline uses its configured model features, including age, sex and selected symptoms. The displayed probability and threshold are model outputs, not an independently validated personal clinical risk. Additional notes, glucose entries and extra questions can appear in reports without changing that pipeline score. The model version is recorded when available.
Accounts and accurate information|Provide accurate information and keep your password private. Do not impersonate another patient or doctor. Account identifiers help match stored assessments to their owner. Required fields support account creation and screening; optional photos and additional notes may be left empty. Contact support for account recovery; this version does not provide independently verified recovery for every deployment.
Patients, children and representatives|Use your own account and avoid entering another person's information without proper authority. Model-supported ages do not establish eligibility or consent capacity. This version has no complete guardian-consent or representative-verification workflow; do not treat it as ready for unsupervised real-patient use by children or dependants.
Doctor registration and responsibilities|Doctor accounts submit identity, specialty, licensing and hospital information and require administrator review. Review is a workflow step, not independent verification of qualifications. A doctor is responsible for accurate professional information, current hospital details, confidentiality and appropriate clinical judgement. A pending or suspended account does not have the same access as an approved active doctor.
Care connections and travel|A patient can connect to several doctors. Patient consent and doctor acceptance establish an active connection; access is checked against the connection. Travel or a shared hospital does not automatically grant a new doctor access. Update your country/hospital when appropriate. Revoking a connection restricts future application access but does not recall previously obtained copies.
Reports and additional notes|Completed assessments may be saved to history and exported as individual or combined PDFs. Review patient ID, date, notes and model information before sharing. Patient notes are patient statements, not verified findings; doctor notes are separate follow-up information. A PDF is a snapshot and may differ from a subsequently edited profile. Older snapshots are not silently translated or rewritten.
Acceptable use|Do not attempt unauthorised access, scrape patient records, share passwords, upload malicious files, impersonate professionals or use the application to discriminate. Only upload permitted profile images and information you have authority to provide. Do not expose passwords, private configurations or patient databases in a public source-code repository.
Administrative and governmental disclosure|The restricted Reports/Activity sections require configured verification and a permit covering the selected country, patient and scope. An entry in configuration is not evidence of genuine medical approval or a legally valid government request. A responsible operator must independently verify the request, authority and lawful scope before disclosure. Country-wide permits can cover current and future patients and require particular care.
Availability, changes and responsibility|The development service can contain errors, incomplete translations or interruptions. Protect downloaded reports and use independent clinical verification. Features and model versions may change. No term here waives rights that cannot be waived under applicable law. This version has no complete subscription, billing, refund or service-level scheme.
Contact and policy updates|Use the deployment contact details shown below for questions, correction requests or concerns. This page has a version and update date; material changes should be communicated by the operator before applying a new purpose to existing data. Reading or visiting this page is not recorded as a new consent, and opening a link does not authorise disclosure.''',
'ar':'''الغرض وحالة التطوير|يوفر PerdiaPredict فحصًا تعليميًا لخطر السكري وتقارير محفوظة وأدوات لمتابعة المريض مع الطبيب. النسخة الحالية قيد التطوير ومخصّصة للاختبار المحلي ببيانات تجريبية. لا يُقدَّم التطبيق باعتباره معتمدًا للاستخدام الطبي العام. يتطلب الإطلاق المستقبلي استكمال المراجعة الطبية والأمنية والمتطلبات التنظيمية المناسبة بواسطة الجهة المشغّلة.
حدود التقييم والطوارئ|تقدير الخطر ليس تشخيصًا أو وصفة أو خطة علاج أو ضمانًا لوجود المرض أو غيابه. النتيجة المنخفضة لا تستبعد المرض. استشر طبيبًا مؤهّلًا بشأن الأعراض والقرارات الصحية. لا يقدم التطبيق مراقبة للطوارئ؛ استخدم خدمات الطوارئ المحلية المناسبة عند الحاجة.
كيفية حساب التقدير|تستخدم منظومة الفحص المدرّبة الخصائص المحدّدة في النموذج، ومنها العمر والجنس والأعراض المختارة. النسبة والحد الفاصل مخرجات للنموذج وليسا تقديرًا سريريًا فرديًا تم التحقق منه بصورة مستقلة. قد تظهر الملاحظات وقراءة السكر والأسئلة الإضافية في التقرير دون تغيير نتيجة النموذج. يُذكر إصدار النموذج عندما يكون متاحًا.
الحساب وصحة المعلومات|أدخل بيانات صحيحة واحفظ كلمة المرور بسرية ولا تنتحل هوية مريض أو طبيب. يساعد الرقم التعريفي على ربط التقييمات بصاحبها. الحقول المطلوبة لازمة للحساب والفحص؛ ويمكن ترك الصورة والملاحظات الاختيارية فارغة. تواصل مع الدعم لاستعادة الحساب؛ لا توجد آلية استعادة مستقلة ومتحقق منها لكل بيئة تشغيل في هذه النسخة.
الأطفال ومن ينوب عن المريض|استخدم حسابك ولا تدخل بيانات شخص آخر دون صلاحية مناسبة. نطاق العمر الذي يقبله النموذج لا يثبت أهلية الاستخدام أو القدرة على الموافقة. لا تتضمن النسخة الحالية مسارًا متكاملًا لموافقة ولي الأمر أو التحقق من الممثل؛ لذلك لا تعتبر جاهزة للاستخدام الحقيقي غير المشرف عليه للأطفال أو من يعتمدون على غيرهم.
تسجيل الطبيب ومسؤوليته|يقدّم الطبيب بيانات الهوية والتخصص والترخيص والمستشفى، ويخضع حسابه لمراجعة الإدارة. المراجعة خطوة تشغيلية ولا تثبت المؤهلات بصورة مستقلة. يتحمل الطبيب مسؤولية دقة بياناته ومكان عمله والحفاظ على السرية والحكم السريري المناسب. الحساب المعلّق أو الموقوف لا يملك صلاحيات الطبيب المعتمد صاحب العلاقة النشطة.
المتابعة مع عدة أطباء والسفر|يمكن للمريض متابعة أكثر من طبيب. تنشأ العلاقة النشطة بعد موافقة المريض وقبول الطبيب، ويُفحص الارتباط عند الوصول. السفر أو وجود الطبيب في المستشفى نفسه لا يمنحه الوصول تلقائيًا. حدّث الدولة والمستشفى عند الحاجة. إلغاء العلاقة يقيّد الوصول اللاحق داخل التطبيق ولا يسترجع النسخ التي سبق الحصول عليها.
التقارير والملاحظات|يمكن حفظ التقييمات المكتملة وتصديرها كملفات PDF فردية أو مجمّعة. راجع رقم المريض والتاريخ والملاحظات ومعلومات النموذج قبل المشاركة. ملاحظات المريض إفادته الشخصية وليست نتائج طبية متحققًا منها، وملاحظات الطبيب معلومات متابعة منفصلة. التقرير نسخة ثابتة وقد يختلف عن الملف الشخصي بعد تعديله. لا يعاد تغيير المحتوى القديم أو ترجمته تلقائيًا.
الاستخدام المقبول|يُمنع الوصول غير المصرّح به أو جمع سجلات المرضى أو مشاركة كلمات المرور أو رفع ملفات ضارة أو انتحال صفة الطبيب أو الاستخدام التمييزي. ارفع الصور المسموحة والمعلومات التي تملك صلاحية تقديمها فقط. لا تنشر كلمات المرور أو إعدادات الوصول الخاصة أو قواعد بيانات المرضى في مستودع كود عام.
الإفصاح الإداري والطلبات الحكومية|تتطلب أقسام التقارير والنشاط المقيّدة تحققًا وتصريحًا مضبوطًا للدولة والمريض والنطاق المطلوب. إدخال تصريح في الإعدادات لا يثبت موافقة طبية فعلية أو طلبًا حكوميًا مشروعًا. يجب على المشغّل المسؤول التحقق المستقل من الجهة والطلب والنطاق القانوني قبل الإفصاح. قد يشمل تصريح الدولة جميع المرضى الحاليين والمستقبليين، ويجب ضبطه بعناية.
التوفر والتغييرات والمسؤولية|قد تتضمن الخدمة التطويرية أخطاء أو ترجمة غير مكتملة أو توقفًا. احمِ التقارير المنزلة واعتمد التحقق الطبي المستقل. قد تتغير الوظائف وإصدارات النموذج. لا تلغي هذه السياسة حقوقًا لا يجوز التنازل عنها وفق القانون المنطبق. لا توجد منظومة متكاملة للاشتراكات أو الفوترة أو الاسترداد أو ضمان مستوى الخدمة في هذه النسخة.
التواصل وتحديث السياسة|استخدم بيانات التواصل الموضحة أدناه للأسئلة وطلبات التصحيح والشكاوى. تتضمن الصفحة إصدارًا وتاريخ تحديث؛ وينبغي للمشغّل إبلاغ المستخدم بالتغييرات الجوهرية قبل تطبيق غرض جديد على بياناته السابقة. لا تُسجَّل قراءة الصفحة كموافقة جديدة، ولا يمنح فتح الرابط إذنًا للإفصاح.''',
'es':'''Finalidad y desarrollo|PerdiaPredict ofrece evaluación educativa, informes y seguimiento. La versión actual es para pruebas locales con datos sintéticos; no se presenta como aprobada para uso clínico público. El operador debe completar las revisiones necesarias antes del lanzamiento.
Límites médicos y emergencias|La estimación no diagnostica, prescribe ni garantiza ausencia de enfermedad. Un resultado bajo no descarta enfermedad. Consulta a un profesional y usa servicios locales de emergencia cuando corresponda; no hay vigilancia de emergencias.
Cálculo del riesgo|El modelo usa las características configuradas, como edad, sexo y síntomas. La probabilidad no es un riesgo clínico individual validado independientemente. Notas, glucosa y preguntas extra pueden aparecer sin modificar el resultado. Se registra la versión disponible.
Cuentas e información|Proporciona datos correctos y protege tu contraseña. No suplantes identidades. Los identificadores vinculan evaluaciones con su titular. Fotos y notas son opcionales. La recuperación depende del soporte; no existe recuperación independiente verificada para todas las instalaciones.
Menores y representantes|No introduzcas datos ajenos sin autoridad. El rango de edad del modelo no acredita capacidad de consentimiento. No existe un proceso completo de consentimiento de tutores ni verificación de representantes; no está listo para uso real no supervisado con menores.
Médicos y responsabilidades|El registro médico requiere revisión administrativa de identidad, especialidad, licencia y hospital. No verifica credenciales independientemente. Los médicos deben mantener datos correctos, confidencialidad y criterio profesional. Cuentas pendientes o suspendidas tienen acceso restringido.
Conexiones y viajes|Puedes conectar varios médicos mediante consentimiento y aceptación. Viajar o compartir hospital no concede acceso automático. Actualiza país y hospital. Revocar una conexión limita acceso futuro, pero no recupera copias obtenidas anteriormente.
Informes y notas|Las evaluaciones completadas pueden guardarse y exportarse en PDF. Revisa ID, fecha y notas antes de compartir. Las notas del paciente no son hallazgos verificados. Los PDF son instantáneas; perfiles posteriores no los reescriben ni traducen.
Uso permitido|No accedas sin permiso, extraigas registros, compartas contraseñas, cargues archivos maliciosos ni suplantes profesionales. Usa datos e imágenes autorizados. No publiques bases de pacientes, secretos ni contraseñas en repositorios públicos.
Divulgación administrativa|Los informes y eventos requieren verificación y permisos con paciente, país y alcance. Una configuración no prueba aprobación médica ni solicitud gubernamental válida. El operador debe comprobar autoridad y legalidad. Permisos por país pueden incluir pacientes presentes y futuros.
Disponibilidad y cambios|Pueden existir errores, traducciones incompletas y interrupciones. Protege informes y verifica decisiones clínicamente. Funciones y modelos pueden cambiar. No se excluyen derechos irrenunciables. No existe un sistema completo de facturación, reembolso o nivel de servicio.
Contacto y actualizaciones|Usa los datos de contacto de la instalación. La política tiene versión y fecha; cambios materiales deben comunicarse antes de nuevos usos de datos. Leer la página no registra un consentimiento nuevo ni autoriza divulgación.''',
'hi':'''उद्देश्य और विकास|PerdiaPredict शैक्षिक जांच, रिपोर्ट और डॉक्टर के साथ देखभाल के उपकरण देता है। वर्तमान संस्करण केवल स्थानीय काल्पनिक डेटा परीक्षण के लिए है। सार्वजनिक चिकित्सा उपयोग की स्वीकृति का दावा नहीं है; जारी करने से पहले आवश्यक समीक्षाएं पूरी करनी होंगी।
चिकित्सा सीमाएं और आपातकाल|अनुमान निदान, नुस्खा या रोग होने अथवा न होने की गारंटी नहीं है। कम स्कोर बीमारी को नहीं नकारता। डॉक्टर से सलाह लें। जरूरत पर स्थानीय आपातकाल सेवाएं लें; ऐप आपातकाल की निगरानी नहीं करता।
जोखिम की गणना|मॉडल निर्धारित आयु, लिंग और लक्षण जैसी विशेषताएं इस्तेमाल करता है। प्रतिशत स्वतंत्र रूप से मान्य व्यक्तिगत चिकित्सा जोखिम नहीं है। अतिरिक्त नोट्स, ग्लूकोज़ और प्रश्न रिपोर्ट में आ सकते हैं पर मॉडल स्कोर नहीं बदलते। उपलब्ध मॉडल संस्करण दर्ज होता है।
खाता और जानकारी|सही जानकारी दें और पासवर्ड निजी रखें। दूसरे व्यक्ति की पहचान न लें। पहचान संख्या मूल्यांकन को मालिक से जोड़ती है। फोटो और नोट्स वैकल्पिक हैं। खाता वापस पाने के लिए सहायता लें; सभी स्थापनाओं के लिए स्वतंत्र सत्यापित प्रक्रिया नहीं है।
बच्चे और प्रतिनिधि|अधिकार के बिना किसी और की जानकारी न दें। मॉडल की आयु सीमा सहमति की क्षमता नहीं बताती। अभिभावक की सहमति और प्रतिनिधि की जांच की पूरी व्यवस्था नहीं है; बच्चों का वास्तविक बिना निगरानी उपयोग तैयार नहीं है।
डॉक्टर की जिम्मेदारी|डॉक्टर की पहचान, विशेषज्ञता, लाइसेंस और अस्पताल की प्रशासनिक समीक्षा होती है, स्वतंत्र योग्यता सत्यापन नहीं। डॉक्टर सही जानकारी, गोपनीयता और उचित निर्णय के जिम्मेदार हैं। लंबित या निलंबित खाते का प्रवेश सीमित है।
संबंध और यात्रा|सहमति और डॉक्टर की स्वीकृति से कई डॉक्टर जुड़ सकते हैं। यात्रा या समान अस्पताल अपने आप प्रवेश नहीं देता। देश और अस्पताल अपडेट करें। संबंध हटाना भविष्य का प्रवेश सीमित करता है, पुरानी प्रतियां नहीं लौटाता।
रिपोर्ट और नोट्स|पूर्ण मूल्यांकन सुरक्षित कर PDF में निकाले जा सकते हैं। साझा करने से पहले पहचान, तारीख और नोट्स जांचें। रोगी के नोट्स सत्यापित निष्कर्ष नहीं हैं। PDF उस समय की प्रति है; बाद की प्रोफ़ाइल पुरानी रिपोर्ट नहीं बदलती या अनुवाद करती।
स्वीकार्य उपयोग|बिना अनुमति प्रवेश, रिकॉर्ड निकालना, पासवर्ड साझा करना, हानिकारक फ़ाइल या नकली पहचान निषिद्ध है। केवल अधिकृत डेटा और फोटो दें। निजी डेटाबेस और रहस्य सार्वजनिक कोड संग्रह में न डालें।
प्रशासनिक जानकारी देना|रिपोर्ट और गतिविधि के लिए निर्धारित प्रवेश तथा रोगी, देश और दायरे की अनुमति जांच चाहिए। सेटिंग वास्तविक चिकित्सा स्वीकृति या वैध सरकारी अनुरोध का प्रमाण नहीं है। संचालक को स्वतंत्र जांच करनी होगी। देश की अनुमति भविष्य के रोगियों तक भी पहुंच सकती है।
उपलब्धता और बदलाव|त्रुटियां, अधूरा अनुवाद और रुकावट संभव हैं। रिपोर्ट सुरक्षित रखें और चिकित्सकीय निर्णय की स्वतंत्र जांच करें। सुविधाएं बदल सकती हैं। कानून से मिले अनिवार्य अधिकार नहीं हटते। पूरी बिलिंग, वापसी या सेवा स्तर व्यवस्था नहीं है।
संपर्क और अपडेट|नीचे स्थापना के संपर्क से सवाल या शिकायत करें। संस्करण और तारीख दी गई हैं; डेटा का नया उपयोग पहले बताया जाना चाहिए। पेज पढ़ना नई सहमति दर्ज नहीं करता और जानकारी साझा करने की अनुमति नहीं देता।''',
'zh':'''用途与开发状态|PerdiaPredict 提供教育性筛查、报告和医生随访工具。目前仅用于本地虚构数据测试，不声称获公共临床使用批准。运营者应在发布前完成必要审查。
医学限制与急救|估计不是诊断、处方或疾病存在与否的保证。低分不能排除疾病。请咨询医生；紧急情况使用本地急救服务。应用不提供急救监测。
估计方式|模型使用配置的年龄、性别和症状等特征。百分比不是独立验证的个人临床风险。备注、血糖和额外问题可以显示在报告中而不改变模型分数。可用时记录模型版本。
账户与资料|提供准确信息并保护密码，不得冒用身份。编号用于关联账户和评估。照片与备注为可选。账户恢复需要支持渠道；所有部署均无完整独立验证恢复机制。
儿童与代理人|无授权不得输入他人资料。模型年龄范围不代表同意能力。当前没有完整监护人同意与代理人核验流程，不能视为适合儿童无人监督的真实使用。
医生职责|医生身份、专业、许可和医院需管理员审核，但不构成独立资质验证。医生负责资料准确、保密与专业判断。待审核或暂停账户访问受限。
照护关系与旅行|患者可在同意和医生接受后连接多位医生。旅行或同院不会自动授予访问。请更新国家和医院。撤销关系限制未来访问，不能收回已有副本。
报告与备注|完成的评估可保存并导出 PDF。分享前核对编号、日期与备注。患者备注不是经核实的医学发现。PDF 是快照，之后的资料修改不会重写或翻译旧报告。
允许的使用|不得未授权访问、抓取记录、分享密码、上传恶意文件、冒用专业身份或歧视。只提供有权提交的数据和照片，不得将患者数据库或秘密上传公共代码仓库。
管理披露|报告和活动记录需要配置的验证及匹配患者、国家、范围的许可。设置本身不能证明医疗批准或合法政府请求。运营者须独立核验。国家范围许可可能包括未来患者。
可用性与变更|可能存在错误、翻译遗漏和中断。请保护下载报告并独立核实医疗决定。功能和模型可能改变。不能放弃的法定权利不受排除。无完整收费、退款或服务等级机制。
联系与更新|通过下方部署联系方式提问或投诉。政策包含版本和日期，重要数据用途变更应预先通知。阅读页面不记录新的同意，也不授权披露。'''}
PRIVACY={
'en':'''Operator and scope|This notice covers the data handled by this application version. The responsible organisation, contact address, hosting location and processing basis depend on the deployment and must be specified below before real-patient launch. Project branding is not proof of an incorporated healthcare provider or regulatory registration.
Account and professional data|Patient data can include account ID, patient ID, name, email, birth date/age, sex/gender, relationship status, country, phone, declared diabetes type and optional uploaded profile photo. Doctor data can include name, email, phone, specialty, licensing identifiers, licensing body, country, city, hospital, approval state and current work information.
Health and follow-up data|We handle symptom answers, additional questions, glucose entries where supplied, free-text patient notes, model score/threshold/version, timestamps, report snapshots, care requests, active/revoked connections and doctor notes. Do not include unrelated third-party identities, passwords or unnecessary sensitive information in free-text notes.
Events, credentials and technical information|The application records selected login/account actions, navigation, assessments, care actions and restricted report access/export preparation. Activity records are incomplete and are not proof of every movement. Credentials are stored using password hashes; this does not encrypt the associated account or health records. Hosting infrastructure may separately process IP addresses, session data and security logs according to its configuration.
Sources and purposes|Data comes from the patient, participating doctors, account/profile changes and generated application events. We use it to manage accounts, run educational screening, display/export reports, maintain consented follow-up and review access. Required data cannot be omitted when a dependent feature needs it; optional notes and photos are not required. We do not claim any unspecified research purpose.
Model processing and human review|The configured model performs automated screening inference locally in the application server process. The score should be reviewed with a clinician and must not be the sole basis for treatment, insurance, employment or eligibility decisions. This code does not automatically retrain the model on saved patient assessments or send them to a conversational AI service.
Patient/doctor access|Patients see their own completed history. Connected approved doctors can view permitted records through an active care relationship; a shared country/hospital filter does not replace consent. Several doctors may be connected at once. Revocation restricts subsequent application access, without deleting previously exported or independently retained material.
Administrator and authority access|Administrators manage account directories and doctor review. Restricted reports/activity require an independent configured password and a matching permit. Access is temporary and checked again for the selected subject. Group permits may cover listed people or all current/future patients in a country. Configured approval does not verify external documents or establish a legal basis; the responsible operator must validate requests independently and minimise disclosed data.
Storage and security limitations|Account/audit spreadsheets, SQLite history/care/audit databases and uploaded photo files are stored on the application server. Data is not encrypted at rest in this version; the machine, configuration or source-code owner can bypass application gates. Password hashing, lockouts, per-patient checks and consent workflows reduce some access risks but do not provide complete security. TLS, backups, separate custody and operational safeguards depend on deployment.
Retention, deletion and backups|No automatic timed deletion or complete self-service erasure workflow is implemented. Data can persist until an authorised operator removes it from all relevant stores. Deleting an account file alone does not necessarily erase report history, care notes, photos, audit records, backups or exported PDFs. The operator must define retention periods or criteria, exceptions, backup expiry and a verified deletion process before launch; no duration is invented here.
Your requests and account recovery|You may ask the operator to explain, provide a copy of, correct or delete your data, restrict use, review a model result or address a complaint. Which rights and exceptions apply depends on the governing law and verified request. Identity verification should be proportionate and use a secure channel. This version does not automate all requests, provide a guaranteed response deadline or offer account recovery through ordinary administrator backup controls.
Sessions, cookies and external links|Streamlit/server infrastructure may use session or technical cookies; this source alone cannot establish the entire deployed cookie inventory. No advertising tracker is deliberately added by this policy feature. Opening the optional WhatsApp support link connects to an external service with its own privacy practices. Do not send health reports, passwords or identity documents through support chat unless a secure authorised process has been established.
Hosting, transfers and third parties|Hosting operators, authorised maintenance staff and backup systems may have technical access depending on deployment. Server country, subprocessors, contractual controls and transfer safeguards have not been supplied here. Changing a patient's country does not itself migrate storage or authorise an international disclosure. The application does not implement a data-sale or advertising service; the deployment operator must confirm any added integrations.
Children and sensitive information|Health records and photos can be sensitive. Supported model ages do not establish consent eligibility. Guardian verification, representation rules and legal bases for real child/sensitive-data use remain to be established. Use synthetic data in development; this notice does not create a verified guardian-consent process.
Incidents and complaints|Report suspected account compromise, inappropriate doctor access or unintended disclosure promptly through the deployment contact. Do not send passwords or full medical files in an initial report. A documented incident assessment, containment, notification and regulator-complaint process must be established by the operator according to applicable law; this build does not provide automatic breach detection or legal notifications.
Changes and outstanding deployment details|This notice is versioned and may change with features, hosting or data purposes. Changes should be communicated before new processing where required. Viewing these pages neither records new consent nor accepts governmental disclosure. Responsible-operator identity, lawful basis for health data, contacts, retention rules, hosting/vendors, applicable jurisdiction and reviewed launch approvals must be completed for the actual deployment.''',
'ar':'''الجهة المشغّلة ونطاق السياسة|تصف هذه السياسة البيانات التي تتعامل معها نسخة التطبيق الحالية. يجب تحديد المؤسسة المسؤولة وعنوان التواصل ومكان الاستضافة وأساس معالجة البيانات بحسب بيئة التشغيل قبل إطلاقه لمرضى حقيقيين. اسم المشروع أو شعاره لا يثبت تسجيل مؤسسة رعاية صحية أو حصولها على تصريح تنظيمي.
بيانات الحساب والطبيب|قد تشمل بيانات المريض رقم الحساب ورقم المريض والاسم والبريد وتاريخ الميلاد أو العمر والجنس والحالة الاجتماعية والدولة والهاتف ونوع السكري المذكور والصورة الاختيارية المرفوعة. وقد تشمل بيانات الطبيب الاسم والبريد والهاتف والتخصص وأرقام الترخيص وجهة الترخيص والدولة والمدينة والمستشفى وحالة الاعتماد ومكان العمل الحالي.
المعلومات الصحية والمتابعة|يتعامل التطبيق مع إجابات الأعراض والأسئلة الإضافية وقراءة السكر عند إدخالها والملاحظات الحرة والنسبة والحد الفاصل وإصدار النموذج والتواريخ ونسخ التقارير وطلبات المتابعة والعلاقات النشطة أو الملغاة وملاحظات الطبيب. لا تكتب بيانات أشخاص آخرين أو كلمات مرور أو معلومات حساسة غير لازمة داخل الملاحظات.
الأحداث وكلمات المرور والبيانات التقنية|يسجل التطبيق بعض إجراءات الدخول والحساب والتنقل والتقييم والمتابعة والوصول المقيّد وتجهيز التصدير. سجل النشاط غير كامل ولا يثبت كل تحركات المستخدم. تحفظ بيانات التحقق بكلمات المرور على هيئة تجزئات؛ وهذا لا يشفّر بقية بيانات الحساب أو الصحة. قد تعالج الاستضافة بصورة منفصلة عناوين الشبكة ومعلومات الجلسة والسجلات الأمنية حسب إعداداتها.
مصادر البيانات وأغراض استخدامها|تأتي البيانات من المريض والأطباء المشاركين وتعديلات الحساب والأحداث التي ينشئها التطبيق. تستخدم لإدارة الحساب والفحص التعليمي وعرض التقارير وتصديرها والمتابعة الموافق عليها ومراجعة الوصول. لا يمكن ترك البيانات المطلوبة فارغة عندما تعتمد عليها وظيفة محددة؛ الملاحظات والصور اختيارية. لا تفترض هذه السياسة وجود غرض بحثي غير محدّد.
النموذج والمراجعة البشرية|يجري النموذج المضبوط تقدير الفحص آليًا داخل عملية خادم التطبيق. ينبغي مراجعة النتيجة مع الطبيب، ولا يجوز الاعتماد عليها وحدها لاتخاذ قرار علاجي أو تأميني أو وظيفي أو قرار أهلية. لا يعيد الكود تدريب النموذج تلقائيًا ببيانات التقييمات المحفوظة، ولا يرسلها إلى خدمة ذكاء اصطناعي للمحادثة.
وصول المريض والطبيب|يطلع المريض على تقييماته المكتملة. يستطيع الطبيب المعتمد المرتبط بعلاقة نشطة الوصول إلى السجلات المسموحة؛ فلتر المستشفى أو الدولة لا يحل محل الموافقة. يمكن ربط عدة أطباء في الوقت نفسه. يقيّد إلغاء العلاقة الوصول اللاحق داخل التطبيق، ولا يحذف تلقائيًا ما سبق تصديره أو الاحتفاظ به خارج التطبيق.
وصول الإدارة والجهات الطالبة|تدير الإدارة دليل الحسابات ومراجعة الأطباء. يتطلب الوصول للتقارير والنشاط المقيّد كلمة مرور مستقلة وتصريحًا مطابقًا. يكون الوصول مؤقتًا ويُعاد فحصه للمريض المختار. قد يغطي التصريح الجماعي أشخاصًا محددين أو جميع مرضى الدولة الحاليين والمستقبليين. علامة الموافقة في الإعدادات لا تتحقق من الوثائق أو تنشئ أساسًا قانونيًا؛ يجب على المشغّل التحقق المستقل وتقليل البيانات المفصح عنها.
التخزين وحدود الحماية|تُخزّن ملفات الحساب والتدقيق وقواعد SQLite للتاريخ والمتابعة والتدقيق وملفات الصور على خادم التطبيق. لا يوجد تشفير للبيانات المخزنة في هذه النسخة، ويمكن لمالك الجهاز أو الإعدادات أو الكود تجاوز قيود الواجهة. تقلل تجزئة كلمات المرور والقفل المؤقت والتحقق من المريض وعلاقات الموافقة بعض المخاطر لكنها لا توفر حماية كاملة. يعتمد الاتصال المشفّر والنسخ الاحتياطي والحفظ المستقل على إعداد التشغيل.
مدة الاحتفاظ والحذف والنسخ الاحتياطية|لا يوجد حذف تلقائي بعد مدة معينة أو مسار متكامل للحذف الذاتي. قد تبقى البيانات حتى يحذفها مشغّل مخوّل من جميع أماكن التخزين ذات الصلة. حذف ملف الحساب وحده لا يضمن حذف التاريخ والملاحظات والصور والتدقيق والنسخ الاحتياطية وملفات PDF. يجب تحديد المدد أو معايير الاحتفاظ والاستثناءات وانتهاء النسخ وآلية تحقق من الحذف قبل الإطلاق؛ لا نفترض مدة غير محددة فعليًا.
طلبات المستخدم واستعادة الحساب|يمكنك طلب شرح البيانات أو نسخة منها أو تصحيحها أو حذفها أو تقييد استخدامها أو مراجعة نتيجة النموذج أو معالجة شكوى. تتوقف الحقوق والاستثناءات على القانون المنطبق والتحقق من الطلب. ينبغي التحقق من الهوية بالقدر اللازم عبر قناة آمنة. لا تؤتمت هذه النسخة جميع الطلبات ولا تضمن مهلة استجابة محددة، ولا توفر الاستعادة عبر نسخ حسابات الإدارة العادية.
الجلسات والكوكيز والروابط الخارجية|قد تستخدم Streamlit أو الاستضافة بيانات جلسة أو ملفات كوكيز تقنية؛ ولا يحدد هذا الكود وحده جميع كوكيز النسخة المنشورة. لا تضيف هذه الوظيفة أدوات تتبع إعلانية. فتح رابط دعم WhatsApp الاختياري ينقلك إلى خدمة خارجية لها ممارسات خصوصية مستقلة. لا ترسل تقارير صحية أو كلمات مرور أو وثائق هوية عبر دردشة الدعم دون مسار آمن ومصرح به.
الاستضافة والنقل والأطراف الأخرى|قد تتمكن جهة الاستضافة وأفراد الصيانة المخوّلون وأنظمة النسخ الاحتياطي من الوصول تقنيًا بحسب التشغيل. لم تُقدّم هنا دولة الخادم أو الجهات الفرعية أو الضوابط التعاقدية أو ضمانات النقل. تعديل دولة المريض لا ينقل التخزين تلقائيًا ولا يأذن بإفصاح دولي. لا يتضمن التطبيق خدمة لبيع البيانات أو الإعلان؛ ويجب على المشغّل بيان أي تكاملات تضاف لاحقًا.
الأطفال والبيانات الحساسة|قد تكون البيانات الصحية والصور حساسة. نطاق عمر النموذج لا يثبت أهلية الموافقة. لم يكتمل تحديد التحقق من ولي الأمر وقواعد التمثيل وأسس الاستخدام الحقيقي لبيانات الأطفال والصحة. استخدم بيانات تجريبية أثناء التطوير؛ ولا تنشئ هذه السياسة مسار موافقة ولي أمر متحققًا منه.
الحوادث والشكاوى|أبلغ عن اختراق الحساب أو وصول طبيب غير مناسب أو إفصاح غير مقصود عبر التواصل المخصص للتشغيل. لا ترسل كلمة مرور أو الملف الطبي كاملًا في البلاغ الأول. يجب على المشغّل وضع إجراءات موثقة للتقييم والاحتواء والإبلاغ والشكاوى للجهة المختصة بحسب القانون المنطبق؛ لا ينفذ هذا الإصدار كشف الاختراق أو الإبلاغ القانوني آليًا.
التحديثات والبيانات التي تحتاج إلى استكمال|قد تتغير السياسة بتغير الوظائف والاستضافة والأغراض، ويجب الإبلاغ قبل المعالجة الجديدة حيث يلزم. لا تسجّل مشاهدة الصفحات موافقة جديدة ولا قبولًا بالإفصاح الحكومي. يجب استكمال هوية المسؤول وأساس معالجة بيانات الصحة وبيانات التواصل ومدد الاحتفاظ والاستضافة والجهات المساعدة والدولة القانونية والمراجعات اللازمة لإطلاق النسخة الفعلية.''',
'es':'''Responsable y alcance|La organización responsable, contactos, base de procesamiento y ubicación del servidor deben identificarse antes de usar datos reales. La marca no demuestra registro sanitario ni aprobación.
Datos de cuentas y médicos|Se manejan ID, nombres, correo, fecha de nacimiento/edad, sexo, estado civil, país, teléfono, diabetes declarada y foto opcional. Médicos aportan identidad, especialidad, licencia, hospital y estado de revisión.
Salud y seguimiento|Se guardan respuestas, glucosa proporcionada, notas, puntuación, umbral, versión, fechas, informes, conexiones y notas médicas. Evita datos ajenos, contraseñas e información sensible innecesaria en texto libre.
Eventos y datos técnicos|Se registran algunas acciones y accesos/exportaciones; no todas las acciones. Las contraseñas usan hashes, sin cifrar el resto de los datos. La infraestructura puede procesar IP, sesiones y registros.
Fuentes y finalidades|Los datos proceden del paciente, médicos y acciones de la aplicación. Se usan para cuentas, evaluación, informes y seguimiento consentido. Campos obligatorios sostienen funciones; fotos/notas son opcionales. No se presupone investigación.
Modelo y revisión|El modelo genera la estimación en el servidor. No debe decidir tratamientos, seguros o empleo por sí solo. El código no reentrena automáticamente con registros ni los envía a un servicio de IA conversacional.
Acceso clínico|Pacientes ven su historial; médicos aprobados acceden mediante conexión activa consentida. Hospital/país no sustituye consentimiento. Se permiten varios médicos. Revocar limita acceso futuro, no recupera copias.
Acceso administrativo|Informes y actividad requieren contraseña independiente y permiso coincidente y temporal. Permisos colectivos pueden abarcar personas listadas o pacientes actuales/futuros del país. La configuración no verifica documentos ni establece legalidad; el operador debe validarlo.
Almacenamiento y protección|Hojas de cálculo, bases SQLite y fotos residen en el servidor sin cifrado en reposo. Su propietario puede eludir controles. Hashes, bloqueos y verificaciones reducen algunos riesgos; TLS, custodia y copias dependen de la instalación.
Retención y eliminación|No existe borrado automático ni eliminación personal completa. Borrar una cuenta no elimina necesariamente informes, notas, fotos, auditorías, copias o PDF. El operador debe definir plazos/criterios, excepciones y eliminación verificada antes del lanzamiento.
Solicitudes y recuperación|Solicita acceso, copia, corrección, eliminación, restricción, revisión o reclamación al operador. Derechos y excepciones dependen de la ley. Se requiere verificación proporcionada y segura. No hay automatización completa ni plazo garantizado.
Sesiones y enlaces|La infraestructura puede usar cookies técnicas; el inventario depende del despliegue. Esta función no añade seguimiento publicitario. WhatsApp es externo. No envíes contraseñas, documentos o informes por chat sin proceso seguro autorizado.
Alojamiento y transferencias|Proveedores, mantenimiento y copias pueden tener acceso técnico. País del servidor, proveedores y garantías no están especificados. Cambiar país del paciente no mueve almacenamiento ni autoriza transferencias. No hay servicio de venta de datos/publicidad; confirma integraciones añadidas.
Menores y datos sensibles|Salud/fotos pueden ser sensibles. La edad admitida no prueba capacidad de consentimiento. Faltan procesos completos de tutores y bases legales reales. Usa información sintética; este aviso no crea consentimiento verificado.
Incidentes y reclamaciones|Comunica sospechas mediante el contacto del despliegue sin contraseñas ni archivos completos inicialmente. El operador debe establecer contención, evaluación, notificaciones y reclamaciones aplicables. No hay detección o avisos legales automáticos.
Actualizaciones y pendientes|El aviso tiene versión y fecha. Comunica cambios antes de nuevos usos cuando corresponda. Leerlo no crea consentimiento ni autoriza divulgación. Deben completarse responsable, base legal, contactos, retención, proveedores, jurisdicción y aprobaciones reales.''',
'hi':'''संचालक और दायरा|वास्तविक डेटा से पहले जिम्मेदार संस्था, संपर्क, प्रक्रिया का आधार और सर्वर स्थान बताना होगा। ब्रांड स्वास्थ्य संस्था के पंजीकरण या स्वीकृति का प्रमाण नहीं है।
खाता और डॉक्टर डेटा|पहचान, नाम, ईमेल, जन्म/आयु, लिंग, वैवाहिक स्थिति, देश, फोन, घोषित मधुमेह और वैकल्पिक फोटो रखे जाते हैं। डॉक्टर की पहचान, विशेषज्ञता, लाइसेंस, अस्पताल और समीक्षा स्थिति भी रहती है।
स्वास्थ्य और देखभाल|उत्तर, दिया गया ग्लूकोज़, नोट्स, स्कोर, सीमा, मॉडल संस्करण, तारीख, रिपोर्ट, संबंध और डॉक्टर नोट्स रहते हैं। नोट्स में दूसरे की पहचान, पासवर्ड या अनावश्यक संवेदनशील डेटा न डालें।
घटनाएं और तकनीकी डेटा|कुछ कार्रवाइयां और प्रवेश/निर्यात तैयारी दर्ज होती हैं, हर गतिविधि नहीं। पासवर्ड हैश किए जाते हैं, अन्य डेटा एन्क्रिप्ट नहीं। स्थापना IP, सत्र और लॉग भी रख सकती है।
स्रोत और उद्देश्य|डेटा रोगी, डॉक्टर और ऐप की घटनाओं से आता है। खाते, शैक्षिक जांच, रिपोर्ट और सहमत देखभाल के लिए उपयोग होता है। जरूरी डेटा संबंधित सुविधा के लिए चाहिए; फोटो/नोट्स वैकल्पिक हैं। शोध का अनिर्दिष्ट उद्देश्य नहीं माना गया।
मॉडल और मानव समीक्षा|मॉडल सर्वर पर अनुमान देता है। अकेला स्कोर इलाज, बीमा या नौकरी का निर्णय नहीं करे। कोड अपने आप रिकॉर्ड से मॉडल फिर नहीं सिखाता और बातचीत की AI सेवा को डेटा नहीं भेजता।
रोगी और डॉक्टर प्रवेश|रोगी अपना इतिहास देखता है; स्वीकृत डॉक्टर सक्रिय सहमत संबंध से डेटा देखता है। अस्पताल/देश सहमति की जगह नहीं। कई डॉक्टर संभव हैं। संबंध हटाना पुरानी प्रतियां नहीं मिटाता।
प्रशासनिक प्रवेश|रिपोर्ट/गतिविधि में अलग पासवर्ड और संबंधित अस्थायी अनुमति चाहिए। समूह अनुमति सूची या देश के वर्तमान/भविष्य रोगियों को शामिल कर सकती है। सेटिंग दस्तावेज या कानूनी आधार सत्यापित नहीं करती; संचालक स्वतंत्र जांच करे।
भंडारण और सुरक्षा|स्प्रेडशीट, SQLite और फोटो सर्वर पर बिना स्थिर एन्क्रिप्शन हैं। मालिक नियमों को पार कर सकता है। हैश, लॉक और जांच कुछ जोखिम घटाते हैं; TLS, स्वतंत्र सुरक्षा और बैकअप स्थापना पर निर्भर हैं।
रखने की अवधि और हटाना|अपने आप समय पर हटाना या पूरी स्वयं हटाने की सुविधा नहीं है। खाता हटाने से इतिहास, नोट्स, फोटो, लॉग, बैकअप और PDF जरूरी नहीं मिटें। संचालक अवधि/मानदंड, अपवाद और सत्यापित हटाना तय करे।
अनुरोध और खाता वापसी|डेटा देखने, कॉपी, सुधार, हटाने, सीमित करने, स्कोर समीक्षा या शिकायत का अनुरोध करें। अधिकार कानून पर निर्भर हैं। सुरक्षित उचित पहचान जांच चाहिए। पूरी स्वचालित प्रक्रिया या तय जवाब समय की गारंटी नहीं है।
सत्र और बाहरी लिंक|तकनीकी कुकी स्थापना पर निर्भर है; यह सुविधा विज्ञापन ट्रैकर नहीं जोड़ती। WhatsApp बाहरी सेवा है। सुरक्षित अधिकृत प्रक्रिया बिना चैट में पासवर्ड, पहचान या रिपोर्ट न भेजें।
होस्टिंग और स्थानांतरण|होस्टिंग, रखरखाव और बैकअप को तकनीकी पहुंच हो सकती है। सर्वर देश, विक्रेता और सुरक्षा शर्तें अभी निर्दिष्ट नहीं। रोगी देश बदलना डेटा नहीं ले जाता या अंतरराष्ट्रीय साझा करने की अनुमति नहीं देता। डेटा बिक्री/विज्ञापन सेवा नहीं है।
बच्चे और संवेदनशील जानकारी|स्वास्थ्य/फोटो संवेदनशील हो सकते हैं। उम्र सहमति की क्षमता नहीं बताती। अभिभावक जांच और वास्तविक कानूनी आधार तय होने बाकी हैं। काल्पनिक डेटा प्रयोग करें; सूचना सत्यापित सहमति प्रक्रिया नहीं बनाती।
घटनाएं और शिकायत|समस्या स्थापना संपर्क को बताएं; शुरुआत में पासवर्ड या पूरी रिपोर्ट न भेजें। संचालक घटना की जांच, रोकथाम, सूचना और शिकायत प्रक्रिया बनाए। स्वचालित खतरा पहचान या कानूनी सूचना नहीं है।
अपडेट और बाकी विवरण|संस्करण और तारीख दी गई हैं। जरूरी होने पर नया उपयोग पहले बताएं। पढ़ना नई सहमति या जानकारी साझा करने की अनुमति नहीं है। संचालक, कानूनी आधार, संपर्क, अवधि, विक्रेता, कानून और स्वीकृति पूरी करनी होंगी।''',
'zh':'''运营者与范围|真实使用前必须明确责任机构、联系方式、处理依据和服务器位置。项目品牌不能证明医疗机构注册或批准。
账户与医生资料|资料包括编号、姓名、邮箱、出生日期/年龄、性别、婚姻状况、国家、电话、声明的糖尿病类型和可选照片，以及医生身份、专业、许可、医院和审核状态。
健康与随访资料|处理回答、提供的血糖、备注、分数、阈值、版本、日期、报告、照护关系和医生备注。自由文本中不要加入他人身份、密码或无关敏感资料。
事件与技术数据|记录部分操作及访问/导出准备，不能证明全部活动。密码采用哈希但不加密其他记录。基础设施可能另行处理 IP、会话和日志。
来源与用途|资料来自患者、医生和应用事件，用于账户、教育筛查、报告及同意的随访。必填数据支持相应功能，照片/备注为可选。没有假定未说明的研究用途。
模型与人工审核|模型在服务器进行推断。分数不能单独决定治疗、保险或就业。代码不会自动用保存记录重新训练模型，也不会发送给聊天 AI 服务。
患者与医生访问|患者查看自身历史，批准医生通过有效同意关系访问。医院/国家筛选不能代替同意。可连接多位医生。撤销关系不能收回旧副本。
管理员访问|报告/活动需要独立密码及匹配的临时许可。群组许可可能覆盖名单或国家现有/未来患者。配置不验证文书，也不建立法律依据；运营者须独立核验并最小化披露。
存储与安全限制|表格、SQLite 和照片在服务器上，未进行静态加密。所有者可绕过界面限制。哈希、锁定与检查减少部分风险；TLS、独立保管和备份取决于部署。
保留与删除|无定期自动删除或完整自助删除。删除账户不一定清除历史、备注、照片、审计、备份和 PDF。运营者须制定期限/标准、例外、备份过期及验证删除流程。
申请与账户恢复|可申请解释、副本、更正、删除、限制使用、结果复核或投诉。权利及例外依适用法律而定。需要适度、安全的身份核验。没有完整自动处理或保证回复期限。
会话与外部链接|技术 cookie 清单依部署而定；本功能不添加广告追踪。WhatsApp 属外部服务。未建立安全授权流程前，不要通过聊天发送密码、身份证明或医疗报告。
托管与国际转移|托管、维护及备份人员可能有技术访问。服务器国家、供应商和保障尚未明确。修改患者国家不会迁移存储或授权国际披露。无数据销售/广告服务；须确认新增集成。
儿童与敏感数据|健康和照片可能敏感。模型年龄范围不证明同意资格。监护核验及真实使用的处理依据尚需确定。开发中使用虚构资料；本通知不建立已核验监护同意流程。
事故与投诉|通过部署联系方式报告异常，初次不要提供密码或完整病历。运营者须建立评估、控制、通知及监管投诉流程。没有自动事故检测或法律通知。
变更与待补充项目|政策含版本和日期，需要时应预先说明新用途。阅读不产生新的同意或披露授权。责任主体、法律依据、联系、保留规则、供应商、管辖与批准须在实际部署中补全。'''}

META={
'en':('Responsible operator','Privacy contact email','Postal address','Hosting country / providers','Retention rules','Processing basis / jurisdiction','Incident and request process'),
'ar':('الجهة المسؤولة','بريد التواصل للخصوصية','العنوان البريدي','دولة الاستضافة والجهات المساعدة','قواعد الاحتفاظ','أساس المعالجة والقانون المنطبق','إجراءات الحوادث والطلبات'),
'es':('Responsable','Correo de privacidad','Dirección postal','País / proveedores','Retención','Base / jurisdicción','Incidentes y solicitudes'),
'hi':('जिम्मेदार संचालक','गोपनीयता ईमेल','डाक पता','होस्ट देश / विक्रेता','रखने के नियम','आधार / कानून','घटनाएं और अनुरोध'),
'zh':('责任运营者','隐私联系邮箱','邮寄地址','托管国家/供应商','保留规则','处理依据/管辖','事故与申请流程')}
CONFIG_KEYS=('POLICY_OPERATOR_NAME','POLICY_CONTACT_EMAIL','POLICY_POSTAL_ADDRESS','POLICY_HOSTING_DETAILS','POLICY_RETENTION_RULES','POLICY_PROCESSING_BASIS','POLICY_REQUEST_PROCESS')


def setting(key):
    import os,streamlit as st
    try:value=st.secrets.get(key,'')
    except (FileNotFoundError,KeyError):value=''
    return str(value or os.environ.get('PERDIA_'+key,'')).strip()


def open_page(kind):
    import streamlit as st
    current=st.session_state.get('page','auth')
    if current not in ('program_policy','privacy_policy'):st.session_state['_policy_return_page']=current
    st.session_state['page']=kind


FOOTER_SENTENCE={
'en':'Before continuing, please read our {terms} and {privacy}.',
'ar':'قبل المتابعة، يُرجى قراءة {terms} و{privacy}.',
'fr':'Avant de continuer, veuillez lire notre {terms} et notre {privacy}.',
'es':'Antes de continuar, lee nuestra {terms} y nuestra {privacy}.',
'de':'Bitte lesen Sie vor dem Fortfahren unsere {terms} und {privacy}.',
 'tr':'Devam etmeden önce {terms} ve {privacy} metinlerini okuyun.',
'hi':'आगे बढ़ने से पहले हमारी {terms} और {privacy} पढ़ें।',
'pt':'Antes de continuar, leia a nossa {terms} e a nossa {privacy}.',
'ru':'Перед продолжением прочитайте {terms} и {privacy}.',
'zh':'继续之前，请阅读我们的{terms}和{privacy}。'}
FOOTER_NAMES={'fr':('Politique du programme','Politique de confidentialité'),'de':('Programmrichtlinie','Datenschutzerklärung'),'tr':('Program politikası','Gizlilik politikası'),'pt':('Política do programa','Política de privacidade'),'ru':('Правила программы','Политика конфиденциальности')}


def render():
    """One inline sentence with real internal links, below Back on account selection."""
    import streamlit as st
    from urllib.parse import urlencode
    lang=st.session_state.get('lang','en')
    names=FOOTER_NAMES.get(lang,LABELS.get(lang,LABELS['en'])[:2])
    theme='dark' if st.session_state.get('dark_mode',False) else 'light'
    def link(kind,name):
        query=urlencode({'policy':kind,'lang':lang,'theme':theme})
        return '<a target="_self" href="?'+escape(query,quote=True)+'">'+escape(name)+'</a>'
    sentence=FOOTER_SENTENCE.get(lang,FOOTER_SENTENCE['en']).format(terms=link('program',names[0]),privacy=link('privacy',names[1]))
    st.markdown('<div class="policy-sentence" dir="'+('rtl' if lang=='ar' else 'ltr')+'">'+sentence+'</div>',unsafe_allow_html=True)


def route_from_query():
    import streamlit as st
    kind=st.query_params.get('policy')
    if kind not in ('program','privacy'):
        st.session_state.pop('_policy_query_seen',None)
        return
    if st.session_state.get('_policy_query_seen')==kind:return
    open_page('privacy_policy' if kind=='privacy' else 'program_policy')
    st.session_state['_policy_query_seen']=kind


def return_page():
    import streamlit as st
    st.query_params.pop('policy',None)
    st.session_state.pop('_policy_query_seen',None)
    previous=st.session_state.pop('_policy_return_page','auth')
    allowed={'splash','language','auth','login','register','doctor_register','doctor_login','doctor_dashboard','main','patient_history','patient_care','admin'}
    st.session_state['page']=previous if previous in allowed else 'auth'


def render_page():
    import streamlit as st
    lang=st.session_state.get('lang','en')
    if lang not in LABELS:lang='en'
    copy=LABELS[lang];privacy=st.session_state.get('page')=='privacy_policy'
    st.button(copy[4],key='policy_page_back',on_click=return_page)
    st.caption('PerdiaPredict | '+copy[5]+' | '+copy[6]+' | '+VERSION)
    st.title(copy[1 if privacy else 0])
    content=PRIVACY[lang] if privacy else TERMS[lang]
    sections=[line.split('|',1) for line in content.splitlines() if line.strip()]
    with st.expander(copy[9]):
        for i,(heading,_) in enumerate(sections,1):st.write(f'{i}. {heading}')
    for i,(heading,body) in enumerate(sections,1):
        with st.container(border=True):
            st.subheader(f'{i}. {heading}')
            st.write(body)
    st.subheader(copy[7])
    for label,key in zip(META[lang],CONFIG_KEYS):
        st.markdown('**'+label+'**')
        st.write(setting(key) or copy[8])
    # Existing support channel is published in the app; privacy email remains separately configurable.
    support={'en':'Existing application support','ar':'دعم التطبيق المتاح','es':'Soporte de la aplicación','hi':'ऐप सहायता','zh':'应用支持'}[lang]
    st.markdown(f'[{support}: +256771715275](https://wa.me/256771715275)')
    missing=[key for key in CONFIG_KEYS if not setting(key)]
    if missing:st.info(copy[8]+'. '+copy[5]+'.')
    st.button(copy[4],key='policy_page_back_bottom',on_click=return_page)
