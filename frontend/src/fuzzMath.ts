/**
 * Funciones triangulares y trapezoidales (misma semántica que el TP / scikit-fuzzy).
 * μ ∈ [0, 1]
 */

export function trimf(x: number, [a, b, c]: [number, number, number]): number {
  if (x <= a || x >= c) return 0
  if (x === b) return 1
  if (x < b) return (x - a) / (b - a)
  return (c - x) / (c - b)
}

export function trapmf(x: number, [a, b, c, d]: [number, number, number, number]): number {
  if (x <= a || x >= d) return 0
  if (x >= b && x <= c) return 1
  if (x < b) return (x - a) / (b - a)
  return (d - x) / (d - c)
}

export type LabeledDegree = { label: string; mu: number }

export function fuzzifyEdad(edad: number): LabeledDegree[] {
  const pairs: [string, number][] = [
    ['Adulto joven', trapmf(edad, [18, 18, 30, 40])],
    ['Adulto', trimf(edad, [30, 45, 60])],
    ['Adulto mayor', trapmf(edad, [55, 65, 80, 80])],
  ]
  return pairs.map(([label, mu]) => ({ label, mu }))
}

export function fuzzifyImc(imc: number): LabeledDegree[] {
  const pairs: [string, number][] = [
    ['Bajo', trapmf(imc, [0, 0, 17, 18.5])],
    ['Normal', trapmf(imc, [18, 18.5, 24.9, 26])],
    ['Moderadamente elevado', trimf(imc, [25, 27.5, 30])],
    ['Elevado', trimf(imc, [29, 32.5, 35])],
    ['Muy elevado', trapmf(imc, [34, 35, 45, 45])],
  ]
  return pairs.map(([label, mu]) => ({ label, mu }))
}

/** Escala 0–10: 0 estable, 10 muy inestable (coincide con backend). */
export function estabilidadCRISP(
  estabilidad: 'estable' | 'poco estable' | 'inestable',
): number {
  const m = { estable: 1.0, 'poco estable': 5.0, inestable: 9.0 }
  return m[estabilidad]
}

export function fuzzifyEstabilidad(v: number): LabeledDegree[] {
  const pairs: [string, number][] = [
    ['Estable', trapmf(v, [0, 0, 2, 4])],
    ['Poco estable', trimf(v, [3, 5, 7])],
    ['Inestable', trapmf(v, [6, 8, 10, 10])],
  ]
  return pairs.map(([label, mu]) => ({ label, mu }))
}

/** Escala 0–10: 0 malo, 10 bueno. */
export function saludCRISP(salud: 'bueno' | 'regular' | 'malo'): number {
  const m = { malo: 1.5, regular: 5.0, bueno: 9.0 }
  return m[salud]
}

export function fuzzifySalud(v: number): LabeledDegree[] {
  const pairs: [string, number][] = [
    ['Malo', trapmf(v, [0, 0, 2, 4])],
    ['Regular', trimf(v, [3, 5, 7])],
    ['Bueno', trapmf(v, [6, 8, 10, 10])],
  ]
  return pairs.map(([label, mu]) => ({ label, mu }))
}

/** Escala 0–10: 0 irreales, 10 realistas. */
export function expectativasCRISP(exp: 'realistas' | 'poco claras' | 'irreales'): number {
  const m = { irreales: 1.5, 'poco claras': 5.0, realistas: 9.0 }
  return m[exp]
}

export function fuzzifyExpectativas(v: number): LabeledDegree[] {
  const pairs: [string, number][] = [
    ['Irreales', trapmf(v, [0, 0, 2, 4])],
    ['Poco claras', trimf(v, [3, 5, 7])],
    ['Realistas', trapmf(v, [6, 8, 10, 10])],
  ]
  return pairs.map(([label, mu]) => ({ label, mu }))
}
