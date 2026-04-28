import { useState, useEffect, useRef, useCallback } from "react";
import { generateAPI } from "./api";

/**
 * Episode 级别任务轮询 Hook。
 * Mount 时自动查后端是否有进行中任务（根据 episode_id + taskType），有则接续轮询。
 * 调用 startTask(recordId) 可立即开始新任务的轮询。
 */
export function useTaskPoller({
  episodeId,
  taskType,
  onSuccess,
  onError,
  intervalMs = 2000,
}: {
  episodeId: string;
  taskType: string;
  onSuccess: () => void;
  onError: (msg: string) => void;
  intervalMs?: number;
}) {
  const [recordId, setRecordId] = useState<string | null>(null);
  const [isRunning, setIsRunning] = useState(false);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  // 用 ref 存回调，避免 useEffect deps 频繁变化
  const onSuccessRef = useRef(onSuccess);
  const onErrorRef = useRef(onError);
  onSuccessRef.current = onSuccess;
  onErrorRef.current = onError;

  // Mount 时：查后端是否有进行中任务，有则恢复轮询
  useEffect(() => {
    let cancelled = false;
    generateAPI.listTasks({ episode_id: episodeId, task_type: taskType, limit: 1 })
      .then((tasks) => {
        if (cancelled) return;
        const latest = tasks[0];
        if (latest && (latest.status === "running" || latest.status === "pending")) {
          setRecordId(latest.id);
          setIsRunning(true);
        }
      })
      .catch(() => {}); // 恢复失败静默处理，不影响正常使用
    return () => { cancelled = true; };
  }, [episodeId, taskType]);

  // 轮询逻辑：recordId + isRunning 变化时触发
  useEffect(() => {
    if (!recordId || !isRunning) return;
    let cancelled = false;

    const poll = async () => {
      if (cancelled) return;
      try {
        const task = await generateAPI.getTask(recordId);
        if (cancelled) return;
        if (task.status === "success") {
          setIsRunning(false);
          setRecordId(null);
          onSuccessRef.current();
        } else if (task.status === "failed" || task.status === "cancelled") {
          setIsRunning(false);
          setRecordId(null);
          onErrorRef.current(task.error ?? "任务失败");
        } else {
          timerRef.current = setTimeout(poll, intervalMs);
        }
      } catch {
        if (!cancelled) {
          setIsRunning(false);
          setRecordId(null);
          onErrorRef.current("轮询失败，请刷新页面重试");
        }
      }
    };

    timerRef.current = setTimeout(poll, intervalMs);
    return () => {
      cancelled = true;
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, [recordId, isRunning, intervalMs]);

  const startTask = useCallback((id: string) => {
    setRecordId(id);
    setIsRunning(true);
  }, []);

  return { isRunning, startTask, recordId };
}

/**
 * Shot 级别批量任务轮询 Hook。
 * 用于 Step 2（图片）/ Step 3（视频）。
 * Mount 时查 episode 下所有 running 的 shot 级任务，恢复各 shot 的 loading 状态。
 * 每个 shot 任务完成后调用 onShotDone(shotId)。
 */
export function useShotTasksPoller({
  episodeId,
  taskType,
  onShotDone,
  intervalMs = 2000,
}: {
  episodeId: string;
  taskType: string;
  onShotDone: (shotId: string) => void;
  intervalMs?: number;
}) {
  // Set of shotIds (= target_id) currently being polled
  const [loadingShotIds, setLoadingShotIds] = useState<Set<string>>(new Set());
  const activePollers = useRef<Map<string, boolean>>(new Map()); // shotId → cancelled
  const onShotDoneRef = useRef(onShotDone);
  onShotDoneRef.current = onShotDone;

  // 为单个 shot 启动轮询
  const pollShot = useCallback((recordId: string, shotId: string) => {
    if (activePollers.current.has(shotId)) return; // 已在轮询
    activePollers.current.set(shotId, false);

    const poll = async () => {
      if (activePollers.current.get(shotId)) return; // cancelled
      try {
        const task = await generateAPI.getTask(recordId);
        if (activePollers.current.get(shotId)) return;
        if (task.status === "success" || task.status === "failed" || task.status === "cancelled") {
          activePollers.current.delete(shotId);
          setLoadingShotIds((prev) => {
            const next = new Set(prev);
            next.delete(shotId);
            return next;
          });
          if (task.status === "success") {
            onShotDoneRef.current(shotId);
          }
        } else {
          setTimeout(poll, intervalMs);
        }
      } catch {
        activePollers.current.delete(shotId);
        setLoadingShotIds((prev) => {
          const next = new Set(prev);
          next.delete(shotId);
          return next;
        });
      }
    };

    setTimeout(poll, intervalMs);
  }, [intervalMs]);

  // Mount 时：查所有 running 的 shot 任务并恢复
  useEffect(() => {
    let cancelled = false;
    generateAPI.listTasks({ episode_id: episodeId, task_type: taskType, limit: 50 })
      .then((tasks) => {
        if (cancelled) return;
        const running = tasks.filter(
          (t) => (t.status === "running" || t.status === "pending") && t.target_id
        );
        if (running.length === 0) return;

        const ids = new Set(running.map((t) => t.target_id!));
        setLoadingShotIds(ids);
        running.forEach((t) => pollShot(t.id, t.target_id!));
      })
      .catch(() => {});
    return () => {
      cancelled = true;
      // 标记所有活跃 poller 为 cancelled
      for (const shotId of activePollers.current.keys()) {
        activePollers.current.set(shotId, true);
      }
    };
  }, [episodeId, taskType, pollShot]);

  // 手动添加一个新的 shot 轮询（触发新任务时调用）
  const trackShot = useCallback((recordId: string, shotId: string) => {
    setLoadingShotIds((prev) => {
      const next = new Set(prev);
      next.add(shotId);
      return next;
    });
    pollShot(recordId, shotId);
  }, [pollShot]);

  return { loadingShotIds, trackShot };
}
