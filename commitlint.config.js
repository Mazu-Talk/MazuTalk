const allowedTypes = [
  "feat",
  "fix",
  "design",
  "style",
  "refactor",
  "comment",
  "docs",
  "test",
  "chore",
  "rename",
  "remove",
  "build",
  "ci",
  "perf",
  "hotfix",
];

module.exports = {
  extends: ["@commitlint/config-conventional"],
  rules: {
    // type 목록 제한
    "type-enum": [2, "always", allowedTypes],

    // type은 소문자 권장
    "type-case": [2, "always", "lower-case"],

    // subject는 비워두면 안 됨
    "subject-empty": [2, "never"],

    // 제목 50자 이내
    "header-max-length": [2, "always", 50],

    // 마침표 금지
    "subject-full-stop": [2, "never", "."],

    // scope 허용: feat(navigation): ...
    "scope-empty": [0],

    // 한글 subject를 허용하기 위해 subject-case 비활성화
    "subject-case": [0],
  },
};
