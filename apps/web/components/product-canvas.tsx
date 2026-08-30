"use client";

import dynamic from "next/dynamic";
import { artifactUrl } from "@/lib/artifact-url";
import type { Build } from "@/types/build";

const EnclosureView = dynamic(() => import("./enclosure-view").then((module) => module.EnclosureView), { ssr: false });

const stageRank = { idea: 0, components: 1, electronics: 2, firmware: 3, simulation: 4, enclosure: 5, verification: 6, complete: 7 };

export function ProductCanvas({ build }: { build: Build }) {
  const rank = stageRank[build.stage] ?? 0;
  if (rank >= 5 && build.enclosure) {
    const baseUrl = artifactUrl(build.id, build.artifact_paths.enclosure_base);
    const lidUrl = artifactUrl(build.id, build.artifact_paths.enclosure_lid);
    return <div className="product-canvas three-canvas"><EnclosureView baseUrl={baseUrl} lidUrl={lidUrl} /><div className="canvas-caption"><span>PARAMETRIC ENCLOSURE</span><b>BASE + LID STL</b></div></div>;
  }
  return (
    <div className={`product-canvas blueprint rank-${rank}`}>
      <svg viewBox="0 0 920 520" role="img" aria-label="Live functional architecture of the product">
        <defs>
          <filter id="softGlow"><feGaussianBlur stdDeviation="4" result="blur" /><feMerge><feMergeNode in="blur" /><feMergeNode in="SourceGraphic" /></feMerge></filter>
          <pattern id="grid" width="32" height="32" patternUnits="userSpaceOnUse"><path d="M32 0H0V32" fill="none" stroke="currentColor" strokeOpacity=".055" /></pattern>
        </defs>
        <rect width="920" height="520" fill="url(#grid)" />
        <path className="device-outline" d="M186 102 Q186 72 216 72 H704 Q734 72 734 102 V418 Q734 448 704 448 H216 Q186 448 186 418Z" />
        <g className="board-node">
          <rect x="356" y="188" width="210" height="142" rx="16" />
          <path d="M382 212h158v94H382z" /><circle cx="399" cy="227" r="6" /><circle cx="524" cy="227" r="6" />
          <text x="461" y="270" textAnchor="middle">ESP32-S3</text><text x="461" y="290" textAnchor="middle">DEVKITC-1</text>
        </g>
        <g className="component oled"><rect x="224" y="130" width="106" height="72" rx="9" /><rect x="236" y="143" width="82" height="46" rx="3" /><text x="277" y="169" textAnchor="middle">23.5°</text><text x="277" y="220" textAnchor="middle">SSD1306</text></g>
        <g className="component sensor"><rect x="606" y="130" width="78" height="92" rx="9" /><path d="M619 145h52M619 154h52M619 163h52" /><text x="645" y="242" textAnchor="middle">DHT22</text></g>
        <g className="component encoder"><circle cx="640" cy="346" r="43" /><circle cx="640" cy="346" r="27" /><path d="M640 318v16" /><text x="640" y="410" textAnchor="middle">KY-040</text></g>
        <g className="connections" filter="url(#softGlow)"><path d="M330 160C360 160 340 225 356 225" /><path d="M330 178C360 178 340 244 356 244" /><path d="M566 227C590 227 582 174 606 174" /><path d="M566 276C596 276 584 332 597 332" /><path d="M566 292C600 292 584 347 597 347" /><path d="M566 308C600 308 584 362 597 362" /></g>
      </svg>
      <div className="canvas-caption"><span>{rank < 2 ? "FUNCTIONAL ARCHITECTURE" : rank < 4 ? "LIVE ELECTRONICS" : "FIRMWARE REPRESENTATION"}</span><b>{build.hardware?.components.length ?? 0} modules · {build.hardware?.connections.length ?? 0} signal paths</b></div>
    </div>
  );
}
