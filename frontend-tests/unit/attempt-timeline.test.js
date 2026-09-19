import { describe, expect, it } from "vitest";

import {
  buildShardTimelineData,
  formatTimelineDateTime,
  layoutTimelineRows,
} from "../../datamind/console/static/assets/details/attempt/timeline.js";

describe("attempt timeline", () => {
  it("computes the true peak concurrency", () => {
    const result = buildShardTimelineData([
      { shard_id: "a", started_at: "2026-09-19T00:00:00.000Z", finished_at: "2026-09-19T00:00:02.000Z" },
      { shard_id: "b", started_at: "2026-09-19T00:00:01.000Z", finished_at: "2026-09-19T00:00:03.000Z" },
      { shard_id: "c", started_at: "2026-09-19T00:00:02.000Z", finished_at: "2026-09-19T00:00:04.000Z" },
    ]);
    expect(result.entries).toHaveLength(3);
    expect(result.peak).toBe(2);
  });

  it("places overlapping shards on different rows and reuses free rows", () => {
    const result = layoutTimelineRows([
      { shard: { shard_id: "a" }, start: 0, end: 10 },
      { shard: { shard_id: "b" }, start: 5, end: 8 },
      { shard: { shard_id: "c" }, start: 10, end: 12 },
    ]);
    expect(result.rowCount).toBe(2);
    expect(result.entries.map((entry) => entry.row)).toEqual([0, 1, 0]);
  });

  it("formats full timestamps with milliseconds and rejects invalid values", () => {
    expect(formatTimelineDateTime("invalid")).toBe("—");
    expect(formatTimelineDateTime("2026-09-19T12:31:38.562Z")).toMatch(
      /^2026\/09\/19 \d{2}:31:38\.562$/,
    );
  });
});
