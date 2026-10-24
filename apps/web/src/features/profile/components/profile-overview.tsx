import type { ReactNode } from "react"

import { Badge } from "@/components/ui/badge"
import type { Schemas } from "@/lib/api/client"
import { formatMonth } from "@/lib/format"

type Profile = Schemas["CareerProfile"]
type Fact = Schemas["Fact"]

/**
 * What we understood from the resume, read-only. Every generated bullet must cite one of these facts, so this is
 * the boundary of what the AI may say about the person.
 */
export function ProfileOverview({ profile }: { profile: Profile }) {
  return (
    <div className="flex flex-col gap-8">
      {profile.headline && <p className="text-lg font-medium">{profile.headline}</p>}

      {profile.experience.length > 0 && (
        <Section title="Experience">
          {profile.experience.map((role) => (
            <Entry
              key={role.id}
              title={role.title}
              org={role.company}
              meta={[`${formatMonth(role.start)} – ${formatMonth(role.end)}`, role.location].filter(Boolean).join(" · ")}
              facts={role.facts}
            />
          ))}
        </Section>
      )}

      {profile.projects.length > 0 && (
        <Section title="Projects">
          {profile.projects.map((project) => (
            <Entry
              key={project.id}
              title={project.name}
              meta={[project.start && `${formatMonth(project.start)} – ${formatMonth(project.end)}`, project.link].filter(Boolean).join(" · ")}
              facts={project.facts}
            />
          ))}
        </Section>
      )}

      {profile.education.length > 0 && (
        <Section title="Education">
          {profile.education.map((school) => (
            <Entry
              key={school.id}
              title={[school.degree, school.field].filter(Boolean).join(", ")}
              org={school.institution}
              meta={[school.end && formatMonth(school.end), school.grade].filter(Boolean).join(" · ")}
              facts={school.facts}
            />
          ))}
        </Section>
      )}

      {profile.skills.length > 0 && (
        <Section title="Skills">
          <ul className="flex flex-wrap gap-2" aria-label="Skills">
            {profile.skills.map((skill) => (
              <li key={skill.name}>
                <Badge variant={skill.evidence_fact_ids.length ? "secondary" : "outline"} className="h-7 px-3 text-sm">
                  {skill.name}
                </Badge>
              </li>
            ))}
          </ul>
          <p className="text-sm text-muted-foreground">Outlined skills are listed on your resume but no achievement shows them yet.</p>
        </Section>
      )}

      {profile.certifications.length > 0 && (
        <Section title="Certifications">
          <ul className="flex flex-col gap-1">
            {profile.certifications.map((cert) => (
              <li key={cert.id}>
                {cert.name}
                <span className="text-muted-foreground">{[cert.issuer, cert.date && formatMonth(cert.date)].filter(Boolean).map((part) => ` · ${part}`)}</span>
              </li>
            ))}
          </ul>
        </Section>
      )}
    </div>
  )
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="flex flex-col gap-4">
      <h3 className="text-sm font-semibold tracking-wide text-muted-foreground uppercase">{title}</h3>
      {children}
    </section>
  )
}

function Entry({ title, org, meta, facts }: { title: string; org?: string; meta?: string; facts: Fact[] }) {
  return (
    <article className="flex flex-col gap-2">
      <div>
        <p className="font-medium">
          {title}
          {org && <span className="font-normal text-muted-foreground">, {org}</span>}
        </p>
        {meta && <p className="text-sm text-muted-foreground">{meta}</p>}
      </div>
      {facts.length > 0 && (
        <ul className="flex list-disc flex-col gap-1 pl-5 text-sm leading-relaxed">
          {facts.map((fact) => (
            <li key={fact.id}>{fact.text}</li>
          ))}
        </ul>
      )}
    </article>
  )
}
