import {
  Activity,
  AlertTriangle,
  Braces,
  Check,
  ChevronDown,
  Clock3,
  Code2,
  Download,
  FileCheck2,
  Files,
  Gauge,
  Languages,
  Layers3,
  LockKeyhole,
  MoreHorizontal,
  PanelLeftClose,
  RotateCw,
  Search,
  Settings,
  ShieldCheck,
  Sparkles,
  Upload,
  UserRoundCheck,
  Webhook,
  ZoomIn,
  ZoomOut,
} from "lucide-react";
import { useMemo, useRef, useState } from "react";

type Nav = "Documents" | "Review" | "API" | "Usage" | "Settings";
type Field = {
  id: string;
  label: string;
  value: string;
  confidence: number;
  direction?: "rtl" | "ltr";
  box: string;
  source: string;
  alternative?: string;
};

const fields: Field[] = [
  { id: "invoice", label: "N° facture", value: "FA-2026-0042", confidence: 98, box: "11, 15 · 36 × 5%", source: "native-pdf / pdfium" },
  { id: "supplier", label: "المورّد / Fournisseur", value: "شركة الأطلس · SARL Atlas Fournitures", confidence: 94, direction: "rtl", box: "10, 23 · 65 × 5%", source: "ocr / pp-ocrv5" },
  { id: "nif", label: "NIF", value: "001626089123456", confidence: 99, box: "58, 31 · 29 × 4%", source: "ocr / numeric-validator" },
  { id: "ht", label: "Total HT", value: "1 000,00 DZD", confidence: 96, box: "62, 71 · 25 × 4%", source: "table-reconstruction" },
  { id: "tva", label: "TVA 19%", value: "190,00 DZD", confidence: 91, box: "62, 77 · 25 × 4%", source: "invoice-dz / arithmetic" },
  { id: "ttc", label: "المبلغ الإجمالي / Total TTC", value: "1 190,00 DZD", confidence: 68, direction: "rtl", box: "62, 83 · 26 × 5%", source: "ocr / arabic-fr fusion", alternative: "1 790,00 DZD · 62%" },
];

const navItems: Array<{ label: Nav; icon: typeof Files }> = [
  { label: "Documents", icon: Files },
  { label: "Review", icon: FileCheck2 },
  { label: "API", icon: Code2 },
  { label: "Usage", icon: Gauge },
  { label: "Settings", icon: Settings },
];

function InvoicePage({ selected, onSelect }: { selected: string; onSelect: (id: string) => void }) {
  return (
    <div className="paper" aria-label="Invoice page with OCR overlays">
      <div className="paper-head">
        <div className="brandmark">A</div>
        <div dir="rtl"><strong>شركة الأطلس للتجهيزات</strong><small>SARL ATLAS FOURNITURES</small></div>
        <div className="invoice-title"><b>FACTURE</b><span>N° FA-2026-0042</span></div>
      </div>
      <div className="paper-rule" />
      <div className="bilingual-row">
        <p><span>Client</span><b>EURL El Bahdja Distribution</b></p>
        <p dir="rtl"><span>الزبون</span><b>مؤسسة البهجة للتوزيع</b></p>
      </div>
      <div className="meta-row"><span>Date: 09/08/2026</span><span>NIF: 001626089123456</span><span>RC: 16/00-1234567B12</span></div>
      <table>
        <thead><tr><th>Désignation / البيان</th><th>Qté</th><th>P.U. HT</th><th>Montant HT</th></tr></thead>
        <tbody>
          <tr><td>Ramette papier A4 / رزمة ورق</td><td>2</td><td>250,00</td><td>500,00</td></tr>
          <tr><td>Cartouche imprimante / خرطوشة</td><td>1</td><td>500,00</td><td>500,00</td></tr>
        </tbody>
      </table>
      <div className="totals"><span>Total HT</span><b>1 000,00 DZD</b><span>TVA 19%</span><b>190,00 DZD</b><span dir="rtl">المبلغ الإجمالي / Total TTC</span><b>1 190,00 DZD</b></div>
      <div className="stamp">مطابق<br /><span>ATLAS</span></div>
      <small className="paper-foot">Paiement à 30 jours · Banque d'Algérie · Page 1 / 3</small>
      {fields.map((field) => <button key={field.id} aria-label={`Inspect ${field.label}`} onClick={() => onSelect(field.id)} className={`ocr-box box-${field.id} ${selected === field.id ? "selected" : ""}`} />)}
    </div>
  );
}

function Inspector({ field, onSaved }: { field: Field; onSaved: (text: string) => void }) {
  const [value, setValue] = useState(field.value);
  const low = field.confidence < 80;
  return (
    <aside className="inspector">
      <div className="inspector-head"><div><span className="eyebrow">Evidence inspector</span><h2>{field.label}</h2></div><MoreHorizontal size={18} /></div>
      <div className={`confidence ${low ? "low" : "good"}`}><span>{low ? <AlertTriangle size={16} /> : <Check size={16} />} Confidence</span><strong>{field.confidence}%</strong><i><em style={{ width: `${field.confidence}%` }} /></i></div>
      <label className="field-label" htmlFor="field-value">Extracted value</label>
      <textarea id="field-value" dir={field.direction ?? "ltr"} value={value} onChange={(event) => setValue(event.target.value)} />
      <button className="save" disabled={value === field.value} onClick={() => onSaved(value)}><UserRoundCheck size={16} /> Save verified correction</button>
      <dl className="evidence-list"><div><dt>Source</dt><dd><Layers3 size={14} /> {field.source}</dd></div><div><dt>Coordinates</dt><dd>{field.box}</dd></div><div><dt>Reading order</dt><dd>Block 18 · Line 2</dd></div><div><dt>Direction</dt><dd>{field.direction?.toUpperCase() ?? "LTR"} · mixed digits</dd></div></dl>
      {field.alternative && <section className="alternative"><span>Closest alternative</span><button onClick={() => setValue(field.alternative!.split(" · ")[0])}>{field.alternative}<ChevronDown size={14} /></button></section>}
      <section className="validation"><span className="eyebrow">Deterministic validation</span><p><Check size={15} /> HT + TVA = TTC</p><p><Check size={15} /> Currency and decimal format</p><p className="warn"><AlertTriangle size={15} /> Recognizers disagree on digit 1</p></section>
      <section className="trace"><span className="eyebrow">Processing trace</span><ol><li><b>Native text</b><small>Rejected · incomplete region</small></li><li><b>Arabic–French OCR</b><small>Two candidates preserved</small></li><li><b>VLM fallback</b><small>Not called · arithmetic resolved</small></li></ol></section>
    </aside>
  );
}

export default function App() {
  const [active, setActive] = useState<Nav>("Review");
  const [selected, setSelected] = useState("ttc");
  const [zoom, setZoom] = useState(78);
  const [notice, setNotice] = useState("5 fields verified · 1 needs review");
  const [uploading, setUploading] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);
  const field = useMemo(() => fields.find((item) => item.id === selected) ?? fields[0], [selected]);

  function upload(files: FileList | null) {
    if (!files?.[0]) return;
    setUploading(true);
    setNotice(`Securely ingesting ${files[0].name}…`);
    window.setTimeout(() => { setUploading(false); setNotice("Queued · native PDF inspection pending"); }, 900);
  }

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="logo"><span>د</span><div><b>DzDoc</b><small>Document intelligence</small></div></div>
        <nav aria-label="Primary navigation">{navItems.map(({ label, icon: Icon }) => <button key={label} className={active === label ? "active" : ""} onClick={() => setActive(label)}><Icon size={18} /><span>{label}</span>{label === "Review" && <em>1</em>}</button>)}</nav>
        <div className="sidebar-foot"><div><ShieldCheck size={16} /><span><b>Private workspace</b><small>EU region · 30-day retention</small></span></div><button aria-label="Collapse navigation"><PanelLeftClose size={18} /></button></div>
      </aside>
      <main>
        <header className="topbar">
          <div className="breadcrumb"><button>Documents</button><span>/</span><strong>Facture_Atlas_Aout.pdf</strong><span className="status"><Check size={13} /> Processed</span></div>
          <div className="actions"><button><Search size={17} /><span>Search</span></button><button><Languages size={17} /> AR / FR</button><button onClick={() => fileRef.current?.click()} className="primary"><Upload size={16} /> {uploading ? "Uploading…" : "New document"}</button><input ref={fileRef} type="file" accept=".pdf,image/*" hidden onChange={(event) => upload(event.target.files)} /></div>
        </header>
        <div className="workbar">
          <div className="page-meta"><button aria-label="Return to documents">‹</button><div><h1>{active === "Review" ? "Review extraction" : active}</h1><p>3 pages · 1.8 MB · Arabic + French</p></div></div>
          <div className="tools"><button aria-label="Rotate"><RotateCw size={16} /></button><button aria-label="Zoom out" onClick={() => setZoom(Math.max(50, zoom - 10))}><ZoomOut size={16} /></button><span>{zoom}%</span><button aria-label="Zoom in" onClick={() => setZoom(Math.min(130, zoom + 10))}><ZoomIn size={16} /></button><button className="export"><Download size={16} /> Export <ChevronDown size={14} /></button></div>
        </div>
        <div className="workspace">
          <aside className="pages"><span className="eyebrow">Pages</span>{[1,2,3].map((page) => <button key={page} className={page === 1 ? "active" : ""}><div className={`mini-page mini-${page}`}><i /><i /><i /></div><span>{page}</span>{page === 1 && <em>1 issue</em>}</button>)}</aside>
          <section className="canvas" style={{ "--paper-scale": zoom / 78 } as React.CSSProperties}><InvoicePage selected={selected} onSelect={setSelected} /></section>
          <Inspector key={field.id} field={field} onSaved={(text) => { setNotice(`Correction saved with provenance: ${text}`); }} />
        </div>
        <footer className="statusbar"><div><Activity size={14} /><span>{notice}</span></div><div><span><LockKeyhole size={13} /> encrypted</span><span><Webhook size={13} /> webhook ready</span><span><Braces size={13} /> schema 1.1.0</span><span><Clock3 size={13} /> 1.42 s/page</span><span><Sparkles size={13} /> VLM 0 regions</span></div></footer>
      </main>
    </div>
  );
}
