import { renderToStaticMarkup } from "react-dom/server";
import { expect, it } from "vitest";
import { ProductCanvas } from "./product-canvas";
import type { Build } from "@/types/build";

it("renders only the components in Hardware IR and connection-derived accessories", () => {
  const build: Build = { id: "alarm", prompt: "alarm", status: "testing", stage: "simulation", progress: 70, version: 1, agent_mode: "test", artifact_paths: {}, events: [], hardware: {
    board: { ref: "board", component_id: "esp32-s3-devkit", label: "ESP32-S3 DevKitC-1" },
    components: [{ ref: "sensor", component_id: "dht22", label: "DHT22" }, { ref: "warning_led", component_id: "led", label: "Warning LED" }],
    connections: [{ from: { ref: "board", pin: "GPIO10" }, to: { ref: "warning_led", pin: "A" }, interface: "gpio", reason: "LED output through 220 ohm resistor" }], power: [], constraints: [],
  } };
  const html = renderToStaticMarkup(<ProductCanvas build={build} />);
  expect(html).toContain("ESP32-S3 DevKitC-1"); expect(html).toContain("DHT22"); expect(html).toContain("Warning LED");
  expect(html).toContain("current-limiting resistor"); expect(html).not.toContain("SSD1306"); expect(html).not.toContain("KY-040");
});
