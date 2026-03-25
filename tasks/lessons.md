# Lessons Learned

## 2026-03-20 — Pet Insurance Integration

### Synthetic time grain conversion works well
Converting quarterly data ("2024 Q4" -> 202412) to monthly YYYYMM format avoided touching any downstream time-series code. All existing trend, comparison, and slider logic worked unchanged.

### Backward-compatible parameter defaults prevent breakage
Adding `product="Motor"` defaults to `pivot_questions_to_wide()` and `question_set=None` to pivot helpers meant Motor/Home paths were completely untouched.

### Graceful degradation already built in
Pages 1-3 already handled missing Q-code columns by returning None from reason/channel functions. No guards needed for those pages.

### Product-aware awareness levels
Awareness levels (spontaneous/prompted/consideration) differ by product. Using a global `set_awareness_product()` is pragmatic but slightly fragile — if two pages run concurrently or forget to call it, wrong Q-codes get used. Consider refactoring to pass product explicitly through awareness functions.

### Pet EAV loader needs batching
Pet's 4 EAV tables (provider_data 199K rows, statement_data 337K rows) need per-quarter batching to stay under the 100K Power BI API limit, same lesson as Motor/Home.

### Free-text questions must not be multi-code pivoted
PET_SPONTANEOUS_AWARENESS ("List any providers you can think of?") was classified as MULTI_CODE, which creates a boolean column per unique answer. Free text means thousands of unique strings, causing a memory explosion during pivot. Free-text awareness questions need brand normalisation first (like Motor/Home Q1), not boolean pivot. Always check whether a question's answers are enumerated or free-text before classifying it.

### Isolate product loading failures
If one product's data load crashes (e.g. Pet pivot OOM), all other products that loaded successfully should still be saved to DuckDB. Wrap each product's load in try/except within init_ss_data so partial success is preserved. The original code had no error handling around _load_pet_data, so a Pet crash meant Motor and Home data (which loaded fine) were lost too.
