import { makeScene2D, Rect, Txt } from "@motion-canvas/2d";
import { all, createRef, waitFor } from "@motion-canvas/core";
export default makeScene2D(function* (view) {
  const bar = createRef<Rect>();
  view.add(
    <Rect
      ref={bar}
      width={100}
      height={100}
      radius={24}
      fill={"#38bdf8"}
      opacity={0}
    />,
  );
  yield* all(bar().opacity(1, 0.3), bar().width(500, 0.7));
  view.add(<Txt text={"Motion Canvas"} fontSize={48} fill={"#0f172a"} />);
  yield* waitFor(1.3);
});
