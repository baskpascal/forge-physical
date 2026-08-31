export type BuildStatus = "queued" | "planning" | "building" | "testing" | "repairing" | "completed" | "needs_review" | "failed" | "unsupported_scope";
export type BuildStage = "idea" | "components" | "electronics" | "firmware" | "simulation" | "enclosure" | "verification" | "complete";

export type Event = {
  id: string;
  type: string;
  stage: BuildStage;
  status: string;
  message: string;
  metadata: Record<string, unknown>;
  created_at: string;
};

export type ComponentInstance = { ref: string; component_id: string; label: string };
export type Connection = { from: { ref: string; pin: string }; to: { ref: string; pin: string }; interface: string; reason: string };
export type Hardware = {
  board: ComponentInstance;
  components: ComponentInstance[];
  connections: Connection[];
  power: Connection[];
  constraints: string[];
};

export type ValidationIssue = { code: string; message: string; path: string; severity: "error" | "warning" };
export type ValidationResult = { passed: boolean; checks: Record<string, boolean>; issues: ValidationIssue[] };

export type ToolResult = { status: string; summary: string; evidence: Record<string, unknown> };
export type Verification = {
  electrical_compatibility: string;
  firmware_compilation: string;
  simulation: string;
  enclosure_generation: string;
  physical_assembly: string;
  emi_emc: string;
  thermals: string;
  scenario_checks?: string[];
};

export type Build = {
  id: string;
  prompt: string;
  status: BuildStatus;
  stage: BuildStage;
  progress: number;
  version: number;
  parent_build_id?: string;
  product_spec?: { name: string; description: string; features: string[]; power: string; constraints: string[]; supported: boolean; unsupported_reason?: string };
  hardware?: Hardware;
  electrical_validation?: ValidationResult;
  firmware?: ToolResult;
  simulation?: ToolResult;
  enclosure?: ToolResult;
  verification?: Verification;
  artifact_paths: Record<string, string>;
  agent_mode: string;
  error?: string;
  created_at?: string;
  updated_at?: string;
  events: Event[];
};
