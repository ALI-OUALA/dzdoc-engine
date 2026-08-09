# Invoice-DZ checkpoint — 2026-08-09

Dataset: four original DZ-Bench invoice PNGs (clean, compressed, photographed, skewed),
seed 23. Host: Intel Core i7-1360P CPU, 31.7 GiB RAM, no NVIDIA GPU. Weights were official
immutable PP-OCRv5 revisions. Scores include every page.

| System | CER | WER | Field F1 | Financial accuracy | Runtime/page | Peak RSS |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Arabic recognizer only | 0.6475 | 0.7857 | 0.8829 | 0.9000 | 52.26 s | 365.7 MB |
| Arabic-probe routed Arabic/Latin | 0.6516 | 0.7812 | 0.9050 | 0.9500 | 40.47 s | 371.5 MB |

The routed path was faster and its validated extraction was stronger, despite slightly
worse raw CER. Digit-exact page accuracy was 0 for both, table structure similarity was
0, and routed hallucinated-block rate was 0.68. The document pack recovered split OCR
evidence through field aliases, geometric sequences, and arithmetic agreement: routed
field precision 0.9853, recall 0.8375, exact accuracy 0.8375, with zero structured-field
hallucination on this synthetic slice. These are not real-invoice claims.

On the clean page only, a hybrid run capped at one fallback improved CER from 0.6831 to
0.6093. Field F1 remained 0.9474 and financial accuracy remained 1.0. Runtime rose from
15.67 to 87.89 seconds; the accepted VLM event itself took 71.73 seconds and preserved
its prompt, raw response, immutable revision, confidence change, and reason. A separate
cold region run took 87.736 seconds and exactly restored the difficult mixed TTC line.
The fallback therefore stays disabled by default and should be reserved for unresolved
high-value regions. Raw reports live under `E:\dev\data\dzdoc-invoice-bench`.
