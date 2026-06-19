import { useCallback, useEffect, useRef, useState } from "react";
import {
  api,
  crawlStream,
  type CrawlStreamEvent,
  type Product,
  type RecheckResult,
} from "../api";
import DriftPanel, { recheckEventsToLogs } from "./DriftPanel";

interface Props {
  products: Product[];
  onProductsChange: (productId?: string) => Promise<void>;
  onSelectProduct: (productId: string) => void;
  onViewGraph: (productId: string) => void;
  onViewHealing: (productId: string) => void;
}

interface CrawlLine {
  id: string;
  status: "done" | "crawling" | "failed";
  url: string;
  title?: string | null;
}

function shortPath(url: string) {
  try {
    const path = new URL(url).pathname;
    return path === "/" ? "/" : path;
  } catch {
    return url;
  }
}

function formatTimestamp(value?: string | null) {
  if (!value) return "Never";
  return new Date(value).toLocaleString();
}

function isValidUrl(value: string) {
  try {
    const parsed = new URL(value);
    return parsed.protocol === "http:" || parsed.protocol === "https:";
  } catch {
    return false;
  }
}

export default function RunAgentPanel({
  products,
  onProductsChange,
  onSelectProduct,
  onViewGraph,
  onViewHealing,
}: Props) {
  const [url, setUrl] = useState("http://localhost:5174");
  const [productName, setProductName] = useState("Pulse");
  const [maxPages, setMaxPages] = useState(20);
  const [crawlLines, setCrawlLines] = useState<CrawlLine[]>([]);
  const [crawlActive, setCrawlActive] = useState(false);
  const [crawlError, setCrawlError] = useState<string | null>(null);
  const [crawlSummary, setCrawlSummary] = useState<CrawlStreamEvent | null>(null);
  const [recheckingId, setRecheckingId] = useState<string | null>(null);
  const [recheckError, setRecheckError] = useState<string | null>(null);
  const [recheckResult, setRecheckResult] = useState<RecheckResult | null>(null);
  const stopCrawlRef = useRef<(() => void) | null>(null);

  useEffect(() => {
    return () => stopCrawlRef.current?.();
  }, []);

  const upsertCrawlLine = useCallback((line: CrawlLine) => {
    setCrawlLines((current) => {
      const index = current.findIndex((item) => item.url === line.url);
      if (index === -1) return [...current, line];
      const next = [...current];
      next[index] = line;
      return next;
    });
  }, []);

  const startCrawl = () => {
    const trimmedUrl = url.trim();
    if (!isValidUrl(trimmedUrl)) {
      setCrawlError("Enter a valid URL starting with http:// or https://");
      return;
    }
    if (!productName.trim()) {
      setCrawlError("Product name is required");
      return;
    }

    stopCrawlRef.current?.();
    setCrawlError(null);
    setCrawlSummary(null);
    setCrawlLines([]);
    setCrawlActive(true);

    stopCrawlRef.current = crawlStream(
      {
        url: trimmedUrl,
        productName: productName.trim(),
        maxPages: maxPages || 20,
      },
      {
        onEvent: (event) => {
          if (event.event === "page_crawling" && event.url) {
            upsertCrawlLine({
              id: event.url,
              status: "crawling",
              url: event.url,
            });
          }
          if (event.event === "page_crawled" && event.url) {
            upsertCrawlLine({
              id: event.url,
              status: "done",
              url: event.url,
              title: event.title,
            });
          }
          if (event.event === "page_failed" && event.url) {
            upsertCrawlLine({
              id: event.url,
              status: "failed",
              url: event.url,
            });
          }
          if (event.event === "done") {
            setCrawlSummary(event);
            if (event.product_id) {
              onSelectProduct(event.product_id);
              onProductsChange(event.product_id).catch(() => undefined);
            } else {
              onProductsChange().catch(() => undefined);
            }
          }
        },
        onError: (message) => {
          setCrawlError(message);
          setCrawlActive(false);
        },
        onDone: () => {
          setCrawlActive(false);
          stopCrawlRef.current = null;
        },
      }
    );
  };

  const runRecheck = async (productId: string) => {
    setRecheckingId(productId);
    setRecheckError(null);
    setRecheckResult(null);
    onSelectProduct(productId);

    try {
      const result = await api.recheckProduct(productId);
      setRecheckResult(result);
      await onProductsChange(productId);
    } catch (err) {
      setRecheckError(err instanceof Error ? err.message : "Re-check failed");
    } finally {
      setRecheckingId(null);
    }
  };

  const meaningfulEvents =
    recheckResult?.events.filter((event) => event.is_meaningful) ?? [];
  const recheckLogs = recheckResult
    ? recheckEventsToLogs(meaningfulEvents, new Date().toISOString())
    : [];

  return (
    <div className="run-agent">
      <section className="panel agent-section">
        <div className="panel-header">
          <h2>New Crawl</h2>
        </div>
        <div className="agent-form">
          <label>
            Site URL
            <input
              type="url"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              placeholder="http://localhost:5174"
              disabled={crawlActive}
            />
          </label>
          <label>
            Product name
            <input
              type="text"
              value={productName}
              onChange={(e) => setProductName(e.target.value)}
              placeholder="Pulse"
              disabled={crawlActive}
            />
          </label>
          <label>
            Max pages
            <input
              type="number"
              min={1}
              max={200}
              value={maxPages}
              onChange={(e) => setMaxPages(Number(e.target.value) || 20)}
              disabled={crawlActive}
            />
          </label>
          <button
            className="primary"
            type="button"
            onClick={startCrawl}
            disabled={crawlActive}
          >
            {crawlActive ? "Crawling…" : "Start Crawl"}
          </button>
        </div>

        {crawlError && <div className="error inline-error">{crawlError}</div>}

        {(crawlActive || crawlLines.length > 0) && (
          <div className="crawl-log">
            <p className="crawl-log-title">{crawlActive ? "Crawling…" : "Crawl log"}</p>
            <ul>
              {crawlLines.map((line) => (
                <li key={line.id} className={`crawl-line crawl-line--${line.status}`}>
                  {line.status === "done" && <span className="crawl-icon">✓</span>}
                  {line.status === "crawling" && <span className="crawl-icon crawl-icon--spin">⏳</span>}
                  {line.status === "failed" && <span className="crawl-icon">✕</span>}
                  <span>
                    {line.status === "done" && "Found: "}
                    {line.status === "crawling" && "Crawling: "}
                    {line.status === "failed" && "Failed: "}
                    <strong>{shortPath(line.url)}</strong>
                    {line.title ? ` (${line.title})` : ""}
                  </span>
                </li>
              ))}
            </ul>
          </div>
        )}

        {crawlSummary?.product_id && (
          <div className="result-card">
            <h3>Crawl complete</h3>
            <p>
              {crawlSummary.nodes_discovered ?? 0} pages,{" "}
              {crawlSummary.edges_discovered ?? 0} edges discovered
            </p>
            <button
              className="primary"
              type="button"
              onClick={() => onViewGraph(crawlSummary.product_id!)}
            >
              View Knowledge Graph
            </button>
          </div>
        )}
      </section>

      <section className="panel agent-section">
        <div className="panel-header">
          <h2>Existing Products</h2>
          <span className="panel-count">{products.length} total</span>
        </div>

        {products.length === 0 ? (
          <p className="empty">No products yet — run a crawl above to get started.</p>
        ) : (
          <div className="product-cards">
            {products.map((product) => (
              <div key={product.id} className="product-card">
                <div>
                  <strong>{product.name}</strong>
                  <div className="meta-line">{product.base_url}</div>
                  <div className="meta-line">
                    Last crawled: {formatTimestamp(product.last_crawled_at)}
                  </div>
                  {product.last_checked_at && (
                    <div className="meta-line">
                      Last checked: {formatTimestamp(product.last_checked_at)}
                    </div>
                  )}
                </div>
                <button
                  className="primary"
                  type="button"
                  disabled={recheckingId === product.id}
                  onClick={() => runRecheck(product.id)}
                >
                  {recheckingId === product.id ? "Re-checking…" : "Re-check for Drift"}
                </button>
              </div>
            ))}
          </div>
        )}

        {recheckError && <div className="error inline-error">{recheckError}</div>}

        {recheckingId && (
          <div className="loading-banner">
            Re-crawling and comparing against known state…
          </div>
        )}

        {recheckResult && (
          <div className="result-card">
            <h3>Re-check complete</h3>
            <ul className="result-stats">
              <li>{recheckResult.nodes_checked} pages checked</li>
              <li>{recheckResult.nodes_meaningful} pages drifted (meaningful changes)</li>
              <li>{recheckResult.nodes_unchanged} pages unchanged</li>
            </ul>

            {meaningfulEvents.length > 0 ? (
              <>
                <h4>Drifted pages</h4>
                <DriftPanel
                  logs={recheckLogs}
                  onlyActive={false}
                  emptyMessage="No meaningful drift detected."
                />
              </>
            ) : (
              <p className="empty">No meaningful drift detected on this re-check.</p>
            )}

            {recheckResult.healing && recheckResult.healing.healed > 0 && (
              <div className="heal-banner">
                <span>✓ Self-healed {recheckResult.healing.healed} pages — knowledge graph updated</span>
                <button
                  type="button"
                  className="link-button"
                  onClick={() => onViewHealing(recheckResult.product_id!)}
                >
                  View Healing History
                </button>
              </div>
            )}
          </div>
        )}
      </section>
    </div>
  );
}
