import { describe, expect, it } from "vitest";

import {
  artifactExtensionsByFramework,
  datetimeLocalValue,
  filterModelTypes,
  normalizeChoice,
  optionalValue,
  roleOptions,
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


describe("角色选择说明", () => {
  it("内置角色保留原名称、说明和提交标识", () => {
    const names = ["administrator", "editor", "viewer", "invoker", "auditor"];
    const roles = names.map((name) => ({ name, is_builtin: true, description: "权限范围说明" }));
    expect(roleOptions(roles)).toEqual(names.map((name) => ({
      value: name, label: name, description: "权限范围说明",
    })));
  });

  it("自定义角色及历史同名角色保留名称和说明", () => {
    expect(roleOptions([
      { name: "自定义角色", is_builtin: false, description: "自定义权限" },
      { name: "editor", is_builtin: false, description: "历史角色说明" },
    ])).toEqual([
      { value: "自定义角色", label: "自定义角色", description: "自定义权限" },
      { value: "editor", label: "editor", description: "历史角色说明" },
    ]);
  });
});
