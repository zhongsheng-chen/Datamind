import { describe, expect, it } from "vitest";

import {
  buildHashQuery,
  buildPageQuery,
  normalizeSortParameters,
  parsePageSize,
  parseSortRules,
} from "../../datamind/console/static/assets/resources/query.js";

describe("resource query", () => {
  it("builds API and hash queries from user filters", () => {
    expect(buildPageQuery(2, 20, "model a", "name", "desc")).toBe(
      "page=2&page_size=20&q=model+a&sort=name&order=desc",
    );
    expect(buildHashQuery(1, 10, "", "", "asc", 10)).toBe("");
    expect(buildHashQuery(2, 20, "x", "name", "asc", 10)).toBe(
      "?page=2&page_size=20&q=x&sort=name&order=asc",
    );
  });

  it("deduplicates, limits and aligns multi-field sorting", () => {
    expect(normalizeSortParameters("name,name,status,created_at", "desc", 3)).toEqual([
      "name,status,created_at",
      "desc,asc,asc",
    ]);
    expect(parseSortRules("name,status", "desc,asc")).toEqual([
      { field: "name", order: "desc" },
      { field: "status", order: "asc" },
    ]);
  });

  it("accepts only configured page sizes", () => {
    expect(parsePageSize("20", [10, 20, 50], 10)).toBe(20);
    expect(parsePageSize("999", [10, 20, 50], 10)).toBe(10);
  });
});
