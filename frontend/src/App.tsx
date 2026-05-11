import * as Tabs from '@radix-ui/react-tabs'
import { useMemo, useState } from 'react'
import { toast } from 'sonner'
import {
  expectativasCRISP,
  fuzzifyEdad,
  fuzzifyEstabilidad,
  fuzzifyExpectativas,
  fuzzifyImc,
  fuzzifySalud,
  type LabeledDegree,
} from './fuzzMath'
import { cn } from './lib/utils'

const API_EVALUAR = 'http://127.0.0.1:8000/evaluar'

export type MemoriaTrabajoPayload = {
  edad: number
  procedimiento_deseado: 'abdominoplastía' | 'liposucción' | 'ambos'
  imc: number
  estabilidad_peso: number
  estado_general_salud: number
  enfermedad_no_controlada: boolean
  tabaquismo: boolean
  consume_drogas: boolean
  antecedentes_quirurgicos:
    | 'sin antecedentes'
    | 'cirugía previa sin complicaciones'
    | 'cirugía previa con complicaciones'
  cicatrizacion: number
  estado_psicologico: 'estable' | 'dudoso' | 'inestable'
  expectativas: 'realistas' | 'poco claras' | 'irreales'
  informacion_completa: boolean
}

export type EvaluacionResultado = {
  aptitud_preliminar: string
  nivel_riesgo: 'bajo' | 'medio' | 'alto'
  nivel_riesgo_numerico: number
  recomendacion: string
  derivacion_sugerida: string
  reglas_activadas: string[]
}

type InferenceStep = {
  id: number
  title: string
  subtitle: string
  status: 'pending' | 'ok' | 'warn' | 'skip' | 'fail'
  detail: string
}

const defaultForm: MemoriaTrabajoPayload = {
  edad: 38,
  procedimiento_deseado: 'abdominoplastía',
  imc: 29,
  estabilidad_peso: 5,
  estado_general_salud: 8,
  enfermedad_no_controlada: false,
  tabaquismo: true,
  consume_drogas: false,
  antecedentes_quirurgicos: 'cirugía previa sin complicaciones',
  cicatrizacion: 3,
  estado_psicologico: 'estable',
  expectativas: 'realistas',
  informacion_completa: true,
}

function buildInferenceSteps(
  form: MemoriaTrabajoPayload,
  result: EvaluacionResultado | null,
): InferenceStep[] {
  if (!result) {
    return [
      {
        id: 1,
        title: 'Control de información',
        subtitle: 'Fase 1 — Regla R1',
        status: 'pending',
        detail: 'Verificación de datos completos antes de inferir.',
      },
      {
        id: 2,
        title: 'Reglas críticas',
        subtitle: 'Fase 2 — R2 a R7',
        status: 'pending',
        detail: 'Menor de edad, enfermedad no controlada, drogas, psicología, expectativas, salud.',
      },
      {
        id: 3,
        title: 'Lógica difusa',
        subtitle: 'Fase 3 — Fuzzificación / Reglas Mamdani',
        status: 'pending',
        detail: 'Edad, IMC, estabilidad, salud, expectativas y factores moderados.',
      },
      {
        id: 4,
        title: 'Reglas combinadas',
        subtitle: 'Fases 4–5 — R8–R22',
        status: 'pending',
        detail: 'Tabaquismo, IMC, peso, antecedentes; conteo de factores moderados (R21–R22).',
      },
      {
        id: 5,
        title: 'Conclusión',
        subtitle: 'Defuzzificación y clasificación',
        status: 'pending',
        detail: 'Centroide → categoría de riesgo → aptitud preliminar.',
      },
    ]
  }

  const reglas = result.reglas_activadas
  const rulesCritical = ['R2', 'R3', 'R4', 'R5', 'R6', 'R7']
  const hitCritical = rulesCritical.some((r) => reglas.includes(r))
  const hitR1 = reglas.includes('R1')
  const hitFuzzy = reglas.some((r) => r.includes('Fase3') || r.includes('difuso'))
  const moderateCodes = [
    'R8',
    'R9',
    'R10',
    'R11',
    'R12',
    'R13',
    'R14',
    'R15',
    'R16',
    'R17',
    'R18',
    'R19',
    'R20',
    'R21',
    'R22',
  ]
  const hitCombined = moderateCodes.some((r) => reglas.includes(r))

  return [
    {
      id: 1,
      title: 'Control de información',
      subtitle: 'Fase 1 — R1',
      status: hitR1 || !form.informacion_completa ? 'fail' : 'ok',
      detail: hitR1
        ? 'Información incompleta: el motor detiene la evaluación (R1).'
        : 'Datos marcados como completos; se continúa el encadenamiento.',
    },
    {
      id: 2,
      title: 'Reglas críticas',
      subtitle: 'Fase 2 — R2 a R7',
      status: hitR1 ? 'skip' : hitCritical ? 'warn' : 'ok',
      detail: hitR1
        ? 'No evaluado: paso previo bloqueante.'
        : hitCritical
          ? `Disparo crítico: ${rulesCritical.filter((r) => reglas.includes(r)).join(', ') || '—'}. Respuesta inmediata.`
          : 'Sin activación de reglas críticas; continúa hacia lógica difusa.',
    },
    {
      id: 3,
      title: 'Lógica difusa',
      subtitle: 'Fase 3 — Motor difuso',
      status: hitR1 || hitCritical ? 'skip' : hitFuzzy ? 'ok' : 'pending',
      detail:
        hitR1 || hitCritical
          ? 'No aplica: la conclusión ya fue fijada por reglas prioritarias.'
          : hitFuzzy
            ? 'Fuzzificación de variables graduales y agregación de reglas difusas (scikit-fuzzy).'
            : 'Sin evidencia de ejecución difusa en la última respuesta.',
    },
    {
      id: 4,
      title: 'Reglas combinadas',
      subtitle: 'Fases 4–5',
      status: hitR1 || hitCritical ? 'skip' : hitCombined || hitFuzzy ? 'ok' : 'warn',
      detail:
        hitR1 || hitCritical
          ? 'No aplica tras corte crítico.'
          : `Moderadas / combinadas según payload y reglas (${
              reglas.filter((r) => r.startsWith('R')).join(', ') || '—'
            }).`,
    },
    {
      id: 5,
      title: 'Conclusión',
      subtitle: 'Defuzzificación + decisión',
      status: 'ok',
      detail: `Riesgo ${result.nivel_riesgo.toUpperCase()} (${result.nivel_riesgo_numerico.toFixed(1)}). ${result.aptitud_preliminar}.`,
    },
  ]
}

const scaleOptions = Array.from({ length: 10 }, (_, i) => i + 1)

function ruleChipClass(rule: string): string {
  if (/^R[2-7]$/.test(rule)) return 'border-red-200 bg-red-50 text-red-800'
  if (rule === 'R1') return 'border-slate-300 bg-slate-100 text-slate-800'
  if (rule === 'R21' || rule === 'R22') return 'border-amber-300 bg-amber-50 text-amber-900'
  if (rule.includes('Fase') || rule.includes('difuso'))
    return 'border-indigo-200 bg-indigo-50 text-indigo-900'
  return 'border-sky-200 bg-sky-50 text-sky-900'
}

function aptitudPalette(aptitud: string): { bar: string; text: string; ring: string } {
  if (aptitud === 'apto preliminarmente')
    return {
      bar: 'from-emerald-500 to-teal-600',
      text: 'text-emerald-900',
      ring: 'ring-emerald-200',
    }
  if (aptitud === 'apto con condiciones')
    return {
      bar: 'from-amber-400 to-amber-600',
      text: 'text-amber-950',
      ring: 'ring-amber-200',
    }
  if (aptitud === 'requiere mayor información')
    return {
      bar: 'from-slate-400 to-slate-600',
      text: 'text-slate-900',
      ring: 'ring-slate-200',
    }
  return { bar: 'from-rose-500 to-red-600', text: 'text-red-950', ring: 'ring-rose-200' }
}

function riesgoBadgeClass(nivel: EvaluacionResultado['nivel_riesgo']): string {
  if (nivel === 'bajo') return 'bg-emerald-100 text-emerald-900 border-emerald-200'
  if (nivel === 'medio') return 'bg-amber-100 text-amber-950 border-amber-200'
  return 'bg-rose-100 text-rose-900 border-rose-200'
}

function MembershipBars({ title, rows }: { title: string; rows: LabeledDegree[] }) {
  const active = rows.filter((r) => r.mu > 0.005).sort((a, b) => b.mu - a.mu)
  const display = active.length ? active : rows

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
      <h4 className="text-sm font-semibold text-slate-800">{title}</h4>
      <p className="mb-3 text-xs text-slate-500">Grados de pertenencia μ (triángulos / trapecios del informe)</p>
      <ul className="space-y-2">
        {display.map((row) => (
          <li key={row.label} className="flex flex-col gap-1">
            <div className="flex items-center justify-between text-xs">
              <span className="font-medium text-slate-700">{row.label}</span>
              <span className="tabular-nums text-slate-500">{(row.mu * 100).toFixed(1)}%</span>
            </div>
            <div className="h-2 w-full overflow-hidden rounded-full bg-slate-100">
              <div
                className="h-full rounded-full bg-gradient-to-r from-sky-400 to-blue-600 transition-[width]"
                style={{ width: `${Math.min(100, Math.round(row.mu * 100))}%` }}
              />
            </div>
          </li>
        ))}
      </ul>
    </div>
  )
}

function RiskGauge({ value }: { value: number }) {
  const v = Math.max(0, Math.min(100, value))
  const markerLeft = `calc(${v}% - 6px)`

  return (
    <div className="w-full">
      <div className="relative h-10 w-full overflow-hidden rounded-full bg-slate-100 shadow-inner">
        <div className="absolute inset-y-0 left-0 w-[35%] bg-emerald-400/90" title="Bajo (0–35)" />
        <div className="absolute inset-y-0 left-[35%] w-[35%] bg-amber-400/90" title="Medio (36–70)" />
        <div className="absolute inset-y-0 left-[70%] w-[30%] bg-rose-400/90" title="Alto (71–100)" />
        <div
          className="absolute top-1/2 z-10 h-0 w-0 -translate-y-1/2 border-x-[6px] border-b-[10px] border-x-transparent border-b-slate-900 drop-shadow"
          style={{ left: markerLeft }}
        />
      </div>
      <div className="mt-2 flex justify-between text-[11px] font-medium text-slate-500">
        <span>0</span>
        <span>35</span>
        <span>70</span>
        <span>100</span>
      </div>
    </div>
  )
}

function Toggle({
  checked,
  onChange,
  label,
  description,
}: {
  checked: boolean
  onChange: (v: boolean) => void
  label: string
  description?: string
}) {
  return (
    <div className="flex items-center justify-between gap-4 rounded-lg border border-slate-200 bg-white px-3 py-2.5">
      <div>
        <p className="text-sm font-medium text-slate-800">{label}</p>
        {description ? <p className="text-xs text-slate-500">{description}</p> : null}
      </div>
      <button
        type="button"
        role="switch"
        aria-checked={checked}
        onClick={() => onChange(!checked)}
        className={cn(
          'relative inline-flex h-7 w-12 shrink-0 rounded-full border transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-500',
          checked ? 'border-blue-600 bg-blue-600' : 'border-slate-300 bg-slate-200',
        )}
      >
        <span
          className={cn(
            'pointer-events-none inline-block h-6 w-6 translate-y-0.5 rounded-full bg-white shadow transition-transform',
            checked ? 'translate-x-5' : 'translate-x-0.5',
          )}
        />
      </button>
    </div>
  )
}

export default function App() {
  const [form, setForm] = useState<MemoriaTrabajoPayload>(defaultForm)
  const [result, setResult] = useState<EvaluacionResultado | null>(null)
  const [loading, setLoading] = useState(false)

  const fuzzPanels = useMemo(() => {
    const edad = fuzzifyEdad(form.edad)
    const imc = fuzzifyImc(form.imc)
    const est = fuzzifyEstabilidad(form.estabilidad_peso)
    const sal = fuzzifySalud(form.estado_general_salud)
    const exp = fuzzifyExpectativas(expectativasCRISP(form.expectativas))
    return { edad, imc, est, sal, exp }
  }, [form])

  const steps = useMemo(() => buildInferenceSteps(form, result), [form, result])

  async function evaluar() {
    setLoading(true)
    try {
      const res = await fetch(API_EVALUAR, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(form),
      })

      if (!res.ok) {
        let msg = `Error HTTP ${res.status}`
        try {
          const errBody = await res.json()
          if (typeof errBody?.detail === 'string') msg = errBody.detail
          else if (Array.isArray(errBody?.detail))
            msg = errBody.detail.map((e: { msg?: string }) => e.msg ?? JSON.stringify(e)).join('; ')
        } catch {
          /* ignore */
        }
        toast.error('La API respondió con error', { description: msg })
        return
      }

      const data = (await res.json()) as EvaluacionResultado
      setResult(data)
      toast.success('Evaluación completada')
    } catch {
      toast.error('No se pudo conectar con la API', {
        description:
          '¿Está corriendo uvicorn en 127.0.0.1:8000? Compruebe CORS y que el backend esté activo.',
      })
    } finally {
      setLoading(false)
    }
  }

  const palette = result ? aptitudPalette(result.aptitud_preliminar) : null

  return (
    <div className="min-h-screen bg-gradient-to-b from-slate-50 to-white text-slate-900">
      <header className="border-b border-slate-200/80 bg-white/90 backdrop-blur">
        <div className="mx-auto flex max-w-6xl flex-col gap-2 px-4 py-6 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wider text-blue-700">Sistema Experto</p>
            <h1 className="mt-1 text-2xl font-semibold tracking-tight text-slate-900 sm:text-3xl">
              Evaluación preliminar — cirugía estética corporal
            </h1>
            <p className="mt-1 max-w-2xl text-sm text-slate-600">
              Herramienta de apoyo clínico (no sustituye juicio médico). Datos enviados a{' '}
              <code className="rounded bg-slate-100 px-1.5 py-0.5 text-xs text-slate-800">{API_EVALUAR}</code>
            </p>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-6xl px-4 py-8">
        <Tabs.Root defaultValue="clinical" className="w-full">
          <Tabs.List className="mb-8 flex w-full gap-1 rounded-xl border border-slate-200 bg-slate-100/80 p-1 shadow-sm">
            <Tabs.Trigger
              value="clinical"
              className={cn(
                'flex-1 rounded-lg px-4 py-3 text-sm font-medium transition-all',
                'data-[state=active]:bg-white data-[state=active]:text-blue-800 data-[state=active]:shadow-sm',
                'data-[state=inactive]:text-slate-600 data-[state=inactive]:hover:text-slate-900',
              )}
            >
              Evaluación clínica
            </Tabs.Trigger>
            <Tabs.Trigger
              value="xai"
              className={cn(
                'flex-1 rounded-lg px-4 py-3 text-sm font-medium transition-all',
                'data-[state=active]:bg-white data-[state=active]:text-blue-800 data-[state=active]:shadow-sm',
                'data-[state=inactive]:text-slate-600 data-[state=inactive]:hover:text-slate-900',
              )}
            >
              Explicabilidad (XAI) y motor
            </Tabs.Trigger>
          </Tabs.List>

          <Tabs.Content value="clinical" className="outline-none">
            <div className="grid gap-8 lg:grid-cols-[minmax(0,1.1fr)_minmax(0,0.9fr)]">
              <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
                <h2 className="text-lg font-semibold text-slate-900">Memoria de trabajo</h2>
                <p className="mt-1 text-sm text-slate-600">Carga rápida para profesionales. Campos alineados al backend Pydantic.</p>

                <div className="mt-6 grid gap-4 sm:grid-cols-2">
                  <label className="flex flex-col gap-1.5 text-sm">
                    <span className="font-medium text-slate-700">Edad</span>
                    <input
                      type="number"
                      min={0}
                      max={120}
                      value={form.edad}
                      onChange={(e) => setForm((f) => ({ ...f, edad: Number(e.target.value) }))}
                      className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2.5 text-slate-900 outline-none ring-blue-100 transition focus:border-blue-400 focus:ring-2"
                    />
                  </label>
                  <label className="flex flex-col gap-1.5 text-sm">
                    <span className="font-medium text-slate-700">IMC</span>
                    <input
                      type="number"
                      min={0}
                      max={60}
                      step={0.1}
                      value={form.imc}
                      onChange={(e) => setForm((f) => ({ ...f, imc: Number(e.target.value) }))}
                      className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2.5 text-slate-900 outline-none transition focus:border-blue-400 focus:ring-2 focus:ring-blue-100"
                    />
                  </label>

                  <label className="flex flex-col gap-1.5 text-sm sm:col-span-2">
                    <span className="font-medium text-slate-700">Procedimiento deseado</span>
                    <select
                      value={form.procedimiento_deseado}
                      onChange={(e) =>
                        setForm((f) => ({
                          ...f,
                          procedimiento_deseado: e.target.value as MemoriaTrabajoPayload['procedimiento_deseado'],
                        }))
                      }
                      className="rounded-lg border border-slate-200 bg-white px-3 py-2.5 text-slate-900 outline-none focus:border-blue-400 focus:ring-2 focus:ring-blue-100"
                    >
                      <option value="abdominoplastía">Abdominoplastía</option>
                      <option value="liposucción">Liposucción</option>
                      <option value="ambos">Ambos</option>
                    </select>
                  </label>

                  <label className="flex flex-col gap-1.5 text-sm">
                    <span className="font-medium text-slate-700">Estabilidad del peso (1 estable - 10 inestable)</span>
                    <select
                      value={form.estabilidad_peso}
                      onChange={(e) =>
                        setForm((f) => ({
                          ...f,
                          estabilidad_peso: Number(e.target.value),
                        }))
                      }
                      className="rounded-lg border border-slate-200 bg-white px-3 py-2.5 text-slate-900 outline-none focus:border-blue-400 focus:ring-2 focus:ring-blue-100"
                    >
                      {scaleOptions.map((v) => (
                        <option key={v} value={v}>
                          {v}
                        </option>
                      ))}
                    </select>
                  </label>

                  <label className="flex flex-col gap-1.5 text-sm">
                    <span className="font-medium text-slate-700">Estado general de salud (1 malo - 10 bueno)</span>
                    <select
                      value={form.estado_general_salud}
                      onChange={(e) =>
                        setForm((f) => ({
                          ...f,
                          estado_general_salud: Number(e.target.value),
                        }))
                      }
                      className="rounded-lg border border-slate-200 bg-white px-3 py-2.5 text-slate-900 outline-none focus:border-blue-400 focus:ring-2 focus:ring-blue-100"
                    >
                      {scaleOptions.map((v) => (
                        <option key={v} value={v}>
                          {v}
                        </option>
                      ))}
                    </select>
                  </label>

                  <label className="flex flex-col gap-1.5 text-sm sm:col-span-2">
                    <span className="font-medium text-slate-700">Antecedentes quirúrgicos</span>
                    <select
                      value={form.antecedentes_quirurgicos}
                      onChange={(e) =>
                        setForm((f) => ({
                          ...f,
                          antecedentes_quirurgicos: e.target
                            .value as MemoriaTrabajoPayload['antecedentes_quirurgicos'],
                        }))
                      }
                      className="rounded-lg border border-slate-200 bg-white px-3 py-2.5 text-slate-900 outline-none focus:border-blue-400 focus:ring-2 focus:ring-blue-100"
                    >
                      <option value="sin antecedentes">Sin antecedentes</option>
                      <option value="cirugía previa sin complicaciones">Cirugía previa sin complicaciones</option>
                      <option value="cirugía previa con complicaciones">Cirugía previa con complicaciones</option>
                    </select>
                  </label>

                  <label className="flex flex-col gap-1.5 text-sm">
                    <span className="font-medium text-slate-700">Cicatrización (1 normal - 10 mala)</span>
                    <select
                      value={form.cicatrizacion}
                      onChange={(e) =>
                        setForm((f) => ({
                          ...f,
                          cicatrizacion: Number(e.target.value),
                        }))
                      }
                      className="rounded-lg border border-slate-200 bg-white px-3 py-2.5 text-slate-900 outline-none focus:border-blue-400 focus:ring-2 focus:ring-blue-100"
                    >
                      {scaleOptions.map((v) => (
                        <option key={v} value={v}>
                          {v}
                        </option>
                      ))}
                    </select>
                  </label>

                  <label className="flex flex-col gap-1.5 text-sm">
                    <span className="font-medium text-slate-700">Estado psicológico</span>
                    <select
                      value={form.estado_psicologico}
                      onChange={(e) =>
                        setForm((f) => ({
                          ...f,
                          estado_psicologico: e.target.value as MemoriaTrabajoPayload['estado_psicologico'],
                        }))
                      }
                      className="rounded-lg border border-slate-200 bg-white px-3 py-2.5 text-slate-900 outline-none focus:border-blue-400 focus:ring-2 focus:ring-blue-100"
                    >
                      <option value="estable">Estable</option>
                      <option value="dudoso">Dudoso</option>
                      <option value="inestable">Inestable</option>
                    </select>
                  </label>

                  <label className="flex flex-col gap-1.5 text-sm sm:col-span-2">
                    <span className="font-medium text-slate-700">Expectativas</span>
                    <select
                      value={form.expectativas}
                      onChange={(e) =>
                        setForm((f) => ({
                          ...f,
                          expectativas: e.target.value as MemoriaTrabajoPayload['expectativas'],
                        }))
                      }
                      className="rounded-lg border border-slate-200 bg-white px-3 py-2.5 text-slate-900 outline-none focus:border-blue-400 focus:ring-2 focus:ring-blue-100"
                    >
                      <option value="realistas">Realistas</option>
                      <option value="poco claras">Poco claras</option>
                      <option value="irreales">Irreales</option>
                    </select>
                  </label>
                </div>

                <div className="mt-6 grid gap-3 sm:grid-cols-2">
                  <Toggle
                    checked={form.enfermedad_no_controlada}
                    onChange={(v) => setForm((f) => ({ ...f, enfermedad_no_controlada: v }))}
                    label="Enfermedad no controlada"
                  />
                  <Toggle
                    checked={form.tabaquismo}
                    onChange={(v) => setForm((f) => ({ ...f, tabaquismo: v }))}
                    label="Tabaquismo"
                  />
                  <Toggle
                    checked={form.consume_drogas}
                    onChange={(v) => setForm((f) => ({ ...f, consume_drogas: v }))}
                    label="Consume drogas"
                  />
                  <Toggle
                    checked={form.informacion_completa}
                    onChange={(v) => setForm((f) => ({ ...f, informacion_completa: v }))}
                    label="Información completa"
                    description="Desactivar para simular regla R1"
                  />
                </div>

                <button
                  type="button"
                  onClick={evaluar}
                  disabled={loading}
                  className={cn(
                    'mt-8 w-full rounded-xl px-4 py-3.5 text-sm font-semibold text-white shadow-md transition',
                    'bg-gradient-to-r from-blue-600 to-blue-700 hover:from-blue-700 hover:to-blue-800',
                    'focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600',
                    'disabled:cursor-not-allowed disabled:opacity-60',
                  )}
                >
                  {loading ? 'Evaluando paciente…' : 'Evaluar paciente'}
                </button>
              </section>

              <aside className="flex flex-col gap-4">
                <div
                  className={cn(
                    'rounded-2xl border bg-white p-6 shadow-md ring-2',
                    palette?.ring ?? 'ring-slate-200',
                  )}
                >
                  <div
                    className={cn(
                      'mb-4 h-1.5 rounded-full bg-gradient-to-r',
                      palette?.bar ?? 'from-slate-300 to-slate-500',
                    )}
                  />
                  <h2 className="text-lg font-semibold text-slate-900">Resultado</h2>
                  {!result ? (
                    <p className="mt-4 text-sm text-slate-600">
                      Envíe el formulario para ver aptitud, riesgo y recomendaciones.
                    </p>
                  ) : (
                    <div className="mt-4 space-y-4">
                      <div>
                        <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Aptitud preliminar</p>
                        <p className={cn('mt-1 text-lg font-semibold', palette?.text)}>{result.aptitud_preliminar}</p>
                      </div>
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="text-xs font-semibold uppercase tracking-wide text-slate-500">Nivel de riesgo</span>
                        <span
                          className={cn(
                            'rounded-full border px-3 py-1 text-xs font-semibold uppercase tracking-wide',
                            riesgoBadgeClass(result.nivel_riesgo),
                          )}
                        >
                          {result.nivel_riesgo}
                        </span>
                        <span className="text-xs text-slate-500 tabular-nums">({result.nivel_riesgo_numerico})</span>
                      </div>
                      <div>
                        <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Recomendación</p>
                        <p className="mt-1 text-sm leading-relaxed text-slate-700">{result.recomendacion}</p>
                      </div>
                      <div>
                        <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Derivación sugerida</p>
                        <p className="mt-1 text-sm text-slate-800">{result.derivacion_sugerida}</p>
                      </div>
                    </div>
                  )}
                </div>

                <div className="rounded-xl border border-dashed border-slate-200 bg-slate-50/80 p-4 text-xs text-slate-600">
                  <p className="font-semibold text-slate-700">Semántica de color</p>
                  <ul className="mt-2 list-inside list-disc space-y-1">
                    <li>
                      <span className="font-medium text-emerald-700">Verde</span>: riesgo bajo / apto preliminar.
                    </li>
                    <li>
                      <span className="font-medium text-amber-800">Ámbar</span>: riesgo medio / apto con condiciones.
                    </li>
                    <li>
                      <span className="font-medium text-rose-700">Rojo</span>: riesgo alto o no apto preliminar.
                    </li>
                  </ul>
                </div>
              </aside>
            </div>
          </Tabs.Content>

          <Tabs.Content value="xai" className="outline-none">
            <div className="grid gap-8 lg:grid-cols-2">
              <section className="space-y-6">
                <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
                  <h2 className="text-lg font-semibold text-slate-900">Ruta del motor de inferencias</h2>
                  <p className="mt-1 text-sm text-slate-600">
                    Vista de auditoría del encadenamiento hacia adelante (reglas duras → difuso → decisión).
                  </p>
                  <ol className="relative mt-6 border-l border-slate-200 pl-6">
                    {steps.map((step) => (
                      <li key={step.id} className="mb-8 last:mb-0">
                        <span
                          className={cn(
                            'absolute -left-[9px] mt-1.5 h-4 w-4 rounded-full border-2 border-white shadow',
                            step.status === 'ok' && 'bg-emerald-500',
                            step.status === 'warn' && 'bg-amber-500',
                            step.status === 'fail' && 'bg-rose-500',
                            step.status === 'skip' && 'bg-slate-300',
                            step.status === 'pending' && 'bg-slate-200',
                          )}
                        />
                        <p className="text-xs font-semibold uppercase tracking-wide text-blue-800">{step.subtitle}</p>
                        <h3 className="text-base font-semibold text-slate-900">{step.title}</h3>
                        <p className="mt-1 text-sm text-slate-600">{step.detail}</p>
                      </li>
                    ))}
                  </ol>
                </div>

                <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
                  <h2 className="text-lg font-semibold text-slate-900">Reglas activadas</h2>
                  <p className="mt-1 text-sm text-slate-600">Etiquetas devueltas por la API (justificación del caso).</p>
                  <div className="mt-4 flex flex-wrap gap-2">
                    {result?.reglas_activadas?.length ? (
                      result.reglas_activadas.map((r) => (
                        <span
                          key={r}
                          className={cn(
                            'inline-flex items-center rounded-full border px-3 py-1 text-xs font-semibold',
                            ruleChipClass(r),
                          )}
                        >
                          {r}
                        </span>
                      ))
                    ) : (
                      <span className="text-sm text-slate-500">Aún no hay evaluación. Ejecute desde la pestaña clínica.</span>
                    )}
                  </div>
                </div>
              </section>

              <section className="space-y-6">
                <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
                  <h2 className="text-lg font-semibold text-slate-900">Fuzzificación (membresía)</h2>
                  <p className="mt-1 text-sm text-slate-600">
                    Visualización local de μ con los mismos parámetros triangulares/trapezoidales del informe. Los valores
                    de la escala se usan de forma directa (1 a 10), como en el backend Python.
                  </p>
                  <div className="mt-6 grid gap-4 sm:grid-cols-1">
                    <MembershipBars title={`Edad (${form.edad} años)`} rows={fuzzPanels.edad} />
                    <MembershipBars title={`IMC (${form.imc})`} rows={fuzzPanels.imc} />
                    <MembershipBars
                      title={`Estabilidad del peso → escala (${form.estabilidad_peso.toFixed(1)}/10)`}
                      rows={fuzzPanels.est}
                    />
                    <MembershipBars
                      title={`Estado de salud → escala (${form.estado_general_salud.toFixed(1)}/10)`}
                      rows={fuzzPanels.sal}
                    />
                    <MembershipBars
                      title={`Expectativas → escala (${expectativasCRISP(form.expectativas).toFixed(1)}/10)`}
                      rows={fuzzPanels.exp}
                    />
                  </div>
                </div>

                <div className="rounded-2xl border border-blue-100 bg-gradient-to-br from-blue-50/90 to-white p-6 shadow-md ring-1 ring-blue-100">
                  <h2 className="text-lg font-semibold text-slate-900">Defuzzificación</h2>
                  <p className="mt-2 text-sm font-medium text-blue-900">
                    Método: <span className="font-bold">Centroide (centro de gravedad)</span>
                  </p>
                  <p className="mt-1 text-sm text-slate-600">
                    El backend usa scikit-fuzzy con salida en [0, 100]. El valor numérico consolidado es el que muestra el
                    medidor.
                  </p>
                  <div className="mt-6">
                    {result ? (
                      <>
                        <div className="flex items-baseline justify-between gap-2">
                          <span className="text-sm font-medium text-slate-700">Índice de riesgo difuso</span>
                          <span className="text-3xl font-bold tabular-nums text-blue-900">
                            {result.nivel_riesgo_numerico.toFixed(1)}
                          </span>
                        </div>
                        <div className="mt-4">
                          <RiskGauge value={result.nivel_riesgo_numerico} />
                        </div>
                      </>
                    ) : (
                      <p className="text-sm text-slate-500">Ejecute una evaluación para ver el valor defuzzificado.</p>
                    )}
                  </div>
                </div>
              </section>
            </div>
          </Tabs.Content>
        </Tabs.Root>
      </main>
    </div>
  )
}
