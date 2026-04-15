import { Composition } from "remotion";
import { BeforeAfterReel, beforeAfterSchema, defaultProps } from "./compositions/BeforeAfterReel";

// Reel is 9:16 vertical at 1080x1920, 30 fps.
// Total duration: 25 seconds = 750 frames.
const FPS = 30;
const DURATION_SECONDS = 25;
const DURATION_FRAMES = FPS * DURATION_SECONDS;

export const RemotionRoot: React.FC = () => {
  return (
    <>
      <Composition
        id="BeforeAfterReel"
        component={BeforeAfterReel}
        durationInFrames={DURATION_FRAMES}
        fps={FPS}
        width={1080}
        height={1920}
        schema={beforeAfterSchema}
        defaultProps={defaultProps}
      />
    </>
  );
};
