import { AbsoluteFill } from "remotion";
import type { TimelineProps } from "../../types";
import { useTimelineBehavior } from "./behavior";
export function Timeline(props: TimelineProps) {
  const view = useTimelineBehavior(props);
  return <AbsoluteFill style={view.style}>{view.clips}</AbsoluteFill>;
}
