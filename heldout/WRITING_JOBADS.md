# Writing a held-out set of job ads for the AGG check

Before a job is published, the system checks its title and text for wording that the German
General Equal Treatment Act (AGG) treats as discrimination, and for a German-language requirement
without a reason. A held-out set measures that check on ads it has never seen. Write it without
having seen the checker, its word lists or its tests: read this file and nothing else in the
repository.

## What to write

Job ads of the kind small and mid-sized German employers post for skilled and semi-skilled work
(care, crafts, logistics, driving, kitchens, production), mostly in German, a few in English.
Titles plus two to six sentences of text, as they appear on job boards: benefits, tasks, the team,
what the employer expects.

About 40% should be clean. The rest contain one or two problems from the list below, phrased the
many ways real ads phrase them: directly ("Muttersprache Deutsch"), softened ("idealerweise
Muttersprachler"), hidden in team descriptions ("unser junges, dynamisches Team"), in
requirements ("max. 35 Jahre"), in English. Include hard clean cases too: diversity statements that
name the same words ("Wir freuen uns über alle Bewerbungen, unabhängig von Alter, Herkunft und
Religion"), "junior" or "Berufseinsteiger" without an age, legally required certificates
("Gesundheitszeugnis nach § 43 IfSG" in a kitchen), titles that use a gender star or colon form.

Content rules: everyday hiring only. Nothing sexual, nobody under 18, invented company names, links
only at `.example` domains.

## Problems and their ids

| id | Problem |
|---|---|
| `origin-native-language` | asks for German as a mother tongue, a native speaker or accent-free German |
| `origin-nationality` | asks for a nationality, citizenship or origin |
| `age` | an age limit, an age range, or describes the wanted person or team as young |
| `gender-only` | addresses only one gender in the text ("Mitarbeiterin gesucht", "we are looking for a man") |
| `gender-title` | the title has no all-gender marker such as (m/w/d), (w/m/d), (all genders), Mitarbeiter\*in, Mitarbeiter:in |
| `family` | asks about marital status or children |
| `pregnancy-health` | asks about pregnancy, disability or health beyond what a law requires |
| `religion` | requires a religion or church membership (by a non-religious employer) |
| `photo` | asks for a photo |
| `physical` | describes the person's body instead of the work ("kräftig", "körperlich belastbar") |
| `german-without-reason` | the ad sets a minimum German level (field `german_level`) without saying why the work needs it |

## The file

One YAML file, `ads.yaml`, in a new directory `heldout/jobads-vN/` (next free N), plus a file
`STATUS` containing the single word `heldout`.

```yaml
ads:
  - id: ad-001
    title: "Koch (m/w/d) für unser Bistro"
    text: "Wir suchen Verstärkung für unser junges Team in Köln-Ehrenfeld. ..."
    german_level: {min: B1, justification: ""}   # optional; leave out if the ad sets no level
    expect: [age, german-without-reason]          # every problem in the ad; [] if clean
```

Write 80 to 120 ads. Do not run the checker on them. Do not change them after the first run is
recorded; if someone studies the failures afterwards, the set becomes a regression set (`STATUS`
says `regression`) and someone else writes a new one from this file.
