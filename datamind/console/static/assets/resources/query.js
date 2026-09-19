"use strict";

export function buildPageQuery(page, pageSize, query, sortBy = "", sortOrder = "asc") {
  const parameters = new URLSearchParams({
    page: String(page),
    page_size: String(pageSize),
  });
  if (query) parameters.set("q", query);
  if (sortBy) {
    parameters.set("sort", sortBy);
    parameters.set("order", sortOrder);
  }
  return parameters.toString();
}

export function buildHashQuery(
  page,
  pageSize,
  query,
  sortBy = "",
  sortOrder = "asc",
  defaultPageSize = 10,
) {
  const parameters = new URLSearchParams();
  if (page > 1) parameters.set("page", String(page));
  if (pageSize !== defaultPageSize) parameters.set("page_size", String(pageSize));
  if (query) parameters.set("q", query);
  if (sortBy) {
    parameters.set("sort", sortBy);
    parameters.set("order", sortOrder);
  }
  const value = parameters.toString();
  return value ? `?${value}` : "";
}

export function normalizeSortParameters(sortBy, sortOrder, maxSortFields = 3) {
  const fields = (sortBy || "")
    .split(",")
    .map((field) => field.trim())
    .filter((field, index, values) => field && values.indexOf(field) === index)
    .slice(0, maxSortFields);
  if (!fields.length) return ["", "asc"];

  const directions = (sortOrder || "")
    .split(",")
    .map((direction) => (direction.trim().toLowerCase() === "desc" ? "desc" : "asc"));
  return [
    fields.join(","),
    fields.map((_field, index) => directions[index] || "asc").join(","),
  ];
}

export function parseSortRules(sortBy, sortOrder, maxSortFields = 3) {
  const [normalizedSort, normalizedOrder] = normalizeSortParameters(
    sortBy,
    sortOrder,
    maxSortFields,
  );
  if (!normalizedSort) return [];
  const fields = normalizedSort.split(",");
  const directions = normalizedOrder.split(",");
  return fields.map((field, index) => ({
    field,
    order: directions[index],
  }));
}

export function parsePageSize(value, pageSizeOptions, defaultPageSize) {
  const pageSize = Number.parseInt(value || "", 10);
  return pageSizeOptions.includes(pageSize) ? pageSize : defaultPageSize;
}
