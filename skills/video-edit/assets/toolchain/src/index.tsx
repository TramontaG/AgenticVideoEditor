import React from "react";
import { Composition, registerRoot } from "remotion";
import { Timeline } from "./components/Timeline";
import type { Manifest } from "./types";
const manifest: Manifest = {
  version: 1,
  width: 1920,
  height: 1080,
  fps: 30,
  durationInFrames: 150,
  background: "#111827",
  clips: [],
};
const metadata = ({ props }: { props: { manifest: Manifest } }) => ({
  width: props.manifest.width,
  height: props.manifest.height,
  fps: props.manifest.fps,
  durationInFrames: props.manifest.durationInFrames,
});
const Root = () => (
  <Composition
    id="Timeline"
    component={Timeline}
    width={1920}
    height={1080}
    fps={30}
    durationInFrames={150}
    defaultProps={{ manifest }}
    calculateMetadata={metadata}
  />
);
registerRoot(Root);
