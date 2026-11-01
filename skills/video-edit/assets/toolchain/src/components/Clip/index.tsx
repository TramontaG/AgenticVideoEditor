import type { ClipData } from "../../types";
import { useClipBehavior } from "./behavior";
export function Clip(props: { clip: ClipData }) {
  const view = useClipBehavior(props);
  return <div style={view.style}>{view.content}</div>;
}
