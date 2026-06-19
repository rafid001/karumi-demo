import { useCallback, useEffect, useState } from "react";
import { api, type DriftLog, type Graph, type Product } from "./api";
import DemoPlayer from "./components/DemoPlayer";
import DriftPanel from "./components/DriftPanel";
import GraphView from "./components/GraphView";
import HealingPanel from "./components/HealingPanel";
import RunAgentPanel from "./components/RunAgentPanel";

type Tab = "agent" | "graph" | "drift" | "healing" | "demo";

const TAB_LABELS: Record<Tab, string> = {
  agent: "Run Agent",
  graph: "Knowledge Graph",
  drift: "Drift Events",
  healing: "Healing History",
  demo: "Demo Playback",
};

export default function App() {
  const [tab, setTab] = useState<Tab>("agent");
  const [products, setProducts] = useState<Product[]>([]);
  const [productId, setProductId] = useState("");
  const [graph, setGraph] = useState<Graph | null>(null);
  const [driftLogs, setDriftLogs] = useState<DriftLog[]>([]);
  const [health, setHealth] = useState<{ status: string; llm: { provider: string; status: string } } | null>(null);
  const [error, setError] = useState<string | null>(null);

  const loadProducts = useCallback(async () => {
    const [productRes, healthRes] = await Promise.all([api.products(), api.health()]);
    setProducts(productRes.products);
    setHealth(healthRes);
    setProductId((current) => {
      if (current && productRes.products.some((p) => p.id === current)) {
        return current;
      }
      return productRes.products[0]?.id || "";
    });
  }, []);

  const loadProductData = useCallback(async (selectedProductId: string) => {
    if (!selectedProductId) {
      setGraph(null);
      setDriftLogs([]);
      return;
    }
    const [graphRes, driftRes] = await Promise.all([
      api.graph(selectedProductId),
      api.driftLogs(selectedProductId),
    ]);
    setGraph(graphRes);
    setDriftLogs(driftRes.logs);
  }, []);

  const refreshWorkspace = useCallback(
    async (selectedId?: string) => {
      try {
        setError(null);
        await loadProducts();
        const id = selectedId || productId;
        if (id) {
          await loadProductData(id);
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load dashboard data");
      }
    },
    [loadProducts, loadProductData, productId]
  );

  const refresh = useCallback(async () => {
    await refreshWorkspace();
  }, [refreshWorkspace]);

  useEffect(() => {
    loadProducts().catch((err) =>
      setError(err instanceof Error ? err.message : "Failed to load products")
    );
  }, [loadProducts]);

  useEffect(() => {
    if (!productId) return;
    loadProductData(productId).catch((err) =>
      setError(err instanceof Error ? err.message : "Failed to load product data")
    );
  }, [productId, loadProductData]);

  const selectProduct = useCallback((id: string) => {
    setProductId(id);
  }, []);

  const viewGraph = useCallback((id: string) => {
    setProductId(id);
    setTab("graph");
  }, []);

  const viewHealing = useCallback((id: string) => {
    setProductId(id);
    setTab("healing");
  }, []);

  const driftCount = driftLogs.filter((l) => !l.healed).length;
  const healedCount = driftLogs.filter((l) => l.healed).length;
  const selectedProduct = products.find((p) => p.id === productId);

  return (
    <div className="app">
      <header>
        <div className="brand">
          <div className="brand-mark">KA</div>
          <h1>Self-Healing Demo Agent</h1>
        </div>
        <div className="meta">
          {health && (
            <>
              <span className={`badge ${health.status === "ok" ? "ok" : "warn"}`}>
                API {health.status}
              </span>
              <span className="badge">
                {health.llm.provider} · {health.llm.status}
              </span>
            </>
          )}
        </div>
      </header>

      <div className="layout">
        <aside className="sidebar">
          <div className="sidebar-section">
            <p className="sidebar-section-title">Workspace</p>
            <label htmlFor="product-select">Product</label>
            <select
              id="product-select"
              value={productId}
              onChange={(e) => setProductId(e.target.value)}
            >
              {products.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
            </select>
            {selectedProduct && (
              <p className="sidebar-url">{selectedProduct.base_url}</p>
            )}
            {products.length === 0 && (
              <p className="empty">No products — run a crawl first.</p>
            )}
          </div>
          <button className="primary" type="button" onClick={refresh}>
            Refresh data
          </button>
        </aside>

        <main>
          <div className="tabs">
            {(["agent", "graph", "drift", "healing", "demo"] as Tab[]).map((t) => (
              <button
                key={t}
                type="button"
                className={`tab ${tab === t ? "active" : ""}`}
                onClick={() => setTab(t)}
              >
                {TAB_LABELS[t]}
              </button>
            ))}
          </div>

          <div className="content">
            {error && <div className="error panel">{error}</div>}

            {tab === "agent" && (
              <RunAgentPanel
                products={products}
                onProductsChange={refreshWorkspace}
                onSelectProduct={selectProduct}
                onViewGraph={viewGraph}
                onViewHealing={viewHealing}
              />
            )}

            {tab === "graph" && (
              <div className="panel">
                <div className="panel-header">
                  <h2>Knowledge Graph</h2>
                  <span className="panel-count">{graph?.nodes.length ?? 0} nodes</span>
                </div>
                <GraphView graph={graph} />
              </div>
            )}

            {tab === "drift" && (
              <div className="panel">
                <div className="panel-header">
                  <h2>Drift Events</h2>
                  <span className="panel-count">{driftCount} active</span>
                </div>
                <DriftPanel logs={driftLogs} />
              </div>
            )}

            {tab === "healing" && (
              <div className="panel">
                <div className="panel-header">
                  <h2>Healing History</h2>
                  <span className="panel-count">{healedCount} healed</span>
                </div>
                <HealingPanel logs={driftLogs} />
              </div>
            )}

            {tab === "demo" && <DemoPlayer productId={productId} products={products} />}
          </div>
        </main>
      </div>
    </div>
  );
}
