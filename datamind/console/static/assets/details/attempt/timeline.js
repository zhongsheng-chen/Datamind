"use strict";

/**
 * @typedef {Object} BatchShardRecord
 * @property {string} [shard_id] 分片 ID
 * @property {string} [task_id] 子任务 ID
 * @property {number} [start_index] 数据起始位置
 * @property {number} [end_index] 数据结束位置
 * @property {string} [status] 执行状态
 * @property {number} [total_count] 总记录数
 * @property {number} [completed_count] 已完成记录数
 * @property {number} [succeeded_count] 成功记录数
 * @property {number} [failed_count] 失败记录数
 * @property {string} [worker_id] 执行节点
 * @property {string | null} [started_at] 开始时间
 * @property {string | null} [finished_at] 完成时间
 */

/**
 * @typedef {Object} ShardTimelineEntry
 * @property {BatchShardRecord} shard 分片记录
 * @property {number} start 开始时间戳
 * @property {number} end 完成时间戳
 */

/**
 * @param {Object} record 执行实例记录
 * @returns {BatchShardRecord[]}
 */
export function getAttemptShards(record) {
  const shards = record?.["shards"];
  return Array.isArray(shards) ? shards : [];
}

/**
 * @param {{attempt_id?: string}} record 执行实例记录
 * @param {string} executionDuration 执行耗时
 * @returns {Array<[unknown, string?]>}
 */
export function buildAttemptSummaryBadges(record, executionDuration) {
  return [
    [record.attempt_id, "blue"],
    ...(executionDuration === "—" ? [] : [[`耗时 ${executionDuration}`]]),
  ];
}

/**
 * @param {{attempt_number?: number}} record 执行实例记录
 * @param {number} workerCount 节点数量
 * @returns {{title: string, subtitle: string}}
 */
export function buildAttemptSummaryCopy(record, workerCount) {
  const attemptNumber = record.attempt_number ?? "—";
  return {
    title: "执行实例",
    subtitle: workerCount > 0
      ? `第 ${attemptNumber} 次 · ${workerCount} 个节点参与`
      : `第 ${attemptNumber} 次 · 等待节点分配`,
  };
}

/**
 * @param {BatchShardRecord[]} shards 分片记录
 * @param {number} [currentTime] 当前时间戳
 * @returns {{entries: ShardTimelineEntry[], start: number, end: number, peak: number}}
 */
export function buildShardTimelineData(shards, currentTime = Date.now()) {
  const entries = shards.flatMap((shard) => {
    const start = Date.parse(shard.started_at || "");
    if (!Number.isFinite(start)) return [];
    const parsedEnd = Date.parse(shard.finished_at || "");
    const end = Number.isFinite(parsedEnd) ? parsedEnd : Math.max(start, currentTime);
    return [{ shard, start, end: Math.max(start + 1, end) }];
  });
  if (!entries.length) return { entries, start: 0, end: 0, peak: 0 };

  const start = Math.min(...entries.map((entry) => entry.start));
  const rawEnd = Math.max(...entries.map((entry) => entry.end));
  const end = rawEnd > start ? rawEnd : start + 1;
  const events = entries.flatMap((entry) => [
    [entry.start, 1],
    [entry.end, -1],
  ]).sort((left, right) => left[0] - right[0] || left[1] - right[1]);
  let active = 0;
  let peak = 0;
  for (const [, change] of events) {
    active += change;
    peak = Math.max(peak, active);
  }
  return { entries, start, end, peak };
}

/** @param {number} timestamp 时间戳 */
export function formatTimelineTick(timestamp) {
  const value = new Date(timestamp);
  const pad = (part, size = 2) => String(part).padStart(size, "0");
  const clock = [
    pad(value.getHours()),
    pad(value.getMinutes()),
    pad(value.getSeconds()),
  ].join(":");
  return `${clock}.${pad(value.getMilliseconds(), 3)}`;
}

/** @param {unknown} timestamp 日期时间值 */
export function formatTimelineDateTime(timestamp) {
  const value = new Date(typeof timestamp === "number"
    ? timestamp
    : String(timestamp || ""));
  if (!Number.isFinite(value.getTime())) return "—";
  const pad = (part, size = 2) => String(part).padStart(size, "0");
  const date = [
    value.getFullYear(),
    pad(value.getMonth() + 1),
    pad(value.getDate()),
  ].join("/");
  const time = [
    pad(value.getHours()),
    pad(value.getMinutes()),
    `${pad(value.getSeconds())}.${pad(value.getMilliseconds(), 3)}`,
  ].join(":");
  return `${date} ${time}`;
}

/**
 * @param {ShardTimelineEntry[]} entries 分片时间区间
 * @returns {{entries: Array<ShardTimelineEntry & {row: number}>, rowCount: number}}
 */
export function layoutTimelineRows(entries) {
  const rowEnds = [];
  const positioned = [...entries]
    .sort((left, right) => left.start - right.start || left.end - right.end)
    .map((entry) => {
      let row = rowEnds.findIndex((end) => end <= entry.start);
      if (row < 0) {
        row = rowEnds.length;
        rowEnds.push(entry.end);
      } else {
        rowEnds[row] = entry.end;
      }
      return { ...entry, row };
    });
  return { entries: positioned, rowCount: Math.max(1, rowEnds.length) };
}
