"use client";

import React, { useState, useEffect } from "react";

type OrbState =
  | "idle"
  | "listening"
  | "planning"
  | "working"
  | "waiting"
  | "needs_approval"
  | "error"
  | "recovering"
  | "complete";

interface OrbProps {
  state?: OrbState;
  size?: number;
  progress?: number;
  mission?: string;
  agentCount?: number;
  toolActive?: boolean;
  onClick?: () => void;
  onContextMenu?: (e: React.MouseEvent) => void;
  showLabel?: boolean;
  interactive?: boolean;
}

function supportsWebGL(): boolean {
  if (typeof window === "undefined") return false;
  try {
    const canvas = document.createElement("canvas");
    const gl = canvas.getContext("webgl2") || canvas.getContext("webgl");
    return !!gl;
  } catch {
    return false;
  }
}

export default function JARVISOrbSmart(props: OrbProps) {
  const [useGL, setUseGL] = useState<boolean | null>(null);

  useEffect(() => {
    setUseGL(supportsWebGL());
  }, []);

  // Loading state — render nothing until we know which renderer to use
  if (useGL === null) {
    return <div style={{ width: props.size || 64, height: props.size || 64 }} />;
  }

  if (useGL) {
    // Dynamic import for WebGL version (code-split)
    const JARVISOrbGL = require("./JARVISOrbGL").default;
    return <JARVISOrbGL {...props} />;
  }

  // Fallback to 2D canvas version
  const JARVISOrb2D = require("./JARVISOrb").default;
  return <JARVISOrb2D {...props} />;
}
