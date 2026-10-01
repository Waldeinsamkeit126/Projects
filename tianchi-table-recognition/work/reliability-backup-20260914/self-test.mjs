import assert from "node:assert/strict";
import { normalizeAnswer, normalizeQuestion, validateAnswer } from "./run.mjs";

const repaired = normalizeQuestion({
  id: 63,
  file_name: "008.pdf",
  question_type: "错位文本",
  question: "示例",
  table_hint: "11",
  answer_format: "json_array",
});
assert.equal(repaired.question_type, "extract");
assert.equal(repaired.table_hint, "");

const numberQuestion = { answer_format: "number", question_type: "extract" };
assert.equal(normalizeAnswer(numberQuestion, "125,000"), "125000");

const arrayQuestion = { answer_format: "json_array", question_type: "extract" };
assert.equal(normalizeAnswer(arrayQuestion, [{ 月份: "1月", 金额: "12" }]), '[{"月份":"1月","金额":"12"}]');
assert.equal(normalizeAnswer(arrayQuestion, [{ 月份: 1, 可用: true }]), '[{"月份":"1","可用":"true"}]');
assert.equal(validateAnswer(arrayQuestion, '[{"月份":"1月"}]').valid, true);
assert.equal(validateAnswer(arrayQuestion, '[{"月份":1}]').valid, false);
assert.equal(validateAnswer(arrayQuestion, '[{"可用":true}]').valid, false);
assert.equal(validateAnswer(arrayQuestion, '{"月份":"1月"}').valid, false);
assert.equal(validateAnswer(arrayQuestion, '["1月","2月"]').valid, false);
assert.equal(validateAnswer(arrayQuestion, '[{"月份":null}]').valid, false);
assert.equal(validateAnswer(arrayQuestion, '[]').valid, false);

const structureQuestion = { answer_format: "json", question_type: "structure" };
const validStructure = JSON.stringify({
  row_count: 2,
  col_count: 2,
  cells: [
    { text: "项目", row: 0, col: 0, rowspan: 1, colspan: 1 },
    { text: "金额", row: 0, col: 1, rowspan: 1, colspan: 1 },
  ],
});
assert.equal(validateAnswer(structureQuestion, validStructure).valid, true);
assert.equal(validateAnswer(structureQuestion, '{"row_count":2,"col_count":2,"cells":[{"text":"x","row":1,"col":1,"rowspan":2,"colspan":1}]}').valid, false);
assert.equal(validateAnswer(structureQuestion, '{"row_count":2,"col_count":2,"cells":[{"text":"x","row":0,"col":0,"rowspan":2,"colspan":1},{"text":"y","row":1,"col":0,"rowspan":1,"colspan":1}]}').valid, false);

console.log("self-test: ok");
