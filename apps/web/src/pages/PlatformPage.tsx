import {
  ArrowLeft,
  ArrowsClockwise,
  BracketsCurly,
  Check,
  Clock,
  Code,
  DownloadSimple,
  File,
  Files,
  Gauge,
  Gear,
  Key,
  LockKey,
  MagnifyingGlass,
  Minus,
  Plus,
  ShieldCheck,
  UploadSimple,
  Warning,
} from "@phosphor-icons/react";
import { useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { toast } from "sonner";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Field, FieldDescription, FieldGroup, FieldLabel } from "@/components/ui/field";
import { Progress } from "@/components/ui/progress";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle, SheetTrigger } from "@/components/ui/sheet";
import { Textarea } from "@/components/ui/textarea";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { DzDocClient } from "@/api";
import type { CanonicalResult, Job } from "@/api";

type Nav = "Documents" | "Review" | "API" | "Usage";
type FieldValue = {
  id: string;
  label: string;
  value: string;
  confidence: number;
  direction?: "rtl" | "ltr";
  source: string;
  box: string;
  alternative?: string;
};

const demoFields: FieldValue[] = [
  { id: "invoice", label: "N° facture", value: "FA-2026-0042", confidence: 98, source: "native-pdf / pdfium", box: "x 11%, y 15%, w 36%, h 5%" },
  { id: "supplier", label: "المورّد / Fournisseur", value: "شركة الأطلس / SARL Atlas Fournitures", confidence: 94, direction: "rtl", source: "ocr / pp-ocrv5", box: "x 10%, y 23%, w 65%, h 5%" },
  { id: "nif", label: "NIF", value: "001626089123456", confidence: 99, source: "numeric validator", box: "x 58%, y 31%, w 29%, h 4%" },
  { id: "ht", label: "Total HT", value: "1 000,00 DZD", confidence: 96, source: "table reconstruction", box: "x 62%, y 71%, w 25%, h 4%" },
  { id: "tva", label: "TVA 19%", value: "190,00 DZD", confidence: 91, source: "invoice arithmetic", box: "x 62%, y 77%, w 25%, h 4%" },
  { id: "ttc", label: "المبلغ الإجمالي / Total TTC", value: "1 190,00 DZD", confidence: 68, direction: "rtl", source: "Arabic-French fusion", box: "x 62%, y 83%, w 26%, h 5%", alternative: "1 790,00 DZD" },
];

const navItems: Array<{ label: Nav; icon: typeof Files }> = [
  { label: "Documents", icon: Files },
  { label: "Review", icon: File },
  { label: "API", icon: Code },
  { label: "Usage", icon: Gauge },
];

function InvoicePage({ selected, onSelect }: { selected: string; onSelect: (id: string) => void }) {
  return (
    <div className="invoice-paper" aria-label="Bilingual invoice with OCR overlays">
      <div className="invoice-head"><div className="invoice-mark">A</div><div dir="rtl"><strong>شركة الأطلس للتجهيزات</strong><span>SARL ATLAS FOURNITURES</span></div><div><b>FACTURE</b><span>N° FA-2026-0042</span></div></div>
      <div className="invoice-rule" />
      <div className="invoice-parties"><p><span>Client</span><b>EURL El Bahdja Distribution</b></p><p dir="rtl"><span>الزبون</span><b>مؤسسة البهجة للتوزيع</b></p></div>
      <div className="invoice-meta"><span>Date: 09/08/2026</span><span>NIF: 001626089123456</span><span>RC: 16/00-1234567B12</span></div>
      <table><thead><tr><th>Désignation / البيان</th><th>Qté</th><th>P.U. HT</th><th>Montant HT</th></tr></thead><tbody><tr><td>Ramette papier A4 / رزمة ورق</td><td>2</td><td>250,00</td><td>500,00</td></tr><tr><td>Cartouche imprimante / خرطوشة</td><td>1</td><td>500,00</td><td>500,00</td></tr></tbody></table>
      <div className="invoice-totals"><span>Total HT</span><b>1 000,00 DZD</b><span>TVA 19%</span><b>190,00 DZD</b><span dir="rtl">المبلغ الإجمالي / Total TTC</span><b>1 190,00 DZD</b></div>
      <div className="invoice-stamp">مطابق<span>ATLAS</span></div>
      <small>Page 1 / 3</small>
      {demoFields.map((field) => <button key={field.id} aria-label={`Inspect ${field.label}`} onClick={() => onSelect(field.id)} className={`ocr-region region-${field.id} ${selected === field.id ? "is-selected" : ""}`} />)}
    </div>
  );
}

function EvidenceInspector({ field, documentId, client }: { field: FieldValue; documentId?: string; client?: DzDocClient }) {
  const [value, setValue] = useState(field.value);
  const changed = value !== field.value;
  const low = field.confidence < 80;

  async function save() {
    if (!changed) return;
    if (client && documentId) await client.correct(documentId, field.id, field.value, value);
    toast.success("Correction saved with provenance");
  }

  return (
    <aside className="evidence-panel">
      <div><span className="panel-label">Evidence inspector</span><h2>{field.label}</h2></div>
      <Separator />
      <div className="confidence-row"><span>{low ? <Warning weight="fill" /> : <Check weight="bold" />}Confidence</span><strong>{field.confidence}%</strong></div>
      <Progress value={field.confidence} data-low={low || undefined} />
      <FieldGroup>
        <Field>
          <FieldLabel htmlFor="extracted-value">Extracted value</FieldLabel>
          <Textarea id="extracted-value" dir={field.direction ?? "ltr"} value={value} onChange={(event) => setValue(event.target.value)} />
          <FieldDescription>Edits are stored separately from raw model output.</FieldDescription>
        </Field>
      </FieldGroup>
      <Button disabled={!changed} onClick={() => void save()} className="w-full"><Check data-icon="inline-start" />Save verified correction</Button>
      <dl className="evidence-list"><div><dt>Source</dt><dd>{field.source}</dd></div><div><dt>Coordinates</dt><dd>{field.box}</dd></div><div><dt>Direction</dt><dd>{field.direction?.toUpperCase() ?? "LTR"}, mixed digits</dd></div></dl>
      {field.alternative && <Alert><Warning /><AlertTitle>Recognition alternative</AlertTitle><AlertDescription><button onClick={() => setValue(field.alternative!)}>{field.alternative}, 62%</button></AlertDescription></Alert>}
      <Separator />
      <section className="validation-list"><h3>Validation trace</h3><p><Check />HT + TVA = TTC</p><p><Check />Currency and decimal format</p><p className="warning-text"><Warning />Recognizers disagree on digit 1</p></section>
      <Separator />
      <section className="trace-list"><h3>Processing trace</h3><ol><li><b>Native text rejected</b><span>Incomplete region</span></li><li><b>Arabic-French OCR</b><span>Two candidates preserved</span></li><li><b>VLM not called</b><span>Arithmetic resolved the region</span></li></ol></section>
    </aside>
  );
}

function ConnectionSheet({ apiUrl, apiKey, onSave }: { apiUrl: string; apiKey: string; onSave: (url: string, key: string) => void }) {
  const [url, setUrl] = useState(apiUrl);
  const [key, setKey] = useState(apiKey);
  return (
    <Sheet>
      <SheetTrigger asChild><Button variant="ghost" size="icon-sm" aria-label="Connection settings"><Gear /></Button></SheetTrigger>
      <SheetContent>
        <SheetHeader><SheetTitle>Engine connection</SheetTitle><SheetDescription>Connect this browser to your hosted or local DzDoc API.</SheetDescription></SheetHeader>
        <div className="sheet-form"><FieldGroup><Field><FieldLabel htmlFor="api-url">API URL</FieldLabel><Textarea id="api-url" value={url} onChange={(event) => setUrl(event.target.value)} rows={2} /><FieldDescription>Use /api for the same-origin Docker deployment.</FieldDescription></Field><Field><FieldLabel htmlFor="api-key">API key</FieldLabel><Textarea id="api-key" value={key} onChange={(event) => setKey(event.target.value)} rows={3} /></Field></FieldGroup><Button onClick={() => { onSave(url.trim(), key.trim()); toast.success("Connection saved in this browser"); }}>Save connection</Button></div>
      </SheetContent>
    </Sheet>
  );
}

export function PlatformPage() {
  const [active, setActive] = useState<Nav>("Review");
  const [selected, setSelected] = useState("ttc");
  const [zoom, setZoom] = useState(82);
  const [apiUrl, setApiUrl] = useState(() => localStorage.getItem("dzdoc.apiUrl") ?? (import.meta.env.VITE_DZDOC_API_URL || "/api"));
  const [apiKey, setApiKey] = useState(() => localStorage.getItem("dzdoc.apiKey") ?? "");
  const [job, setJob] = useState<Job | null>(null);
  const [result, setResult] = useState<CanonicalResult | null>(null);
  const [sourceName, setSourceName] = useState("Facture_Atlas_Aout.pdf");
  const [error, setError] = useState("");
  const fileRef = useRef<HTMLInputElement>(null);
  const field = useMemo(() => demoFields.find((item) => item.id === selected) ?? demoFields[0], [selected]);
  const client = useMemo(() => new DzDocClient(apiKey, apiUrl), [apiKey, apiUrl]);

  function saveConnection(url: string, key: string) {
    localStorage.setItem("dzdoc.apiUrl", url);
    localStorage.setItem("dzdoc.apiKey", key);
    setApiUrl(url);
    setApiKey(key);
  }

  async function waitForJob(next: Job) {
    let current = next;
    for (let attempt = 0; attempt < 180 && !["succeeded", "failed"].includes(current.status); attempt += 1) {
      await new Promise((resolve) => window.setTimeout(resolve, 1000));
      current = await client.getJob(current.id);
      setJob(current);
    }
    if (current.status === "failed") throw new Error(current.error?.message ?? "Processing failed");
    if (current.status !== "succeeded") throw new Error("Processing did not finish within three minutes");
    setResult(await client.getResult(current.document_id));
    toast.success("Document processed");
  }

  async function upload(files: FileList | null) {
    const file = files?.[0];
    if (!file) return;
    if (!apiKey) {
      setError("Add an API key in connection settings before uploading.");
      return;
    }
    setError(""); setResult(null); setSourceName(file.name);
    try {
      const submission = await client.upload(file);
      setJob(submission.job);
      await waitForJob(submission.job);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Upload failed");
    }
  }

  return (
    <TooltipProvider>
      <div className="platform-shell">
        <aside className="platform-nav">
          <Link to="/" className="wordmark"><span>د</span><b>DzDoc</b></Link>
          <nav aria-label="Platform navigation">{navItems.map(({ label, icon: Icon }) => <button key={label} data-active={active === label || undefined} onClick={() => setActive(label)}><Icon /><span>{label}</span>{label === "Review" && <Badge variant="secondary">1</Badge>}</button>)}</nav>
          <div className="nav-security"><ShieldCheck /><span><b>Private workspace</b><small>Local retention policy</small></span></div>
        </aside>
        <main className="platform-main">
          <header className="platform-topbar">
            <div className="breadcrumbs"><Link to="/"><ArrowLeft /></Link><span>Documents</span><b>{sourceName}</b><Badge variant="secondary">{job?.status ?? "Demo sample"}</Badge></div>
            <div className="top-actions"><Tooltip><TooltipTrigger asChild><Button variant="ghost" size="icon-sm" aria-label="Search"><MagnifyingGlass /></Button></TooltipTrigger><TooltipContent>Search</TooltipContent></Tooltip><ConnectionSheet apiUrl={apiUrl} apiKey={apiKey} onSave={saveConnection} /><Button size="sm" onClick={() => fileRef.current?.click()}><UploadSimple data-icon="inline-start" />New document</Button><input ref={fileRef} hidden type="file" accept=".pdf,image/png,image/jpeg,image/tiff" onChange={(event) => void upload(event.target.files)} /></div>
          </header>
          <div className="document-toolbar"><div><h1>{active === "Review" ? "Review extraction" : active}</h1><p>{result ? `${result.pages?.length ?? 0} pages processed` : "3 pages, Arabic + French"}</p></div><div><Button variant="outline" size="icon-sm" onClick={() => setZoom(Math.max(55, zoom - 10))}><Minus /></Button><span>{zoom}%</span><Button variant="outline" size="icon-sm" onClick={() => setZoom(Math.min(130, zoom + 10))}><Plus /></Button><Button variant="outline" size="sm"><DownloadSimple data-icon="inline-start" />Export</Button><Sheet><SheetTrigger asChild><Button className="mobile-evidence-trigger" size="sm" variant="outline"><MagnifyingGlass data-icon="inline-start" />Evidence</Button></SheetTrigger><SheetContent side="bottom" className="h-[86dvh]"><SheetHeader><SheetTitle>Review evidence</SheetTitle><SheetDescription>Inspect the selected field and save a verified correction.</SheetDescription></SheetHeader><ScrollArea className="min-h-0 flex-1"><EvidenceInspector key={`mobile-${field.id}`} field={field} documentId={job?.document_id} client={apiKey ? client : undefined} /></ScrollArea></SheetContent></Sheet></div></div>
          {error && <Alert variant="destructive" className="runtime-alert"><Warning /><AlertTitle>Could not process the document</AlertTitle><AlertDescription>{error}</AlertDescription></Alert>}
          <div className="review-grid">
            <ScrollArea className="page-rail"><div className="page-rail-inner"><span className="panel-label">Pages</span>{[1, 2, 3].map((page) => <button key={page} data-active={page === 1 || undefined}><div><i /><i /><i /></div><span>{page}</span>{page === 1 && <small>1 issue</small>}</button>)}</div></ScrollArea>
            <section className="document-canvas" style={{ "--paper-zoom": zoom / 82 } as React.CSSProperties}><InvoicePage selected={selected} onSelect={setSelected} /></section>
            <ScrollArea className="evidence-scroll"><EvidenceInspector key={field.id} field={field} documentId={job?.document_id} client={apiKey ? client : undefined} /></ScrollArea>
          </div>
          <footer className="platform-status"><span><ArrowsClockwise />{job ? `Job ${job.status}` : "Sample data, connect an engine to upload"}</span><span><LockKey />encrypted</span><span><BracketsCurly />schema 1.1.0</span><span><Clock />CPU profile</span><span><Key />{apiKey ? "API connected" : "API key required"}</span></footer>
        </main>
      </div>
    </TooltipProvider>
  );
}
