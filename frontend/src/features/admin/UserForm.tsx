import { zodResolver } from '@hookform/resolvers/zod'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Plus, Trash2 } from 'lucide-react'
import { useMemo, useState } from 'react'
import { useFieldArray, useForm } from 'react-hook-form'
import { z } from 'zod'

import { ErrorAlert, Field, Loading, NativeSelect } from '@/components/common'
import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Separator } from '@/components/ui/separator'
import { Textarea } from '@/components/ui/textarea'
import {
  CI_DEPARTMENTS,
  INSTITUTION_TYPES,
  useAcademicLevels,
  useInstitutions,
  usePositions,
  useRoles,
} from '@/features/admin/catalogs'
import { ME_KEY, useHasPermission } from '@/features/auth/useAuth'
import { api } from '@/lib/api'
import { ageOn, birthDateError, earliestGraduationYear, latestAdultBirthDate, MIN_AGE } from '@/lib/people'
import type { AcademicLevel, CiDepartment, DegreeInput, ProfileInput, Role, User, UserWithTemporaryPassword } from '@/types/api'

// Las reglas definitivas se validan en el backend; aquí se orienta al usuario mientras escribe.
// Vacío (apellido opcional) o con al menos una letra, igual que la API: «--» no es un nombre.
const NAME = /^(?:[A-Za-zÁÉÍÓÚÜÑáéíóúüñ' .-]*[A-Za-zÁÉÍÓÚÜÑáéíóúüñ][A-Za-zÁÉÍÓÚÜÑáéíóúüñ' .-]*)?$/
const EMAIL = /^[^@\s]+@[^@\s]+\.[^@\s]+$/
const optionalEmail = z.string().trim().refine((v) => v === '' || EMAIL.test(v), 'Correo no válido')
const currentYear = new Date().getFullYear()

function makeSchema(levels: AcademicLevel[]) {
  const levelById = new Map(levels.map((l) => [String(l.id), l]))
  return z
  .object({
    username: z.string().regex(/^[a-zA-Z0-9_.-]{3,64}$/, '3–64 caracteres: letras, números, punto, guion'),
    role_ids: z.array(z.number()).min(1, 'Asigne al menos un rol'),
    first_names: z.string().trim().min(2, 'Ingrese los nombres').regex(NAME, 'Solo letras'),
    paternal_surname: z.string().trim().regex(NAME, 'Solo letras'),
    maternal_surname: z.string().trim().regex(NAME, 'Solo letras'),
    ci_number: z.string().trim().regex(/^\d{4,10}$/, 'Solo números (4 a 10 dígitos)'),
    ci_complement: z.string().trim().regex(/^[0-9A-Za-z]{0,2}$/, 'Máximo 2 caracteres (p. ej. 1A)'),
    ci_issued_in: z.string(),
    institutional_email: optionalEmail,
    personal_email: optionalEmail,
    mobile_phone: z.string().trim().regex(/^[67]\d{7}$/, '8 dígitos, inicia en 6 o 7'),
    birth_date: z.string(),
    address: z.string().trim().max(255),
    position_id: z.string(),
    degrees: z.array(
      z.object({
        academic_level_id: z.string().min(1, 'Seleccione el nivel'),
        title: z.string().trim().min(3, 'Indique el título'),
        institution_id: z.string().min(1, 'Seleccione la institución'),
        graduation_year: z
          .string()
          .refine((v) => v === '' || (Number(v) >= 1950 && Number(v) <= currentYear), `Entre 1950 y ${currentYear}`),
      }),
    ),
  })
  .refine((v) => v.paternal_surname !== '' || v.maternal_surname !== '', {
    message: 'Indique al menos un apellido',
    path: ['paternal_surname'],
  })
  .superRefine((v, ctx) => {
    const birthError = birthDateError(v.birth_date)
    if (birthError) {
      ctx.addIssue({ code: 'custom', message: birthError, path: ['birth_date'] })
      return
    }
    // El año de egreso debe ser posible para la edad de la persona y el nivel del título.
    v.degrees.forEach((d, index) => {
      const level = levelById.get(d.academic_level_id)
      if (!level || !d.graduation_year) return
      const earliest = earliestGraduationYear(v.birth_date, level.min_graduation_age)
      if (Number(d.graduation_year) < earliest) {
        ctx.addIssue({
          code: 'custom',
          message: `Para ${level.name.toLowerCase()} el egreso debe ser desde ${earliest} (edad mínima ${level.min_graduation_age} años)`,
          path: ['degrees', index, 'graduation_year'],
        })
      }
    })
  })
}
type FormValues = z.infer<ReturnType<typeof makeSchema>>

const orNull = (v: string) => (v.trim() === '' ? null : v.trim())

function toPayload(v: FormValues): { profile: ProfileInput; degrees: DegreeInput[] } {
  return {
    profile: {
      first_names: v.first_names.trim(),
      paternal_surname: orNull(v.paternal_surname),
      maternal_surname: orNull(v.maternal_surname),
      ci_number: v.ci_number.trim(),
      ci_complement: orNull(v.ci_complement),
      ci_issued_in: (orNull(v.ci_issued_in) as CiDepartment | null) ?? null,
      institutional_email: orNull(v.institutional_email),
      personal_email: orNull(v.personal_email),
      mobile_phone: v.mobile_phone.trim(),
      birth_date: v.birth_date,
      address: orNull(v.address),
      position_id: v.position_id ? Number(v.position_id) : null,
    },
    degrees: v.degrees.map((d) => ({
      academic_level_id: Number(d.academic_level_id),
      title: d.title.trim(),
      institution_id: Number(d.institution_id),
      graduation_year: d.graduation_year ? Number(d.graduation_year) : null,
    })),
  }
}

function defaults(user?: User): FormValues {
  const p = user?.profile
  return {
    username: user?.username ?? '',
    role_ids: user?.roles.map((r) => r.id) ?? [],
    first_names: p?.first_names ?? '',
    paternal_surname: p?.paternal_surname ?? '',
    maternal_surname: p?.maternal_surname ?? '',
    ci_number: p?.ci_number ?? '',
    ci_complement: p?.ci_complement ?? '',
    ci_issued_in: p?.ci_issued_in ?? '',
    institutional_email: p?.institutional_email ?? '',
    personal_email: p?.personal_email ?? '',
    mobile_phone: p?.mobile_phone ?? '',
    birth_date: p?.birth_date ?? '',
    address: p?.address ?? '',
    position_id: p?.position ? String(p.position.id) : '',
    degrees:
      user?.degrees.map((d) => ({
        academic_level_id: String(d.academic_level.id),
        title: d.title,
        institution_id: String(d.institution.id),
        graduation_year: d.graduation_year ? String(d.graduation_year) : '',
      })) ?? [],
  }
}

function RoleChecklist({ roles, value, onChange }: { roles: Role[]; value: number[]; onChange: (ids: number[]) => void }) {
  return (
    <div className="flex flex-wrap gap-4">
      {roles.map((role) => (
        <label key={role.id} className="flex items-center gap-2 text-sm" title={role.description}>
          <Checkbox
            checked={value.includes(role.id)}
            onCheckedChange={(checked) => onChange(checked ? [...value, role.id] : value.filter((id) => id !== role.id))}
          />
          {role.name.replaceAll('_', ' ')}
        </label>
      ))}
    </div>
  )
}

function InstitutionQuickAdd({ onCreated }: { onCreated: (id: number) => void }) {
  const qc = useQueryClient()
  const [name, setName] = useState('')
  const [type, setType] = useState('universidad_publica')
  const [city, setCity] = useState('')
  const create = useMutation({
    mutationFn: async () =>
      (await api.post<{ id: number }>('/catalogs/institutions', { name, institution_type: type, city: city || null })).data,
    onSuccess: async (created) => {
      await qc.invalidateQueries({ queryKey: ['catalogs', 'institutions'] })
      setName('')
      setCity('')
      onCreated(created.id)
    },
  })
  return (
    <div className="bg-muted/40 grid gap-2 rounded-lg p-3 sm:grid-cols-[1fr_14rem_10rem_auto] sm:items-end">
      <Field label="Nueva institución" htmlFor="inst-name">
        <Input id="inst-name" value={name} onChange={(e) => setName(e.target.value)} />
      </Field>
      <Field label="Tipo" htmlFor="inst-type">
        <NativeSelect id="inst-type" value={type} onChange={(e) => setType(e.target.value)}>
          {INSTITUTION_TYPES.map((t) => (
            <option key={t.value} value={t.value}>
              {t.label}
            </option>
          ))}
        </NativeSelect>
      </Field>
      <Field label="Ciudad" htmlFor="inst-city">
        <Input id="inst-city" value={city} onChange={(e) => setCity(e.target.value)} />
      </Field>
      <Button type="button" variant="outline" disabled={name.trim().length < 3 || create.isPending} onClick={() => create.mutate()}>
        Agregar
      </Button>
      <div className="sm:col-span-4">
        <ErrorAlert error={create.error} />
      </div>
    </div>
  )
}

interface UserFormProps {
  user?: User
  /** `self`: el usuario edita su propio perfil (sin usuario, roles ni cargo). */
  mode?: 'admin' | 'self'
  onDone: (result: UserWithTemporaryPassword | null) => void
}

export function UserForm(props: UserFormProps) {
  const catalogs = [useRoles(props.mode !== 'self'), useAcademicLevels(), useInstitutions(), usePositions()]
  // Los <select> solo pueden mostrar el valor guardado si sus opciones ya existen al montarse.
  if (catalogs.some((c) => c.isLoading)) return <Loading label="Cargando catálogos…" />
  const failed = catalogs.find((c) => c.error)
  if (failed) return <ErrorAlert error={failed.error} />
  return <UserFormFields {...props} />
}

function UserFormFields({ user, mode = 'admin', onDone }: UserFormProps) {
  const isSelf = mode === 'self'
  const qc = useQueryClient()
  const roles = useRoles(!isSelf)
  const can = useHasPermission()
  const canAddInstitution = can('usuarios.gestionar')
  const levels = useAcademicLevels()
  const institutions = useInstitutions()
  const positions = usePositions()
  const [addingInstitutionFor, setAddingInstitutionFor] = useState<number | null>(null)
  const editing = Boolean(user)
  const schema = useMemo(() => makeSchema(levels.data ?? []), [levels.data])
  const form = useForm<FormValues>({ resolver: zodResolver(schema), defaultValues: defaults(user) })
  const degrees = useFieldArray({ control: form.control, name: 'degrees' })
  const birthDate = form.watch('birth_date')
  const validBirth = birthDateError(birthDate) === null

  const save = useMutation({
    mutationFn: async (v: FormValues) => {
      const body = toPayload(v)
      if (isSelf) {
        const { position_id: _position, ...personal } = body.profile
        await api.put('/auth/me/profile', { profile: personal, degrees: body.degrees })
        return null
      }
      if (user) {
        await api.put(`/users/${user.id}`, { ...body, role_ids: v.role_ids })
        return null
      }
      return (await api.post<UserWithTemporaryPassword>('/users', { ...body, username: v.username, role_ids: v.role_ids })).data
    },
    onSuccess: async (result) => {
      await qc.invalidateQueries({ queryKey: isSelf ? ME_KEY : ['users'] })
      onDone(result)
    },
  })
  const { errors } = form.formState
  const reg = form.register

  return (
    <form onSubmit={form.handleSubmit((v) => save.mutate(v))} className="grid gap-5" noValidate>
      {!isSelf && (
      <section className="grid gap-3">
        <h3 className="font-medium">Cuenta</h3>
        <div className="grid gap-3 sm:grid-cols-2">
          <Field label="Usuario" htmlFor="u-username" error={errors.username?.message}>
            <Input id="u-username" autoComplete="off" disabled={editing} {...reg('username')} />
          </Field>
        </div>
        <div className="grid gap-1.5">
          <Label>Roles</Label>
          <RoleChecklist
            roles={roles.data ?? []}
            value={form.watch('role_ids')}
            onChange={(ids) => form.setValue('role_ids', ids, { shouldValidate: true })}
          />
          {errors.role_ids && <p className="text-destructive text-xs">{errors.role_ids.message}</p>}
        </div>
      </section>
      )}
      {!isSelf && <Separator />}
      <section className="grid gap-3">
        <h3 className="font-medium">Datos personales</h3>
        <div className="grid gap-3 sm:grid-cols-3">
          <Field label="Nombres" htmlFor="u-first" error={errors.first_names?.message}>
            <Input id="u-first" {...reg('first_names')} />
          </Field>
          <Field label="Apellido paterno" htmlFor="u-pat" error={errors.paternal_surname?.message}>
            <Input id="u-pat" {...reg('paternal_surname')} />
          </Field>
          <Field label="Apellido materno" htmlFor="u-mat" error={errors.maternal_surname?.message}>
            <Input id="u-mat" {...reg('maternal_surname')} />
          </Field>
        </div>
        <div className="grid gap-3 sm:grid-cols-[1fr_8rem_12rem]">
          <Field label="Cédula de identidad (CI)" htmlFor="u-ci" error={errors.ci_number?.message}>
            <Input id="u-ci" inputMode="numeric" {...reg('ci_number')} />
          </Field>
          <Field label="Complemento" htmlFor="u-cic" error={errors.ci_complement?.message} hint="Si tiene (p. ej. 1A)">
            <Input id="u-cic" maxLength={2} {...reg('ci_complement')} />
          </Field>
          <Field label="Expedido en" htmlFor="u-cie">
            <NativeSelect id="u-cie" {...reg('ci_issued_in')}>
              <option value="">—</option>
              {CI_DEPARTMENTS.map((d) => (
                <option key={d.value} value={d.value}>
                  {d.value} — {d.label}
                </option>
              ))}
            </NativeSelect>
          </Field>
        </div>
        <div className="grid gap-3 sm:grid-cols-3">
          <Field label="Correo institucional" htmlFor="u-mail1" error={errors.institutional_email?.message}>
            <Input id="u-mail1" type="email" {...reg('institutional_email')} />
          </Field>
          <Field label="Correo personal" htmlFor="u-mail2" error={errors.personal_email?.message}>
            <Input id="u-mail2" type="email" {...reg('personal_email')} />
          </Field>
          <Field label="Número de celular" htmlFor="u-cel" error={errors.mobile_phone?.message}>
            <Input id="u-cel" inputMode="tel" maxLength={8} placeholder="7xxxxxxx" {...reg('mobile_phone')} />
          </Field>
        </div>
        <div className="grid gap-3 sm:grid-cols-[14rem_1fr]">
          <Field
            label="Fecha de nacimiento"
            htmlFor="u-birth"
            error={errors.birth_date?.message}
            hint={validBirth ? `Edad: ${ageOn(birthDate)} años` : `Mayor de ${MIN_AGE} años`}
          >
            <Input id="u-birth" type="date" min="1900-01-01" max={latestAdultBirthDate()} {...reg('birth_date')} />
          </Field>
          <Field label="Dirección" htmlFor="u-addr" error={errors.address?.message}>
            <Textarea id="u-addr" rows={2} placeholder="Comunidad, zona, calle y número" {...reg('address')} />
          </Field>
        </div>
      </section>

      <Separator />
      <section className="grid gap-3">
        <h3 className="font-medium">Información laboral</h3>
        <div className="grid gap-3 sm:grid-cols-2">
          {isSelf ? (
            <Field label="Cargo en el CEA" htmlFor="u-pos" hint="Lo asigna el administrador del sistema.">
              <Input id="u-pos" value={user?.profile?.position?.name ?? 'Sin cargo asignado'} disabled readOnly />
            </Field>
          ) : (
            <Field label="Cargo en el CEA" htmlFor="u-pos">
              <NativeSelect id="u-pos" {...reg('position_id')}>
                <option value="">—</option>
                {positions.data?.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name}
                  </option>
                ))}
              </NativeSelect>
            </Field>
          )}
        </div>
        <div className="flex items-center justify-between">
          <Label>Formación académica</Label>
          <Button
            type="button"
            size="sm"
            variant="outline"
            onClick={() => degrees.append({ academic_level_id: '', title: '', institution_id: '', graduation_year: '' })}
          >
            <Plus /> Título
          </Button>
        </div>
        {degrees.fields.length === 0 && <p className="text-muted-foreground text-sm">Sin títulos registrados.</p>}
        {degrees.fields.map((field, index) => {
          const e = errors.degrees?.[index]
          const level = levels.data?.find((l) => String(l.id) === form.watch(`degrees.${index}.academic_level_id`))
          const earliest = level && validBirth ? earliestGraduationYear(birthDate, level.min_graduation_age) : null
          return (
            <div key={field.id} className="grid gap-2 rounded-lg border p-3">
              <div className="grid gap-2 sm:grid-cols-[12rem_1fr_7rem_auto] sm:items-start">
                <Field label="Nivel" htmlFor={`d-level-${index}`} error={e?.academic_level_id?.message}>
                  <NativeSelect id={`d-level-${index}`} {...reg(`degrees.${index}.academic_level_id`)}>
                    <option value="">Seleccione…</option>
                    {levels.data?.map((l) => (
                      <option key={l.id} value={l.id}>
                        {l.name}
                      </option>
                    ))}
                  </NativeSelect>
                </Field>
                <Field label="Título obtenido" htmlFor={`d-title-${index}`} error={e?.title?.message}>
                  <Input
                    id={`d-title-${index}`}
                    placeholder="Ej.: Licenciatura en Ciencias de la Educación"
                    {...reg(`degrees.${index}.title`)}
                  />
                </Field>
                <Field
                  label="Año de egreso"
                  htmlFor={`d-year-${index}`}
                  error={e?.graduation_year?.message}
                  hint={earliest ? `Desde ${earliest}` : undefined}
                >
                  <Input id={`d-year-${index}`} inputMode="numeric" maxLength={4} {...reg(`degrees.${index}.graduation_year`)} />
                </Field>
                <Button type="button" variant="ghost" className="sm:mt-6" aria-label="Quitar título" onClick={() => degrees.remove(index)}>
                  <Trash2 />
                </Button>
              </div>
              <Field label="Institución de egreso" htmlFor={`d-inst-${index}`} error={e?.institution_id?.message}>
                <NativeSelect id={`d-inst-${index}`} {...reg(`degrees.${index}.institution_id`)}>
                  <option value="">Seleccione…</option>
                  {institutions.data?.map((i) => (
                    <option key={i.id} value={i.id}>
                      {i.name}
                      {i.acronym ? ` (${i.acronym})` : ''}
                    </option>
                  ))}
                </NativeSelect>
              </Field>
              {addingInstitutionFor === index ? (
                <InstitutionQuickAdd
                  onCreated={(id) => {
                    form.setValue(`degrees.${index}.institution_id`, String(id), { shouldValidate: true })
                    setAddingInstitutionFor(null)
                  }}
                />
              ) : canAddInstitution ? (
                <button
                  type="button"
                  className="text-muted-foreground w-fit text-xs underline decoration-primary decoration-2 underline-offset-4"
                  onClick={() => setAddingInstitutionFor(index)}
                >
                  ¿No está en la lista? Agregar institución
                </button>
              ) : (
                <p className="text-muted-foreground text-xs">
                  ¿No está en la lista? Solicite al administrador que la registre.
                </p>
              )}
            </div>
          )
        })}
      </section>

      <ErrorAlert error={save.error} />
      <div className="flex gap-2">
        <Button type="submit" disabled={save.isPending}>
          {editing || isSelf ? 'Guardar cambios' : 'Crear usuario'}
        </Button>
        <Button type="button" variant="ghost" onClick={() => onDone(null)}>
          Cancelar
        </Button>
      </div>
      {!editing && !isSelf && (
        <p className="text-muted-foreground text-xs">
          Se generará una contraseña temporal; el usuario deberá cambiarla en su primer inicio de sesión.
        </p>
      )}
    </form>
  )
}
