"use client";

import gsap from "gsap";
import { useEffect, useRef, useState } from "react";

const vertex = `attribute vec2 aPosition;
void main() { gl_Position = vec4(aPosition, 0., 1.); }`;

// One material surface: both photographs seed density in this same field. There
// is no bridge canvas, line, or additional particle emitter.
const fragment = `precision highp float;
uniform sampler2D uLeft, uRight;
uniform vec2 uResolution, uPointer, uPointerVelocity;
uniform float uTime, uHover, uMobile, uDpr;

float maskInk(sampler2D source, vec2 p, vec2 centre, vec2 scale) {
  vec2 uv = (p - centre) / scale + .5;
  if (any(lessThan(uv, vec2(0.))) || any(greaterThan(uv, vec2(1.)))) return 0.;
  vec4 sample = texture2D(source, uv);
  float ink = (1. - dot(sample.rgb, vec3(.299, .587, .114))) * sample.a;
  return smoothstep(.022, .30, ink);
}

// Low-frequency curl-like field: motion is continuous rather than JS x/y loops.
vec2 field(vec2 p, float phase) {
  float a = sin(p.y * 8.1 + phase * .091) + sin(p.x * 4.2 - phase * .053);
  float b = cos(p.x * 9.4 - phase * .071) - cos(p.y * 5.7 + phase * .047);
  return vec2(b, -a) * .5;
}

float gaussian(vec2 p, vec2 centre, vec2 radius) {
  vec2 q = (p - centre) / radius;
  return exp(-dot(q, q) * 2.65);
}

// Copy is a soft obstacle in the material, not a rectangular clipping zone.
float copyExclusion(vec2 p) {
  float headline = gaussian(p, vec2(.5, .43), vec2(.29, .19));
  float actions = gaussian(p, vec2(.5, .64), vec2(.19, .14));
  return max(headline, actions);
}

void main() {
  float cell = mix(8.7, 11.2, step(900., uResolution.x));
  vec2 grid = floor(gl_FragCoord.xy / cell) * cell + cell * .5;
  vec2 p = grid / uResolution;
  float time = uTime;

  // Independent macro movement, while the shared field supplies non-rigid life.
  vec2 leftCentre = vec2(.18, .53) + vec2(sin(time * .061) * .017, cos(time * .047) * .011);
  vec2 rightCentre = vec2(.82, .49) + vec2(sin(time * .049 + 1.7) * .019, cos(time * .063 + .8) * .012);
  vec2 drift = field(p, time) * .008;

  // An irregular, slow attraction interval. The field has no hard visual state.
  float pulse = .5 + .5 * sin(time * .125 + sin(time * .037));
  float connection = smoothstep(.54, .83, pulse) * .72;
  float topCurrent = gaussian(p, vec2(.5, .17), vec2(.48, .105));
  float bottomCurrent = gaussian(p, vec2(.5, .84), vec2(.46, .12));
  float currents = clamp(topCurrent + bottomCurrent, 0., 1.);

  // Only source-drone material is sampled into the shared space; no third asset.
  float leftPull = connection * currents * smoothstep(.18, .84, p.x) * .22;
  float rightPull = connection * currents * (1. - smoothstep(.16, .82, p.x)) * .22;
  vec2 curve = vec2(0., sin(p.x * 12. + time * .15) * .030 + sin(p.x * 5. - time * .09) * .014);
  vec2 leftSample = p - drift - vec2(leftPull, 0.) - curve * connection;
  vec2 rightSample = p - drift + vec2(rightPull, 0.) + curve * connection;

  float leftHome = maskInk(uLeft, p - drift, leftCentre, vec2(.60, .82));
  float rightHome = maskInk(uRight, p - drift, rightCentre, vec2(.60, .80)) * (1. - uMobile);
  float leftStream = maskInk(uLeft, leftSample, leftCentre, vec2(.60, .82)) * connection * currents;
  float rightStream = maskInk(uRight, rightSample, rightCentre, vec2(.60, .80)) * connection * currents * (1. - uMobile);
  float density = max(max(leftHome, rightHome), max(leftStream, rightStream));

  float exclusion = copyExclusion(p);
  density *= 1. - exclusion * .985;

  // Pointer force modifies the same flow model and fades through GSAP inertia.
  // The pointer uses physical canvas pixels throughout. 18px / 72px in CSS
  // pixels become the same perceived local footprint at every DPR.
  vec2 delta = grid - uPointer;
  float distanceToPointer = length(delta);
  float innerRadius = 18. * uDpr;
  float outerRadius = 72. * uDpr;
  float pointerField = pow(1. - smoothstep(innerRadius, outerRadius, distanceToPointer), 2.) * uHover;
  float speed = clamp(length(uPointerVelocity) / (900. * uDpr), 0., 1.);
  float repulsion = mix(3.6, 6.8, speed) * uDpr;
  vec2 radial = normalize(delta + vec2(.001)) * pointerField * repulsion;
  // A restrained tangential component stops the response reading as a bubble.
  vec2 tangent = normalize(field(p + vec2(.013, -.017), time + .7)) * pointerField * 1.15 * uDpr;
  vec2 copyDirection = normalize(p - vec2(.5, .50) + vec2(.001));
  vec2 copyPush = copyDirection * exclusion * (4. + connection * 2.);
  vec2 dotCentre = grid + field(p, time) * 4.8 + radial + tangent + copyPush;

  float breathing = (sin(grid.x * .035 + grid.y * .022 + time * .27) + sin(grid.y * .019 - time * .16)) * .032;
  float radius = clamp((density + breathing) * cell * .51 * (1. + pointerField * .065), 0., cell * .485);
  float dot = 1. - smoothstep(-1.05, 1.05, length(gl_FragCoord.xy - dotCentre) - radius);
  if (dot < .02 || density < .017) discard;
  gl_FragColor = vec4(vec3(.035), 1.);
}`;

function compile(gl: WebGLRenderingContext, type: number, source: string) {
  const shader = gl.createShader(type)!;
  gl.shaderSource(shader, source);
  gl.compileShader(shader);
  if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) throw new Error(gl.getShaderInfoLog(shader) ?? "Shader error");
  return shader;
}

export default function SharedHalftoneField() {
  const canvas = useRef<HTMLCanvasElement>(null);
  const debug = useRef<HTMLOutputElement>(null);
  const [ready, setReady] = useState(false);
  const debugEnabled = process.env.NODE_ENV === "development" && typeof window !== "undefined" && new URLSearchParams(window.location.search).has("pointerDebug");

  useEffect(() => {
    const element = canvas.current;
    if (!element) return;
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const gl = element.getContext("webgl", { alpha: false, antialias: false, powerPreference: "high-performance" });
    if (!gl) return;
    try {
      const program = gl.createProgram()!;
      gl.attachShader(program, compile(gl, gl.VERTEX_SHADER, vertex));
      gl.attachShader(program, compile(gl, gl.FRAGMENT_SHADER, fragment));
      gl.linkProgram(program);
      if (!gl.getProgramParameter(program, gl.LINK_STATUS)) throw new Error("Unable to link halftone material");
      const buffer = gl.createBuffer()!;
      gl.bindBuffer(gl.ARRAY_BUFFER, buffer);
      gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 1, -1, -1, 1, -1, 1, 1, -1, 1, 1]), gl.STATIC_DRAW);
      const loadTexture = (src: string) => {
        const texture = gl.createTexture()!;
        const image = new Image();
        image.src = src;
        image.onload = () => {
          gl.bindTexture(gl.TEXTURE_2D, texture);
          gl.pixelStorei(gl.UNPACK_FLIP_Y_WEBGL, 1);
          gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR);
          gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
          gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
          gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
          gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, gl.RGBA, gl.UNSIGNED_BYTE, image);
        };
        return texture;
      };
      const left = loadTexture("/hero-drone-left.png");
      const right = loadTexture("/hero-drone-right.png");
      const pointer = { x: -9999, y: -9999, vx: 0, vy: 0, hover: 0 };
      let last = { x: 0, y: 0, time: performance.now() };
      let frame = 0;
      let shown = false;
      let active = !document.hidden;
      const resize = () => {
        const dpr = Math.min(devicePixelRatio, 1.5);
        const rect = element.getBoundingClientRect();
        element.width = Math.max(1, Math.floor(rect.width * dpr));
        element.height = Math.max(1, Math.floor(rect.height * dpr));
      };
      resize();
      const observer = new ResizeObserver(resize);
      observer.observe(element);
      const onPointerMove = (event: PointerEvent) => {
        const rect = element.getBoundingClientRect();
        const now = performance.now();
        const dpr = element.width / rect.width;
        const inside = event.clientX >= rect.left && event.clientX <= rect.right && event.clientY >= rect.top && event.clientY <= rect.bottom;
        if (!inside) { gsap.to(pointer, { hover: 0, duration: .62, ease: "power2.out" }); return; }
        const x = (event.clientX - rect.left) * dpr;
        const y = (rect.bottom - event.clientY) * dpr;
        pointer.vx = (x - last.x) / Math.max(1, now - last.time) * 1000;
        pointer.vy = (y - last.y) / Math.max(1, now - last.time) * 1000;
        last = { x, y, time: now };
        gsap.to(pointer, { x, y, hover: 1, duration: .2, ease: "power3.out", overwrite: true });
        if (debug.current) {
          const cssDpr = element.width / rect.width;
          const speed = Math.min(1, Math.hypot(pointer.vx, pointer.vy) / (900 * cssDpr));
          debug.current.value = `pointer  ${Math.round(x / cssDpr)}, ${Math.round(y / cssDpr)}\ninner / outer  18px / 72px\ndisplacement  ${(3.6 + (6.8 - 3.6) * speed).toFixed(1)}px\nvelocity  ${Math.round(Math.hypot(pointer.vx, pointer.vy) / cssDpr)}px/s`;
        }
      };
      const draw = (now: number) => {
        if (!active) return;
        gl.viewport(0, 0, element.width, element.height);
        gl.clearColor(.9686, .9647, .9490, 1);
        gl.clear(gl.COLOR_BUFFER_BIT);
        gl.useProgram(program);
        const position = gl.getAttribLocation(program, "aPosition");
        gl.enableVertexAttribArray(position);
        gl.vertexAttribPointer(position, 2, gl.FLOAT, false, 0, 0);
        gl.activeTexture(gl.TEXTURE0); gl.bindTexture(gl.TEXTURE_2D, left); gl.uniform1i(gl.getUniformLocation(program, "uLeft"), 0);
        gl.activeTexture(gl.TEXTURE1); gl.bindTexture(gl.TEXTURE_2D, right); gl.uniform1i(gl.getUniformLocation(program, "uRight"), 1);
        gl.uniform2f(gl.getUniformLocation(program, "uResolution"), element.width, element.height);
        gl.uniform2f(gl.getUniformLocation(program, "uPointer"), pointer.x, pointer.y);
        gl.uniform2f(gl.getUniformLocation(program, "uPointerVelocity"), pointer.vx, pointer.vy);
        gl.uniform1f(gl.getUniformLocation(program, "uTime"), now * .001);
        gl.uniform1f(gl.getUniformLocation(program, "uHover"), reduced || window.innerWidth <= 700 ? 0 : pointer.hover);
        gl.uniform1f(gl.getUniformLocation(program, "uMobile"), window.innerWidth <= 700 ? 1 : 0);
        gl.uniform1f(gl.getUniformLocation(program, "uDpr"), element.width / element.getBoundingClientRect().width);
        gl.drawArrays(gl.TRIANGLES, 0, 6);
        if (!shown) { shown = true; setReady(true); }
        if (!reduced) frame = requestAnimationFrame(draw);
      };
      const visibility = () => { active = !document.hidden; if (active) draw(performance.now()); };
      window.addEventListener("pointermove", onPointerMove, { passive: true });
      document.addEventListener("visibilitychange", visibility);
      draw(performance.now());
      return () => { cancelAnimationFrame(frame); observer.disconnect(); window.removeEventListener("pointermove", onPointerMove); document.removeEventListener("visibilitychange", visibility); gl.deleteProgram(program); };
    } catch { return; }
  }, []);

  return <div className="shared-field"><div className="shared-field-fallback"><img src="/hero-drone-left.png" alt="" /><img src="/hero-drone-right.png" alt="" /></div><canvas ref={canvas} className={ready ? "ready" : ""} aria-label="Living halftone drone field" />{debugEnabled && <output ref={debug} aria-live="polite" style={{ position: "fixed", left: 12, top: 12, zIndex: 20, padding: 8, background: "#f7f6f2", color: "#111", border: "1px solid #111", font: "12px/1.35 monospace", whiteSpace: "pre", pointerEvents: "none" }}>pointer debug</output>}</div>;
}
