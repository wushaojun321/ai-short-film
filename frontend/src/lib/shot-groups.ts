import type { Shot } from "@/lib/data";

export type ShotGroup = {
  key: string;
  label: string;
  segmentCode?: string;
  segmentName?: string;
  segmentFunction?: string;
  items: Array<{ shot: Shot; index: number }>;
};

export function shotNumberLabel(index: number) {
  return `镜头${index + 1}`;
}

export function buildShotGroups(shots: Shot[]): ShotGroup[] {
  const groups: ShotGroup[] = [];
  const groupMap = new Map<string, ShotGroup>();

  shots.forEach((shot, index) => {
    const segmentCode = shot.segmentCode?.trim();
    const segmentName = shot.segmentName?.trim();
    const key = segmentCode || segmentName || "ungrouped";
    let group = groupMap.get(key);
    if (!group) {
      group = {
        key,
        label: segmentName || segmentCode || "未分段片段",
        segmentCode,
        segmentName,
        segmentFunction: shot.segmentFunction,
        items: [],
      };
      groupMap.set(key, group);
      groups.push(group);
    }
    if (!group.segmentFunction && shot.segmentFunction) group.segmentFunction = shot.segmentFunction;
    group.items.push({ shot, index });
  });

  return groups;
}

export function segmentTitle(group: ShotGroup, groupIndex: number) {
  const name = group.segmentName || group.segmentCode || group.label;
  return `片段${groupIndex + 1}${name && name !== "未分段片段" ? ` · ${name}` : ""}`;
}
