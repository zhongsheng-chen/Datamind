import { describe, expect, it } from "vitest";

import {
  artifactExtensionsByFramework,
  datetimeLocalValue,
  filterModelTypes,
  normalizeChoice,
  optionalValue,
  taskTypeOptionsByModelType,
} from "../../datamind/console/static/assets/management/forms.js";

describe("management form rules", () => {
  it("keeps model task types constrained by the selected model type", () => {
    expect(taskTypeOptionsByModelType.logistic_regression).toEqual([
      ["scoring", "评分"],
      ["classification", "分类"],
    ]);
    expect(taskTypeOptionsByModelType.xgboost).toEqual([
      ["classification", "分类"],
    ]);
  });

  it("filters framework model types using the backend catalog", () => {
    expect(filterModelTypes(
      ["logistic_regression", "decision_tree", "random_forest"],
      ["decision_tree", "xgboost"],
    )).toEqual(["decision_tree"]);
  });

  it("uses backend artifact capabilities for upload extensions", () => {
    const capabilities = artifactExtensionsByFramework({
      artifact_extensions: {
        sklearn: [".joblib"],
        catboost: [".cbm"],
      },
    });

    expect(capabilities.sklearn).toEqual([".joblib"]);
    expect(capabilities.catboost).toEqual([".cbm"]);
    expect(artifactExtensionsByFramework({})).toEqual({});
  });

  it("normalizes form values and choice declarations", () => {
    const data = new FormData();
    data.set("name", "  model-a  ");
    data.set("empty", "   ");
    expect(optionalValue(data, "name")).toBe("model-a");
    expect(optionalValue(data, "empty")).toBeNull();
    expect(normalizeChoice(["active", "启用"])).toEqual({
      value: "active",
      label: "启用",
      description: "",
      group: "",
    });
  });

  it("returns an empty datetime value for invalid input", () => {
    expect(datetimeLocalValue("")).toBe("");
    expect(datetimeLocalValue("not-a-date")).toBe("");
  });
});
