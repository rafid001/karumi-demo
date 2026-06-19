import { useState } from "react";
import { api, type DemoResult, type Product } from "../api";

interface Props {
  productId: string;
  products: Product[];
}

export default function DemoPlayer({ productId, products }: Props) {
  const [persona, setPersona] = useState(
    "Technical decision maker evaluating the product for their team"
  );
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [demo, setDemo] = useState<DemoResult | null>(null);
  const [activeStep, setActiveStep] = useState(0);

  const product = products.find((p) => p.id === productId);

  async function runDemo() {
    if (!productId) return;
    setLoading(true);
    setError(null);
    try {
      const result = await api.runDemo(productId, persona);
      setDemo(result);
      setActiveStep(0);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Demo failed");
    } finally {
      setLoading(false);
    }
  }

  const step = demo?.steps[activeStep];

  return (
    <div>
      <div className="demo-controls panel" style={{ marginBottom: "1rem" }}>
        <div className="panel-header">
          <h2>Generate Demo</h2>
        </div>
        <label>Prospect persona</label>
        <textarea rows={3} value={persona} onChange={(e) => setPersona(e.target.value)} />
        <button className="primary" disabled={!productId || loading} onClick={runDemo}>
          {loading ? "Running demo…" : `Run demo for ${product?.name || "product"}`}
        </button>
        {error && <div className="error">{error}</div>}
      </div>

      {!demo && <p className="empty">Run a demo to see narrated playback.</p>}

      {demo && (
        <div>
          <div className="demo-step-tabs">
            {demo.steps.map((s, i) => (
              <button
                key={s.step}
                type="button"
                className={`step-pill ${i === activeStep ? "active" : ""}`}
                onClick={() => setActiveStep(i)}
              >
                Step {s.step}
              </button>
            ))}
          </div>

          {step && (
            <div className="demo-step">
              <div>
                {step.screenshot_url ? (
                  <img src={step.screenshot_url} alt={`Step ${step.step}`} />
                ) : (
                  <div className="empty" style={{ padding: "2rem" }}>
                    No screenshot
                  </div>
                )}
              </div>
              <div>
                <h3>
                  Step {step.step}: {step.title || step.url}
                </h3>
                <p className="narration">"{step.narration}"</p>
                <p className="meta-line">
                  <strong>Action:</strong> {step.action}
                </p>
                <p className="meta-line">
                  <strong>Result:</strong> {step.action_result || "—"}
                </p>
                <p className="meta-line">
                  <strong>URL:</strong> {step.url}
                </p>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
