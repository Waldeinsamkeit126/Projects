import json
import pandas as pd

path = r"C:\Users\zhhzh\Documents\Codex\2026-08-26\x20-x20-2\outputs\table_competition_solution\submission-final-v6-excel.xlsx"

default_df = pd.read_excel(path)
literal_df = pd.read_excel(path, dtype=str, keep_default_na=False)

default_missing = default_df[default_df["answer"].isna()][["id", "answer"]]
literal_answers = literal_df.loc[default_missing.index, ["id", "answer"]]
print(json.dumps({
    "default_shape": list(default_df.shape),
    "literal_shape": list(literal_df.shape),
    "columns": list(default_df.columns),
    "default_missing_ids": [str(value) for value in default_missing["id"].tolist()],
    "literal_values_at_default_missing": literal_answers.to_dict(orient="records"),
    "default_id_dtype": str(default_df["id"].dtype),
    "default_answer_dtype": str(default_df["answer"].dtype),
    "literal_id_dtype": str(literal_df["id"].dtype),
    "duplicate_ids": int(literal_df["id"].duplicated().sum()),
    "literal_blank_answers": int(literal_df["answer"].str.strip().eq("").sum()),
}, ensure_ascii=False, indent=2))
