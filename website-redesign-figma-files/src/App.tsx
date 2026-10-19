import { useEffect, useRef, useState } from 'react';
import type { FormEvent } from 'react';

type IconName = 'arrow' | 'diagonal' | 'scan' | 'cube' | 'chart' | 'plus' | 'close' | 'menu' | 'download' | 'mail' | 'send' | 'check';
function Icon({ name, size = 20, className = '' }: { name: IconName; size?: number; className?: string }) {
  const paths: Record<IconName, React.ReactNode> = {
    arrow: <><path d="M4 12h16M14 6l6 6-6 6" /></>,
    diagonal: <><path d="M5 19 19 5M5 5h14v14" /></>,
    scan: <><path d="M8 3H3v5m13-5h5v5M3 16v5h5m13-5v5h-5M2 12h20" /><path d="m12 6 5 3v6l-5 3-5-3V9z" /></>,
    cube: <><path d="m12 2 9 5v10l-9 5-9-5V7zM3 7l9 5 9-5M12 12v10M7.5 4.5l9 5" /></>,
    chart: <><path d="M3 3v18h18M7 15l4-5 4 3 6-8" /><path d="M17 5h4v4" /></>,
    plus: <path d="M12 4v16M4 12h16" />,
    close: <path d="m6 6 12 12M6 18 18 6" />,
    menu: <path d="M3 6h18M3 12h18M3 18h18" />,
    download: <><path d="M12 3v12m-5-5 5 5 5-5M4 16v5h16v-5" /></>,
    mail: <><rect x="3" y="5" width="18" height="14" rx="1" /><path d="m3 6 9 7 9-7" /></>,
    send: <><path d="m21 3-7 18-4-7-7-4 18-7ZM10 14 21 3" /></>,
    check: <path d="m5 12 4 4L19 6" />,
  };
  return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" className={className} aria-hidden="true">{paths[name]}</svg>;
}
const services: { icon: IconName; name: string; description: string; features: string[]; tag: string }[] = [
  { icon: 'scan', name: '3D-сканирование', description: 'Оцифровываем объекты любой сложности. От миниатюрных деталей до промышленных механизмов.', features: ['Точность до 0.02 мм', 'Выезд на производство', 'Облако точек и полисетка'], tag: 'STL / PLY / OBJ' },
  { icon: 'cube', name: 'Реверс-инжиниринг', description: 'Восстанавливаем геометрию и создаём параметрические CAD-модели, готовые к производству.', features: ['Твердотельное моделирование', 'Чертежи по ГОСТ / ISO', 'Подготовка к ЧПУ'], tag: 'STEP / IGES / SLDPRT' },
  { icon: 'chart', name: 'Контроль геометрии', description: 'Сравниваем реальную деталь с CAD-моделью. Находим отклонения до того, как они станут проблемой.', features: ['Цветовые карты отклонений', 'Анализ износа и деформаций', 'Метрологический отчёт'], tag: '3D INSPECTION / PDF' },
];
const projects = [
  { name: 'Рабочее колесо турбины', category: 'Реверс-инжиниринг', image: 'turbine.jpg', type: 'ЭНЕРГЕТИКА', detail: 'Восстановление сложной геометрии лопаток по физическому образцу. Сканирование позволяет получить полную цифровую копию, а реверс-инжиниринг — подготовить твердотельную модель для дальнейшего производства.', formats: 'STEP, IGES, STL' },
  { name: 'Корпус редуктора', category: '3D-сканирование', image: 'housing.jpg', type: 'МАШИНОСТРОЕНИЕ', detail: 'Оцифровка корпусной детали со сложными внутренними поверхностями, рёбрами жёсткости и посадочными местами. Результат — детализированная полисетка для измерений и восстановления конструкторской документации.', formats: 'STL, PLY, OBJ' },
  { name: 'Инспекция фланца', category: 'Контроль геометрии', image: 'inspection.jpg', type: 'МЕТРОЛОГИЯ', detail: 'Сопоставление скана детали с номинальной CAD-моделью. Цветовая карта наглядно показывает отклонения поверхности и помогает оценить соответствие геометрии заданным допускам.', formats: 'PDF, STL' },
];
const nav = [['Услуги', 'services'], ['Проекты', 'projects'], ['Как работаем', 'process'], ['Оборудование', 'equipment'], ['Контакты', 'contacts']];

export default function App() {
  const [menu, setMenu] = useState(false);
  const [view, setView] = useState('solid');
  const [filter, setFilter] = useState('Все проекты');
  const [selected, setSelected] = useState<number | null>(null);
  const [service, setService] = useState('3D-сканирование');
  const [prepared, setPrepared] = useState(false);
  const [copied, setCopied] = useState(false);
  const dialog = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    if (selected !== null) dialog.current?.showModal();
    else dialog.current?.close();
  }, [selected]);
  function chooseService(name: string) { setService(name); document.getElementById('contacts')?.scrollIntoView({ behavior: 'smooth' }); }
  function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const data = new FormData(e.currentTarget);
    const body = `Здравствуйте!\n\nИнтересует: ${service}\nИмя: ${data.get('name')}\nКонтакт: ${data.get('contact')}\n\nЗадача: ${data.get('message') || 'Хочу обсудить проект'}\n`;
    window.location.href = `mailto:mifnail@yandex.ru?subject=${encodeURIComponent(`Заявка: ${service}`)}&body=${encodeURIComponent(body)}`;
    setPrepared(true);
  }
  async function copyEmail() {
    try { await navigator.clipboard.writeText('mifnail@yandex.ru'); setCopied(true); setTimeout(() => setCopied(false), 2500); } catch { window.location.href = 'mailto:mifnail@yandex.ru'; }
  }
  return <>
    <header className="header">
      <div className="container header-inner">
        <a className="brand" href="#" aria-label="mifnail — на главную">mifnail<span className="brand-slashes">//</span><span className="brand-sub">engineering</span></a>
        <nav className={menu ? 'navigation open' : 'navigation'} aria-label="Основная навигация">{nav.map(([label, id]) => <a key={id} href={`#${id}`} onClick={() => setMenu(false)}>{label}</a>)}</nav>
        <a className="header-cta" href="#contacts">Обсудить проект <Icon name="diagonal" size={16} /></a>
        <button className="mobile-toggle" onClick={() => setMenu(!menu)} aria-label={menu ? 'Закрыть меню' : 'Открыть меню'} aria-expanded={menu}><Icon name={menu ? 'close' : 'menu'} /></button>
      </div>
    </header>
    <main>
      <section className="hero container">
        <div className="hero-copy">
          <div className="eyebrow hero-eyebrow"><span className="status-dot" /> ИНЖЕНЕРИЯ, ОСНОВАННАЯ НА ТОЧНОСТИ</div>
          <h1>Из физического<br />в <span>цифровое.</span><span className="heading-sub">С точностью до 0.02 мм.</span></h1>
          <p className="hero-description">3D-сканирование, реверс-инжиниринг и контроль<br className="desktop-break" /> геометрии. Превращаем сложные объекты<br className="desktop-break" /> в точные CAD-модели для вашего производства.</p>
          <div className="hero-actions"><a href="#contacts" className="button button-lime">Рассчитать проект <Icon name="diagonal" size={19} /></a><a href="#projects" className="button button-outline">Наши проекты <Icon name="arrow" size={19} /></a></div>
          <div className="hero-note"><span className="tiny-cross">+</span> От одной детали до комплексных инженерных задач</div>
        </div>
        <div className={`cad-view ${view === 'mesh' ? 'mesh-mode' : ''}`}>
          <div className="cad-grid" />
          <div className="cad-top"><span><Icon name="cube" size={14} /> DIGITAL TWIN / 001</span><span className="live-label"><i /> LIVE PREVIEW</span></div>
          <img className="turbine-image" src="images/turbine.jpg" alt="Цифровая визуализация рабочего колеса турбины" />
          {view === 'mesh' && <svg className="mesh-overlay" viewBox="0 0 600 500" aria-hidden="true"><defs><clipPath id="part"><ellipse cx="305" cy="250" rx="202" ry="180" transform="rotate(-25 305 250)" /></clipPath></defs><g clipPath="url(#part)" stroke="#c4f35c" strokeWidth=".6" fill="none">{Array.from({ length: 28 }, (_, i) => <g key={i}><path d={`M${i * 25 - 100} 0L${i * 25 + 240} 500`} /><path d={`M${i * 25 + 100} 0L${i * 25 - 240} 500`} /><ellipse cx="305" cy="250" rx={i * 8} ry={i * 6.5} transform="rotate(-25 305 250)" /></g>)}</g></svg>}
          <div className="precision-label"><span className="label-cross">+</span><span>ТОЧНОСТЬ СКАНИРОВАНИЯ<strong>± 0.02 <small>мм</small></strong></span></div>
          <div className="part-label"><span className="part-line" /><span>Рабочее колесо турбины<small>REVERSE ENGINEERING</small></span></div>
          <div className="axis"><span className="axis-y">Y</span><span className="axis-z">Z</span><span className="axis-x">X</span><svg width="55" height="55" viewBox="0 0 55 55"><path d="M24 33V8M24 33l23 10M24 33 7 46" stroke="#737a70" fill="none" /><circle cx="24" cy="33" r="2" fill="#c4f35c" /></svg></div>
          <div className="view-controls"><button onClick={() => setView('solid')} className={view === 'solid' ? 'active' : ''}><Icon name="cube" size={13} /> CAD-модель</button><button onClick={() => setView('mesh')} className={view === 'mesh' ? 'active' : ''}><Icon name="scan" size={13} /> Полисетка</button></div>
          <span className="cad-corner corner-tl" /><span className="cad-corner corner-br" />
        </div>
      </section>
      <div className="container stats"><div className="stat"><strong>0.02<span> мм</span></strong><span>Точность сканирования</span></div><div className="stat"><strong>500<span>+</span></strong><span>Реализованных проектов</span></div><div className="stat"><strong className="format-stat">STEP / IGES</strong><span>Промышленные форматы CAD</span></div><div className="stat stat-last"><Icon name="scan" size={29} /><div><strong>Работаем по всей РФ</strong><span>Выезд на ваше производство</span></div><span className="status-dot" /></div></div>
      <section className="section container" id="services">
        <div className="section-label"><span>// 01</span> НАШИ УСЛУГИ</div>
        <div className="section-heading"><h2>Точная геометрия.<br /><span className="muted-heading">Реальные возможности.</span></h2><p>Закрываем полный цикл задач — от оцифровки<br /> физического объекта до готовой документации.</p></div>
        <div className="service-grid">{services.map((s, i) => <article className="service-card" key={s.name}><div className="card-top"><div className="service-icon"><Icon name={s.icon} size={27} /></div><span className="card-number">0{i + 1}</span></div><h3>{s.name}</h3><p>{s.description}</p><ul>{s.features.map(f => <li key={f}><span>+</span>{f}</li>)}</ul><div className="card-bottom"><span>{s.tag}</span><button aria-label={`Обсудить: ${s.name}`} onClick={() => chooseService(s.name)}><Icon name="diagonal" size={19} /></button></div></article>)}</div>
      </section>
      <section className="projects-section section" id="projects"><div className="container">
        <div className="section-label"><span>// 02</span> ОТ ОБЪЕКТА К МОДЕЛИ</div>
        <div className="section-heading"><h2>Сложные детали.<br /><span className="muted-heading">Продуманные решения.</span></h2><p>Примеры инженерных задач.<br />У каждой геометрии есть точное решение.</p></div>
        <div className="filter-row" aria-label="Фильтр проектов">{['Все проекты', '3D-сканирование', 'Реверс-инжиниринг', 'Контроль геометрии'].map(f => <button className={filter === f ? 'selected' : ''} key={f} onClick={() => setFilter(f)}>{f}{f === 'Все проекты' && <span>03</span>}</button>)}</div>
        <div className="project-grid">{projects.map((p, i) => (filter === 'Все проекты' || p.category === filter) && <button className="project-card" key={p.name} onClick={() => setSelected(i)}><div className="project-image"><span className="project-type">{p.type}</span><img src={`images/${p.image}`} alt={p.name} loading="lazy" /><span className="project-open"><Icon name="plus" /></span></div><div className="project-info"><div><span>{p.category}</span><h3>{p.name}</h3></div><Icon name="diagonal" /></div></button>)}</div>
      </div></section>
      <section className="section container" id="process"><div className="section-label"><span>// 03</span> КАК МЫ РАБОТАЕМ</div><div className="section-heading"><h2>От вашей задачи<br />до готового CAD-файла.</h2><p>Прозрачный процесс на каждом этапе.<br />Без лишних итераций и неожиданных затрат.</p></div><div className="process-grid">{[{ title: 'Погружаемся в задачу', text: 'Обсуждаем деталь, требуемую точность и форматы. Согласовываем стоимость и сроки.' }, { title: 'Сканируем объект', text: 'Фиксируем геометрию лазерным сканером. У вас на производстве или в нашей лаборатории.' }, { title: 'Создаём модель', text: 'Обрабатываем облако точек и строим параметрическую CAD-модель. Проверяем каждую поверхность.' }, { title: 'Передаём результат', text: 'Вы получаете готовые файлы, чертежи и метрологический отчёт. Остаёмся на связи.' }].map((s, i) => <div className="process-step" key={s.title}><div className="step-number"><span>0{i + 1}</span>{i < 3 ? <Icon name="arrow" size={19} /> : <Icon name="check" size={19} />}</div><h3>{s.title}</h3><p>{s.text}</p></div>)}</div></section>
      <section className="equipment-section" id="equipment"><div className="container equipment-layout"><div><div className="section-label"><span>// 04</span> НАШИ ИНСТРУМЕНТЫ</div><h2>Технологии, которым<br />можно доверять.</h2><p className="equipment-description">Профессиональное метрологическое оборудование и промышленное ПО. Точность — не обещание, а характеристика нашего рабочего процесса.</p><div className="equipment-list"><div><Icon name="scan" /><span>Синий лазерный сканер</span><small>ДО 0.020 ММ</small></div><div><Icon name="cube" /><span>Geomagic & SolidWorks</span><small>CAD / REVERSE</small></div><div><Icon name="chart" /><span>Мобильный измерительный комплекс</span><small>FULL FIELD</small></div></div></div><div className="lab-panel"><div className="lab-header"><span><span className="status-dot" /> LAB / SYSTEM READY</span><Icon name="plus" size={16} /></div><div className="lab-art"><div className="orbit orbit-one" /><div className="orbit orbit-two" /><div className="orbit orbit-three" /><Icon name="cube" size={76} /><span className="art-cross one">+</span><span className="art-cross two">+</span><span className="lab-coordinate">X 124.082<br />Y 086.014<br />Z 032.006</span></div><div className="lab-spec"><span>Скорость захвата</span><strong>1 200 000 точек/сек</strong></div><div className="lab-spec"><span>Форматы данных</span><strong>STEP, IGES, STL, PLY, DWG</strong></div><div className="lab-spec"><span>География работы</span><strong>Вся Россия <span className="lime">↗</span></strong></div></div></div></section>
      <section className="section container contact-layout" id="contacts"><div className="contact-copy"><div className="section-label"><span>// 05</span> НАЧНЁМ С ВАШЕЙ ЗАДАЧИ</div><h2>Есть деталь?<br /><span className="lime">Найдём решение.</span></h2><p>Расскажите о проекте. Поможем выбрать технологию,<br className="desktop-break" /> оценим сроки и стоимость работ.</p><a className="contact-link" href="https://t.me/mifnail" target="_blank" rel="noreferrer"><span className="contact-icon"><Icon name="send" /></span><span><small>Напишите в Telegram</small>@mifnail</span><Icon name="diagonal" size={19} /></a><button className="contact-link email-copy" onClick={copyEmail}><span className="contact-icon"><Icon name={copied ? 'check' : 'mail'} /></span><span><small>{copied ? 'Адрес скопирован' : 'Электронная почта · нажмите, чтобы скопировать'}</small>mifnail@yandex.ru</span><Icon name={copied ? 'check' : 'plus'} size={19} /></button><div className="availability"><span className="status-dot" /> Открыты к новым проектам</div></div><form className="contact-form" onSubmit={submit}><div className="form-top"><h3>Обсудим ваш проект</h3><Icon name="diagonal" /></div><div className="form-two"><label>Ваше имя<input name="name" required placeholder="Как к вам обращаться?" autoComplete="name" /></label><label>Телефон или email<input name="contact" required placeholder="Как с вами связаться?" autoComplete="email" /></label></div><label>Что вас интересует?<select value={service} onChange={e => setService(e.target.value)}>{services.map(s => <option key={s.name}>{s.name}</option>)}<option>Комплексная задача</option></select></label><label>Несколько слов о задаче<textarea name="message" rows={3} placeholder="Что нужно отсканировать или восстановить?" /></label><button className="button button-lime submit-button" type="submit">Подготовить заявку <Icon name="diagonal" size={19} /></button><p className="form-note">Откроется ваш почтовый клиент с готовым письмом.<br />Фото и чертежи можно прикрепить перед отправкой.</p>{prepared && <div className="form-feedback" role="status"><Icon name="check" size={18} /><span>Письмо подготовлено. Отправьте его в почтовом приложении. Не открылось? <a href="https://t.me/mifnail" target="_blank" rel="noreferrer">Напишите в Telegram ↗</a></span></div>}</form></section>
    </main>
    <footer className="footer"><div className="container footer-top"><a href="#" className="brand">mifnail<span className="brand-slashes">//</span><span className="brand-sub">engineering</span></a><span>Инженерия начинается с точности.</span><a href="downloads/mifnail-redesign.zip" download className="archive-link"><Icon name="download" size={16} /> Скачать файлы сайта</a></div><div className="container footer-bottom"><span>© {new Date().getFullYear()} mifnail engineering</span><span>3D SCANNING / REVERSE ENGINEERING / METROLOGY</span><a href="#">Наверх ↑</a></div></footer>
    <dialog ref={dialog} className="project-dialog" onCancel={() => setSelected(null)} onClick={e => { if (e.target === e.currentTarget) setSelected(null); }}>{selected !== null && <><button className="dialog-close" onClick={() => setSelected(null)} aria-label="Закрыть проект"><Icon name="close" /></button><img src={`images/${projects[selected].image}`} alt={projects[selected].name} /><div className="dialog-content"><div className="section-label">ПРИМЕР ЗАДАЧИ / {projects[selected].type}</div><h2>{projects[selected].name}</h2><p>{projects[selected].detail}</p><div className="dialog-formats">Форматы результата <span>{projects[selected].formats}</span></div><button className="button button-lime" onClick={() => { chooseService(projects[selected].category); setSelected(null); }}>У меня похожая задача <Icon name="diagonal" size={18} /></button><small className="illustration-note">Изображение — иллюстрация инженерной задачи.</small></div></>}</dialog>
  </>;
}
