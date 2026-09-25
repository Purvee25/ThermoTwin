import { z } from 'zod'

const API_URL = import.meta.env.VITE_API_URL ?? '/api'

const Flag = z.object({ drug_class: z.string(), note: z.string() })

export const PatientSummary = z.object({
  patient_id: z.string(),
  name: z.string(),
  age: z.number(),
  sex: z.string(),
  occupation: z.string(),
  medications: z.array(z.string()),
  flags: z.array(Flag),
  learned_bias_c: z.number(),
  risk_now: z.number().nullable(),
  p_above_now: z.number().nullable(),
  peak_risk: z.number(),
  status: z.enum(['red', 'amber', 'green']),
  first_alert_clock: z.string().nullable(),
})
export type PatientSummary = z.infer<typeof PatientSummary>

const Point = z.object({
  minute: z.number(),
  clock: z.string(),
  twin_core_c: z.number(),
  band_low_c: z.number(),
  band_high_c: z.number(),
  true_core_c: z.number(),
  heart_rate: z.number(),
  air_temp_c: z.number(),
  activity_par: z.number(),
  risk_60: z.number().nullable(),
  p_above_now: z.number(),
  alert: z.boolean(),
})
export type Point = z.infer<typeof Point>

export const Timeline = z.object({
  patient_id: z.string(),
  date: z.string(),
  danger_core_c: z.number(),
  points: z.array(Point),
})
export type Timeline = z.infer<typeof Timeline>

const Scenario = z.object({
  peak_twin_core_c: z.number(),
  alert_minutes: z.number(),
  true_danger_minutes: z.number(),
})
export type Scenario = z.infer<typeof Scenario>

export const WhatIf = z.object({ baseline: Scenario, scenario: Scenario, timeline: Timeline })
export type WhatIf = z.infer<typeof WhatIf>

export const Meta = z.object({
  location: z.string(),
  date: z.string(),
  max_air_temp_c: z.number(),
  danger_core_c: z.number(),
  alert_probability: z.number(),
  disclaimer: z.string(),
})
export type Meta = z.infer<typeof Meta>

async function request<T>(schema: z.ZodType<T>, path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, init)
  if (!response.ok) throw new Error(`${response.status} ${response.statusText} for ${path}`)
  return schema.parse(await response.json())
}

export const api = {
  meta: () => request(Meta, '/meta'),
  patients: (minute: number) => request(z.array(PatientSummary), `/patients?minute=${minute}`),
  timeline: (id: string) => request(Timeline, `/patients/${encodeURIComponent(id)}/timeline`),
  whatIf: (id: string, startMinute: number, durationMin: number) =>
    request(WhatIf, `/patients/${encodeURIComponent(id)}/whatif`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ start_minute: startMinute, duration_min: durationMin }),
    }),
}
