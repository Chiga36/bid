// Ambient declaration for the plain-JS WebThreads.jsx (React Bits component, kept as vendored
// JS rather than converted to TSX — see its own file header). Lets strict TS import it without
// enabling project-wide allowJs, which would also pull other .jsx/.js files into type-checking.
import type { ComponentType } from "react";

export interface WebThreadsProps {
  color1?: string;
  color2?: string;
  color3?: string;
  speed?: number;
  threadCount?: number;
  frequency?: number;
  spread?: number;
  taper?: number;
  position?: number;
  fanMode?: "center" | "left" | "right";
  glow?: number;
  falloff?: number;
  thickness?: number;
  brightness?: number;
  opacity?: number;
  mirror?: boolean;
  shimmer?: boolean;
  grain?: boolean;
  grainIntensity?: number;
  mouseInteraction?: boolean;
  mouseStrength?: number;
  backgroundColor?: string;
  lightMode?: boolean;
  className?: string;
}

declare const WebThreads: ComponentType<WebThreadsProps>;
export default WebThreads;
