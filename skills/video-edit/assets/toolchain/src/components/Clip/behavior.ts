import React from "react";
import {
  Audio,
  Img,
  OffthreadVideo,
  staticFile,
  useCurrentFrame,
} from "remotion";
import type { ClipData } from "../../types";

export function useClipBehavior({ clip }: { clip: ClipData }) {
  const frame = useCurrentFrame();
  const progress = Math.min(1, frame / Math.max(1, clip.durationInFrames - 1));
  const zoom =
    (clip.zoomStart ?? 1) +
    ((clip.zoomEnd ?? 1) - (clip.zoomStart ?? 1)) * progress;
  const fadeIn = clip.fadeInFrames ? Math.min(1, frame / clip.fadeInFrames) : 1;
  const fadeOut = clip.fadeOutFrames
    ? Math.min(1, (clip.durationInFrames - 1 - frame) / clip.fadeOutFrames)
    : 1;
  const fade = Math.max(0, Math.min(fadeIn, fadeOut));
  const mediaStyle: React.CSSProperties = {
    width: "100%",
    height: "100%",
    objectFit: clip.objectFit ?? "cover",
    objectPosition: clip.objectPosition ?? "50% 50%",
    transform: `scale(${zoom})`,
  };
  const style: React.CSSProperties = {
    position: "absolute",
    left: clip.x ?? 0,
    top: clip.y ?? 0,
    width: clip.width ?? "100%",
    height: clip.height ?? "100%",
    overflow: "hidden",
    opacity: (clip.opacity ?? 1) * fade,
    display: "flex",
    justifyContent: "center",
    alignItems: "center",
  };
  const volume = (f: number) => {
    const attack = clip.fadeInFrames ? Math.min(1, f / clip.fadeInFrames) : 1;
    const release = clip.fadeOutFrames
      ? Math.min(1, (clip.durationInFrames - 1 - f) / clip.fadeOutFrames)
      : 1;
    return (clip.volume ?? 1) * Math.max(0, Math.min(attack, release));
  };
  let content: React.ReactNode;
  const src = clip.src ? staticFile(clip.src) : "";
  switch (clip.type) {
    case "image":
      content = React.createElement(Img, { src, style: mediaStyle });
      break;
    case "video":
      content = React.createElement(OffthreadVideo, {
        src,
        startFrom: clip.trimStartFrames ?? 0,
        volume,
        style: mediaStyle,
      });
      break;
    case "audio":
      content = React.createElement(Audio, {
        src,
        startFrom: clip.trimStartFrames ?? 0,
        volume,
      });
      break;
    case "frames": {
      const index = Math.min(
        frame,
        (clip.frameCount ?? clip.durationInFrames) - 1,
      );
      const pattern = clip.framePattern ?? "%06d.png";
      const file = pattern.replace(/%0?(\d*)d/, (_, digits: string) =>
        String(index).padStart(Number(digits || 1), "0"),
      );
      content = React.createElement(Img, {
        src: staticFile(`${clip.src}/${file}`),
        style: mediaStyle,
      });
      break;
    }
    case "title":
      content = React.createElement(
        "div",
        {
          style: {
            color: clip.color ?? "#fff",
            fontSize: clip.fontSize ?? 64,
            fontFamily: clip.fontFamily ?? "sans-serif",
            textAlign: clip.textAlign ?? "center",
            padding: "5%",
            whiteSpace: "pre-wrap",
          },
        },
        clip.text,
      );
      break;
  }
  return { style, content };
}
