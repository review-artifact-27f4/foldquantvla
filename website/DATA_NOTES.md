# Manuscript source and editorial decisions

Source: the ten-page September 2026 revision entitled “FoldQuantVLA: Native Low-Bit Vision-Language-Action Inference with Consistent Folding and Closed-Loop Evaluation.” The PDF was visually checked during implementation. It is not part of the website artifact.

Tables take precedence over conflicting abstract/body statements, as requested. These notes are for maintainers only and are not deployed.

## Sources

| Dataset | Source | Scope |
| --- | --- | --- |
| Desktop | Table II, page 6 | RTX 4070 Ti SUPER, batch 1; full-chunk latency and separately labeled head-only rows |
| Jetson | Table III, page 7 | GR00T N1.6, Jetson AGX Orin, batch 1; GPU time, observation-to-action latency, engine bytes, build time |
| LIBERO | Table IV, page 7; K from Table I | 40 campaigns of 800 episodes, H100 MIG 3g.40gb |
| Method | Figure 1, page 4 | Consistent site transform, offline/online boundary, low-bit projection scope |
| Analysis | Section VI-B, pages 7–8 | Offline fidelity is not a reliable ordering of working closed-loop arms |

Published percentages and one-decimal Wilson endpoints are transcribed as printed (including ties such as 97.12 for 777/800). The exact success counts are retained. A standard-library test independently checks counts, rates, and interval rounding. Table II derived columns are transcribed, not recomputed from already-rounded times.

## Deliberately excluded or qualified

- “44 arm-versus-reference comparisons” is not reproducible from the 40 displayed rows, which include six BF16 references. The page reports the 40 campaigns and 32,000 episodes without that comparison count or multiplicity-derived statistical labels.
- Mixed precision is not evaluated on SmolVLA in Table IV. No all-six mixed-precision claim appears.
- The conclusion's 35.3 ms mixed-precision headline has no identified row/scope in the selected tables and is excluded.
- Table II's caption gives repeated 60-iteration measurements after ten warmups. Its local protocol is used instead of the different counts in Section IV.
- SmolVLA uniform W4A4 is marked as a throughput diagnostic, not an accurate fast policy. Evo-1 loses closed-loop successes at uniform W4A4; its 0.5 ms desktop regression versus W8A8 is below the paper's timing resolution.
- Jetson's 2.11× reduction describes serialized engine size, not peak memory, power, thermal behavior, or robot success.
- Native INT4 hardware claims name sm89 / sm87. The H100 success campaign uses the lowered INT8 datapath.
- Applying the input-dependent transform remains online inside the fused prologue. No “no online rotation” wording is used.
- Descriptive Wilson intervals do not establish equivalence. P1 and P2 observations/cosines are not merged.
- The real-robot reel is a reserved qualitative area. Until a protocol and quantitative results are added to the manuscript, its captions must not imply measured robustness, success rates, or deployment generalization.

The README and existing figure generators elsewhere in the repository may describe earlier results. They do not override these manuscript tables.
