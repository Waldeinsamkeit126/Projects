import json
import sys
import pandas as pd

sys.stdout.reconfigure(encoding="utf-8")

path = r"D:\tests.xlsx"
df = pd.read_excel(path, dtype=str, keep_default_na=False)
answer_nonblank = df[df["answer"].str.strip().ne("")]
unexpected_question_types = df[~df["question_type"].isin(["extract", "thinking", "structure"])]
structure_non_json = df[(df["question_type"] == "structure") & (df["answer_format"] != "json")]

print(json.dumps({
    "shape": list(df.shape),
    "columns": list(df.columns),
    "answer_format_counts": df["answer_format"].value_counts().to_dict(),
    "question_type_counts": df["question_type"].value_counts().to_dict(),
    "nonblank_answer_count": int(len(answer_nonblank)),
    "nonblank_answer_examples": answer_nonblank[["id", "file_name", "question_type", "answer_format", "answer"]].head(30).to_dict(orient="records"),
    "last_nonblank_answer_examples": answer_nonblank[["id", "file_name", "question_type", "answer_format", "answer"]].tail(10).to_dict(orient="records"),
    "unexpected_question_type_rows": unexpected_question_types.to_dict(orient="records"),
    "structure_non_json_count": int(len(structure_non_json)),
    "structure_non_json_rows": structure_non_json[["id", "file_name", "question", "table_hint", "answer_format"]].to_dict(orient="records"),
}, ensure_ascii=False, indent=2))
