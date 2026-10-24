"use client"

import { useRef, useState, type FormEvent } from "react"
import { toast } from "sonner"

import { Button } from "@/components/ui/button"
import { Field, FieldDescription, FieldError, FieldGroup, FieldLabel } from "@/components/ui/field"
import { Input } from "@/components/ui/input"
import { Spinner } from "@/components/ui/spinner"
import { Textarea } from "@/components/ui/textarea"
import { useSaveContact } from "@/features/profile/api"
import { ApiError, errorMessage, type Schemas } from "@/lib/api/client"

type Values = { full_name: string; email: string; phone: string; city: string; links: string }
type Errors = Partial<Record<keyof Values, string>>

const FIELD_ORDER: (keyof Values)[] = ["full_name", "email", "phone", "city", "links"]

function toValues(contact: Schemas["ContactOut"] | Schemas["ContactDetails"] | null | undefined): Values {
  return {
    full_name: contact?.full_name ?? "",
    email: contact?.email ?? "",
    phone: contact?.phone ?? "",
    city: contact?.city ?? "",
    links: (contact?.links ?? []).join("\n"),
  }
}

function linesOf(text: string) {
  return text.split("\n").map((line) => line.trim()).filter(Boolean)
}

function validate(values: Values): Errors {
  const errors: Errors = {}
  if (!values.full_name.trim()) errors.full_name = "Enter your name as it should appear on your resume."
  if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(values.email.trim())) errors.email = "Enter an email address like you@example.com."
  const links = linesOf(values.links)
  if (links.length > 10) errors.links = "Add at most 10 links."
  else if (links.some((link) => link.length < 4)) errors.links = "Each line should be a full link, like linkedin.com/in/you."
  return errors
}

/**
 * Name, email, phone, city and links: the header of every resume and letter. They're stored apart from the
 * profile and never sent to the AI (CLAUDE.md non-negotiable #2), which the form says so people trust it.
 */
export function ContactForm({ contact }: { contact: Schemas["ContactOut"] | Schemas["ContactDetails"] | null }) {
  const save = useSaveContact()
  const [values, setValues] = useState<Values>(() => toValues(contact))
  const [errors, setErrors] = useState<Errors>({})
  const formRef = useRef<HTMLFormElement>(null)

  function update(field: keyof Values, value: string) {
    setValues((current) => ({ ...current, [field]: value }))
    if (errors[field]) setErrors((current) => ({ ...current, [field]: undefined }))
  }

  function submit(event: FormEvent) {
    event.preventDefault()
    const found = validate(values)
    setErrors(found)
    const first = FIELD_ORDER.find((field) => found[field])
    if (first) {
      formRef.current?.querySelector<HTMLElement>(`[name="${first}"]`)?.focus() // take the user to the first problem
      return
    }
    save.mutate(
      {
        full_name: values.full_name.trim(),
        email: values.email.trim(),
        phone: values.phone.trim() || null,
        city: values.city.trim() || null,
        links: linesOf(values.links),
      },
      {
        onSuccess: () => toast.success("Contact details saved"),
        onError: (error) => {
          if (!(error instanceof ApiError && error.code === "validation_error")) toast.error(errorMessage(error))
        },
      },
    )
  }

  const serverError = save.isError ? errorMessage(save.error) : null

  return (
    <form ref={formRef} onSubmit={submit} noValidate className="flex flex-col gap-6">
      <FieldGroup className="grid gap-5 sm:grid-cols-2">
        <TextField name="full_name" label="Full name" autoComplete="name" required values={values} errors={errors} onChange={update} />
        <TextField name="email" label="Email" type="email" inputMode="email" autoComplete="email" required values={values} errors={errors} onChange={update} />
        <TextField name="phone" label="Phone" type="tel" inputMode="tel" autoComplete="tel" values={values} errors={errors} onChange={update} />
        <TextField name="city" label="City" autoComplete="address-level2" hint="City and region, e.g. Austin, TX" values={values} errors={errors} onChange={update} />
        <Field className="sm:col-span-2" data-invalid={errors.links ? true : undefined}>
          <FieldLabel htmlFor="links">Links</FieldLabel>
          <Textarea
            id="links"
            name="links"
            rows={3}
            value={values.links}
            onChange={(event) => update("links", event.target.value)}
            aria-invalid={errors.links ? true : undefined}
            aria-describedby="links-hint"
            placeholder={"linkedin.com/in/you\ngithub.com/you"}
          />
          <FieldDescription id="links-hint">One per line: LinkedIn, GitHub, portfolio. Up to 10.</FieldDescription>
          {errors.links && <FieldError>{errors.links}</FieldError>}
        </Field>
      </FieldGroup>
      {serverError && <p role="alert" className="text-sm text-destructive">{serverError}</p>}
      <div className="flex flex-wrap items-center gap-3">
        <Button type="submit" disabled={save.isPending}>
          {save.isPending && <Spinner />}
          Save contact details
        </Button>
        <p className="text-sm text-muted-foreground">Kept separate from your profile and never sent to the AI.</p>
      </div>
    </form>
  )
}

function TextField({
  name, label, hint, required, values, errors, onChange, ...inputProps
}: {
  name: keyof Values
  label: string
  hint?: string
  required?: boolean
  values: Values
  errors: Errors
  onChange: (field: keyof Values, value: string) => void
} & Pick<React.ComponentProps<"input">, "type" | "inputMode" | "autoComplete">) {
  const error = errors[name]
  const describedBy = [hint && `${name}-hint`, error && `${name}-error`].filter(Boolean).join(" ") || undefined
  return (
    <Field data-invalid={error ? true : undefined}>
      <FieldLabel htmlFor={name}>
        {label}
        {required && <span aria-hidden className="text-destructive">*</span>}
      </FieldLabel>
      <Input
        id={name}
        name={name}
        value={values[name]}
        required={required}
        aria-required={required}
        aria-invalid={error ? true : undefined}
        aria-describedby={describedBy}
        onChange={(event) => onChange(name, event.target.value)}
        {...inputProps}
      />
      {hint && <FieldDescription id={`${name}-hint`}>{hint}</FieldDescription>}
      {error && <FieldError id={`${name}-error`}>{error}</FieldError>}
    </Field>
  )
}
