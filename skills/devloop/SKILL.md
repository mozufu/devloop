---
name: devloop
description: Execute one MyQue UUID with validated Zutai requirements, fresh review, consumer gates, and bound evidence. Use for spec-driven implementation or next-milestone integration.
---

# One canonical work item

1. Read the consuming repository's contribution, testing, approval, and execution rules. They own policy; this skill does not override them. Identify its configured policy, execution inputs, target and image identities. Never invent an approval.
2. Select a full canonical MyQue UUID explicitly or with `devloop select`. Never discover work through Markdown checkboxes or create a second state store. Use `myque api get UUID` and `devloop render` to read the structured requirements as prose. `devloop validate UUID --policy POLICY` must succeed before implementation. Plain legacy items are not silently adopted.
3. Start with `devloop start UUID --policy POLICY`. Dependency or approval refusal leaves the item unstarted. If already active after interruption, re-read it, validate again and resume by the same UUID; do not admit another item. Reopened items must start again to rotate the execution epoch.
4. Implement the stated problem and requirements, not a convenient subset. Run the real application when required. Keep gate scripts and all relevant implementation paths in consumer policy `codePaths`; no item-supplied shell commands. The body is an inert canonical requirements snapshot, not an editable source companion.
5. Obtain a fresh independent review after implementation. Review actual code and requirements, not merely successful tool output. Apply every required fix. Repeat review when findings change the implementation materially. Follow the consumer's commit and contribution rules; this skill grants no push, publication, or merge authority.
6. Run `devloop gate UUID ACCEPTANCE --policy POLICY --inputs INPUTS --target TARGET --image IMAGE` for each automated obligation. Failed execution or predicates prevent acceptance and are historical evidence, never success. Correct failures and rerun; changed source, policy, inputs, helpers, target/image, or requirements make old evidence stale.
7. Human or physical observations remain explicitly pending. Ask the authorized observer for actual observations, then use `devloop human UUID ACCEPTANCE ... --observations OBSERVATIONS --observer NAME`. Do not generate approval files or claim that a predicate proves the observation happened. Stop waiting without closing if the observer is unavailable.
8. Run `devloop eligible UUID ...`, then `devloop complete UUID ...` only with current real consumer approval. These tools check MyQue dependency completion, current evidence and policy; they do not redefine the graph. Direct `myque close` bypasses this skill's evidence boundary and must not be used to evade it.

# Interruption and retention

After a CAS conflict, re-read and revalidate; never overwrite competing records. Admission retries reuse the original persisted token and payload, never a new token. Evidence is appended only to the devloop consumer record. Temporary native wrappers are deleted; author `.zt` files are not copied into the store. Retired items expose identity but may lack bodies offline; use MyQue's supported history recovery, never synthesize missing requirements.

# Next-milestone integration

An owning next-milestone skill delegates its UUID-backed execution cycle here after applying its own planning, audit and publication rules. Do not copy that skill's body, discover a different roadmap item, or mark a Markdown checkbox as the canonical state transition.
