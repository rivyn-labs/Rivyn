# Triage Baseline: Measured Pipeline vs. Modeled Manual Review

## What AETHER measures today

For every ingestion run, AETHER measures its own end-to-end pipeline time:

1. parse and normalize the selected logs;
2. score anomalies;
3. correlate incidents;
4. generate deterministic evidence-grounded explanations.

The dashboard compares that elapsed time with a **modeled manual baseline** of
**15 seconds per anomalous log**. The model is explicit in both the API and UI:

```
modeled_manual_seconds = anomaly_count x 15 seconds
speedup = modeled_manual_seconds / measured_pipeline_seconds
```

This is a repeatable operational estimate, not a claim that a human was timed.
It allows runs on different datasets to be compared while avoiding the false
precision of treating an assumption as an experiment.

## Human-review comparison protocol

Use this short protocol for a final demo or post-hackathon evaluation:

1. Randomly select 50 anomalous lines from a LogHub dataset and keep the line
   IDs fixed for both conditions.
2. Ask 2--3 reviewers to identify the likely incident, evidence lines, and a
   recommended next action using raw logs only. Record elapsed time and whether
   the identified incident matches the known label or team-agreed rubric.
3. Run the same slice through AETHER. Record its measured pipeline duration,
   top ranked incident, cited evidence, and recommendation.
4. Report the median reviewer time, AETHER time, agreement rate, and the
   number of evidence links. Do not combine this human result with the modeled
   baseline; show them as separate rows.

## Reporting template

| Condition | Slice | Time | Output quality |
|---|---:|---:|---|
| Manual, raw logs | 50 fixed anomalies | median of reviewers | agreement rate + evidence links |
| AETHER pipeline | same 50 anomalies | measured wall-clock time | top-incident agreement + evidence links |
| Modeled baseline | all detected anomalies | 15 sec/anomaly assumption | planning estimate only |

## Limitations

- The 15-second value is an assumption and must be presented as such.
- A human comparison must use the same fixed slice and rubric in both arms.
- Results from LogHub research data do not imply production SLO performance.
