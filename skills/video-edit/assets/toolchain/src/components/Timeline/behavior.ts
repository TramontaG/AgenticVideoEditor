import React from "react";
import { Sequence } from "remotion";
import type { TimelineProps } from "../../types";
import { Clip } from "../Clip";
export function useTimelineBehavior({ manifest }: TimelineProps) {
  return {
    style: { backgroundColor: manifest.background },
    clips: manifest.clips.map((clip) =>
      React.createElement(
        Sequence,
        {
          key: clip.id,
          from: clip.from,
          durationInFrames: clip.durationInFrames,
        },
        React.createElement(Clip, { clip }),
      ),
    ),
  };
}
