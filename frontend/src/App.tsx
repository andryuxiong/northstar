import { useEffect, useMemo, useRef, useState } from "react";
import type { LucideIcon } from "lucide-react";
import {
  Activity,
  Ad,
  AlertCircle,
  ArrowLeft,
  ArrowRight,
  Bookmark,
  Calculator,
  Check,
  CheckCircle2,
  ChevronRight,
  CircleHelp,
  ClipboardList,
  Database,
  Download,
  ExternalLink,
  Eye,
  Gauge,
  Globe2,
  GitCompareArrows,
  Image,
  KeyRound,
  LayoutDashboard,
  LoaderCircle,
  Menu,
  PackageSearch,
  Plus,
  Radar,
  RefreshCw,
  Search,
  Save,
  Settings,
  ShieldCheck,
  ShoppingBag,
  Store,
  TrafficCone,
  TrendingUp,
  WifiOff,
  X,
  Zap,
} from "lucide-react";
import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { apiFetch, getToken, localLogin } from "./api/client";

type View =
  | "overview"
  | "products"
  | "stores"
  | "ads"
  | "shortlist"
  | "compare"
  | "settings"
  | "ad-detail"
  | "store-report";
type ReportTab =
  | "overview"
  | "products"
  | "traffic"
  | "ads"
  | "offers"
  | "technology"
  | "evidence"
  | "diagnostics";
type ApiStatus = "checking" | "offline" | "connected";
type Toast = {
  title: string;
  body?: string;
  tone?: "success" | "error";
} | null;

interface TrafficData {
  provider?: string;
  status?: string;
  fetch_status?: string;
  period?: string;
  period_start?: string;
  period_end?: string;
  visits?: number | null;
  total_visits?: number | null;
  global_rank?: number | null;
  country_rank?: number | null;
  category_rank?: number | null;
  fetched_at?: string;
  error?: string | null;
  metric_status?: {
    total_visits?: TrafficMetricStatus;
    global_rank?: TrafficMetricStatus;
  };
  data_notice?: string;
}

interface TrafficMetricStatus {
  status?: string;
  available?: boolean;
  message?: string | null;
}

interface LocalStore {
  id: number;
  domain: string;
  platform: string;
  last_seen_at: string;
  product_count: number;
  observation_state?: "observed" | "submitted";
  traffic?: TrafficData | null;
  latest_traffic?: TrafficData | null;
}

interface LocalProduct {
  id: number;
  title: string;
  canonical_url: string;
  store_domain?: string;
  currency?: string;
  last_seen_at: string;
  first_seen_at?: string;
  price_min?: number;
  price_max?: number;
  available?: boolean;
  variant_count?: number;
  image_url?: string;
  momentum_score?: number;
  confidence?: number;
}

interface ProductEconomicsScenario {
  id: number;
  product_id: number;
  scenario_key: string;
  revision: number;
  supersedes_id?: number | null;
  is_active: boolean;
  name: string;
  version: string;
  input_source: "user_entered";
  currency: string;
  selling_price: string | number;
  product_cost_low: string | number;
  product_cost_high: string | number;
  shipping_cost_low: string | number;
  shipping_cost_high: string | number;
  fulfillment_cost_low: string | number;
  fulfillment_cost_high: string | number;
  other_variable_cost_low: string | number;
  other_variable_cost_high: string | number;
  payment_fee_rate: string | number;
  payment_fee_fixed: string | number;
  refund_allowance_rate: string | number;
  target_profit_margin: string | number;
  notes?: string | null;
  updated_at: string;
  calculation: {
    version: string;
    status: "target_viable" | "cost_sensitive" | "break_even_only" | "negative_contribution";
    label: string;
    explanation: string;
    landed_variable_cost_low: string | number;
    landed_variable_cost_high: string | number;
    payment_fee: string | number;
    refund_allowance: string | number;
    pre_ad_contribution_low: string | number;
    pre_ad_contribution_high: string | number;
    contribution_margin_low: string | number;
    contribution_margin_high: string | number;
    break_even_cpa_low: string | number;
    break_even_cpa_high: string | number;
    break_even_roas_low?: string | number | null;
    break_even_roas_high?: string | number | null;
    target_cpa_low: string | number;
    target_cpa_high: string | number;
    target_roas_low?: string | number | null;
    target_roas_high?: string | number | null;
    formula_notice: string;
  };
}

interface InvestigationItem {
  id: number;
  entity_type: "store" | "product" | "ad";
  entity_id: number;
  entity_title: string;
  entity_subtitle?: string | null;
  entity_url: string;
  workflow_stage: "inbox" | "researching" | "ready_to_test" | "testing" | "decided" | "archived";
  decision: "undecided" | "investigate" | "test" | "reject";
  priority: "low" | "medium" | "high";
  thesis?: string | null;
  risks?: string | null;
  next_action?: string | null;
  evidence: Array<{ id: number; evidence_type: string; source_type: string; details?: string | null; observed_at?: string | null }>;
  created_at: string;
  updated_at: string;
}

interface ProductComparisonData {
  generated_at: string;
  known_corpus: { product_count: number; store_count: number; selected_product_count: number };
  products: Array<{
    product_id: number;
    title: string;
    canonical_url: string;
    store_id: number;
    store_domain: string;
    platform: string;
    currency?: string | null;
    price_low?: number | null;
    price_high?: number | null;
    available?: boolean | null;
    variant_count?: number | null;
    image_count: number;
    first_observed_at: string;
    last_observed_at: string;
    observation_days: number;
    related_ad_count: number;
    evidence_count: number;
    evidence_types: string[];
    economics?: {
      scenario_name: string;
      revision: number;
      currency: string;
      status: string;
      label: string;
      break_even_cpa_low: string | number;
      break_even_cpa_high: string | number;
      target_cpa_low: string | number;
      target_cpa_high: string | number;
      target_roas_low?: string | number | null;
      target_roas_high?: string | number | null;
      input_source: string;
    } | null;
    unavailable: string[];
  }>;
  data_notice: string;
}

interface IntelligenceEvidence {
  type?: string;
  label?: string;
  value?: unknown;
  source?: string;
  observed_at?: string;
  explanation?: string;
  [key: string]: unknown;
}

interface IntelligenceInsight {
  status?: string;
  low?: number | null;
  central?: number | null;
  high?: number | null;
  value?: unknown;
  score?: number | null;
  currency?: string;
  unit?: string;
  confidence_score?: number | null;
  confidence_label?: string | null;
  evidence?: IntelligenceEvidence[];
  assumptions?: Record<string, unknown> | string[];
  missing_signals?: string[];
  explanation?: string;
  estimator_version?: string;
  [key: string]: unknown;
}

type InsightValue = IntelligenceInsight | string | number | boolean | null;

interface IntelligenceStore {
  id?: number;
  domain?: string;
  brand_name?: string;
  name?: string;
  platform?: string;
  category?: string;
  primary_category?: string;
  market?: string;
  main_country?: string;
  currency?: string;
  url?: string;
  [key: string]: unknown;
}

interface IntelligenceExecutiveSummary {
  verdict?: InsightValue;
  strongest_evidence?: unknown;
  largest_uncertainty?: unknown;
  next_step?: unknown;
  overall_confidence?: InsightValue;
  metrics?: {
    monthly_visits?: InsightValue;
    monthly_orders?: InsightValue;
    monthly_revenue?: InsightValue;
    aov?: InsightValue;
    store_momentum?: InsightValue;
    advertising_status?: InsightValue;
    dropshipping_likelihood?: InsightValue;
    [key: string]: InsightValue | undefined;
  };
}

interface IntelligenceTraffic {
  status?: string;
  provider?: string;
  periods?: unknown[];
  trend?: InsightValue;
  unavailable_metrics?: string[];
  source_notice?: string;
  [key: string]: unknown;
}

interface IntelligenceProduct {
  rank?: number;
  id?: number;
  title?: string;
  url?: string;
  image_url?: string;
  current_price?: number | null;
  currency?: string;
  first_seen_at?: string;
  momentum?: InsightValue;
  active_related_ads?: InsightValue;
  review_signal?: InsightValue;
  sales_contribution?: InsightValue;
  saturation?: InsightValue;
  supplier_match?: InsightValue;
  estimated_margin?: InsightValue;
  reasons?: unknown;
  uncertainties?: unknown;
  confidence?: InsightValue;
  [key: string]: unknown;
}

interface StoreIntelligenceReportData {
  report_version?: string;
  generated_at?: string;
  store?: IntelligenceStore;
  executive_summary?: IntelligenceExecutiveSummary;
  traffic?: IntelligenceTraffic;
  products?: IntelligenceProduct[];
  ads?: unknown;
  offers_and_funnel?: unknown;
  technology?: unknown;
  evidence_and_assumptions?: unknown;
  diagnostics?: unknown;
}

interface StoreIdentityCandidate {
  id: number;
  identity_type: string;
  display_value: string;
  source_type: string;
  source_url?: string | null;
  confidence_score: number;
  is_confirmed: boolean;
  evidence?: Record<string, unknown>;
  first_seen_at?: string;
  last_seen_at?: string;
  confirmed_at?: string | null;
}

interface ScanSource {
  id: number;
  url: string;
  type: string;
  fetch_status: string;
  last_http_status?: number;
  created_at: string;
  last_fetched_at?: string;
}

interface ScanJob {
  id: string;
  label: string;
  status: "queued" | "running" | "completed" | "failed";
  created_at: string;
  started_at?: string;
  finished_at?: string;
  error?: string;
}

interface LocalLibraryData {
  summary: {
    stores: number;
    observed_stores?: number;
    submitted_stores?: number;
    products: number;
    sources: number;
    fetched_sources?: number;
    active_jobs: number;
  };
  stores: LocalStore[];
  products: LocalProduct[];
  sources: ScanSource[];
  jobs: ScanJob[];
}

interface RealAd {
  id: number;
  external_ad_id?: string;
  data_provider: string;
  source_type: string;
  provider_record_id?: string;
  source_url?: string;
  provider_metadata?: Record<string, unknown>;
  platform: string;
  advertiser_name?: string;
  advertiser_id?: string;
  ad_text?: string;
  headline?: string;
  cta?: string;
  landing_url?: string;
  first_seen_at: string;
  last_seen_at: string;
  creative_type: string;
  creative_urls?: string[];
  publisher_platforms?: string[];
  ad_creation_time?: string;
  delivery_start_time?: string;
  delivery_stop_time?: string;
  ad_snapshot_url?: string;
}

interface AdMetricData {
  id: number;
  ad_id: number;
  metric_key: string;
  value_kind: string;
  value_numeric?: string | number | null;
  range_low?: string | number | null;
  range_high?: string | number | null;
  value_text?: string | null;
  unit?: string | null;
  provider: string;
  source_type: string;
  source_url?: string | null;
  geography?: string | null;
  period_start?: string | null;
  period_end?: string | null;
  confidence_score?: string | number | null;
  observed_at: string;
}

interface AdAnalyticsData {
  ad_id: number;
  data_provider: string;
  source_type: string;
  source_url?: string | null;
  metrics: AdMetricData[];
  observed_signals: Array<{
    metric_key: string;
    value_kind: string;
    value: unknown;
    unit?: string;
    source: string;
    explanation: string;
  }>;
  unavailable_metrics: Array<{ metric_key: string; reason: string }>;
  has_provider_performance_metrics: boolean;
  data_notice: string;
}

interface AdLibraryFacets {
  metric_keys: string[];
  geographies: string[];
  metric_keys_by_ad: Record<string, string[]>;
  geographies_by_ad: Record<string, string[]>;
  data_notice: string;
}

interface AdAutopsyData {
  ad: RealAd;
  analytics: AdAnalyticsData;
  creative_analysis: {
    asset_count: number;
    media_state: "available" | "not_saved";
    transcript_status: "not_collected";
    ocr_status: "not_collected";
    notice: string;
  };
  landing_pages: Array<{
    source_url_id: number;
    url: string;
    fetch_status?: string | null;
    last_http_status?: number | null;
    last_fetched_at?: string | null;
    final_url?: string | null;
    snapshot_fetched_at?: string | null;
    products: Array<{
      id: number;
      title: string;
      canonical_url: string;
      currency?: string | null;
      store_id: number;
      store_domain: string;
    }>;
  }>;
  store?: { id: number; domain: string; platform: string; last_seen_at: string } | null;
  products: Array<{
    id: number;
    title: string;
    canonical_url: string;
    currency?: string | null;
    store_id: number;
    store_domain: string;
  }>;
  related_ads: Array<{ ad: RealAd; reasons: string[] }>;
  conclusion: {
    status: "investigate" | "weak_evidence" | "insufficient_data";
    label: string;
    explanation: string;
    next_step: string;
  };
}

interface MetaSearchResult {
  status: string;
  fetched_count: number;
  inserted_count: number;
  updated_count: number;
  skipped_count: number;
}

interface AdWatchRun {
  id: number;
  status: string;
  trigger: string;
  started_at: string;
  finished_at?: string | null;
  fetched_count: number;
  inserted_count: number;
  updated_count: number;
  recurring_count: number;
  error_code?: string | null;
  error_message?: string | null;
}

interface AdWatch {
  id: number;
  name: string;
  provider: string;
  store_domain?: string | null;
  search_terms?: string | null;
  advertiser_id?: string | null;
  countries: string[];
  interval_hours: number;
  result_limit: number;
  is_enabled: boolean;
  last_run_at?: string | null;
  next_run_at?: string | null;
  last_status: string;
  last_error?: string | null;
  ad_count: number;
  retention_tiers: Record<string, number>;
  observation_statuses: Record<string, number>;
  latest_run?: AdWatchRun | null;
}

interface AdWatchListData {
  watches: AdWatch[];
  summary: { total: number; enabled: number; due: number; failed: number };
  retention_policy: Record<string, string>;
}

interface GetHookdAd {
  provider: "gethookd";
  source: string;
  provider_ad_id?: string | null;
  external_ad_id?: string | null;
  platforms: string[];
  advertiser_name?: string | null;
  advertiser_id?: string | null;
  advertiser_logo_url?: string | null;
  headline?: string | null;
  ad_text?: string | null;
  cta?: string | null;
  creative_type: string;
  creative_urls: string[];
  thumbnail_url?: string | null;
  landing_url?: string | null;
  provider_url?: string | null;
  delivery_start_time?: string | null;
  delivery_stop_time?: string | null;
  days_active?: number | null;
  is_active: boolean;
  provider_score?: number | null;
  provider_classification?: string | null;
  used_count?: number | null;
}

interface GetHookdSearchResult {
  provider: "gethookd";
  status: string;
  query: string;
  result_count: number;
  used_credits?: number | null;
  remaining_credits?: number | null;
  ads: GetHookdAd[];
  data_notice: string;
}

interface IntegrationProviderStatus {
  configured: boolean;
  active_source?: "environment" | "local_file" | string | null;
  connected?: boolean;
  status?: string;
  detail?: string;
  masked_key?: string;
  masked_token?: string;
  graph_version?: string;
}

interface IntegrationStatus {
  meta?: IntegrationProviderStatus;
  gethookd?: IntegrationProviderStatus;
  similarweb?: IntegrationProviderStatus;
  meta_configured?: boolean;
  similarweb_configured?: boolean;
}

interface EstimationProfileSettings {
  id: number;
  name: string;
  category_key: string;
  is_default: boolean;
  version: string;
  conversion_rate_low: number;
  conversion_rate_central?: number | null;
  conversion_rate_high: number;
  basket_multiplier_low: number;
  basket_multiplier_central?: number | null;
  basket_multiplier_high: number;
  traffic_reliability_low: number;
  traffic_reliability_central?: number | null;
  traffic_reliability_high: number;
  freshness_limit_days: number;
  minimum_evidence_count: number;
  score_weights: Record<string, number>;
  thresholds: Record<string, unknown>;
  updated_at: string;
}

const emptyLibrary: LocalLibraryData = {
  summary: { stores: 0, products: 0, sources: 0, active_jobs: 0 },
  stores: [],
  products: [],
  sources: [],
  jobs: [],
};

const navItems: { id: View; label: string; icon: LucideIcon }[] = [
  { id: "overview", label: "Overview", icon: LayoutDashboard },
  { id: "products", label: "Product discovery", icon: PackageSearch },
  { id: "stores", label: "Stores & traffic", icon: Store },
  { id: "ads", label: "Ad library", icon: Ad },
  { id: "shortlist", label: "Investigation shortlist", icon: ClipboardList },
  { id: "compare", label: "Compare products", icon: GitCompareArrows },
];

const reportTabs: { id: ReportTab; label: string; icon: LucideIcon }[] = [
  { id: "overview", label: "Overview", icon: LayoutDashboard },
  { id: "products", label: "Products", icon: PackageSearch },
  { id: "traffic", label: "Traffic", icon: TrendingUp },
  { id: "ads", label: "Ads", icon: Ad },
  { id: "offers", label: "Offers & funnel", icon: ShoppingBag },
  { id: "technology", label: "Technology", icon: Zap },
  { id: "evidence", label: "Evidence", icon: ShieldCheck },
  { id: "diagnostics", label: "Diagnostics", icon: Activity },
];

const reportTabIds = new Set<ReportTab>(reportTabs.map((tab) => tab.id));

function parseLocationRoute(): {
  view: View;
  storeId: number | null;
  adId: number | null;
  reportTab: ReportTab;
} {
  const path = window.location.pathname.replace(/\/+$/, "") || "/";
  const reportMatch = path.match(/^\/stores\/(\d+)(?:\/([^/]+))?$/);
  if (reportMatch) {
    const requestedTab = reportMatch[2] as ReportTab | undefined;
    return {
      view: "store-report",
      storeId: Number(reportMatch[1]),
      adId: null,
      reportTab:
        requestedTab && reportTabIds.has(requestedTab)
          ? requestedTab
          : "overview",
    };
  }
  const adMatch = path.match(/^\/ads\/(\d+)$/);
  if (adMatch) {
    return {
      view: "ad-detail",
      storeId: null,
      adId: Number(adMatch[1]),
      reportTab: "overview",
    };
  }
  const viewByPath: Record<string, View> = {
    "/": "overview",
    "/products": "products",
    "/shopify-product": "products",
    "/stores": "stores",
    "/ads": "ads",
    "/library-product": "ads",
    "/shortlist": "shortlist",
    "/compare": "compare",
    "/settings": "settings",
  };
  return {
    view: viewByPath[path] || "overview",
    storeId: null,
    adId: null,
    reportTab: "overview",
  };
}

const formatNumber = (value?: number | null) =>
  value == null
    ? "—"
    : new Intl.NumberFormat("en-US", {
        notation: "compact",
        maximumFractionDigits: 1,
      }).format(value);

const formatMoney = (value?: number | null, currency = "USD") => {
  if (value == null) return "—";
  try {
    return new Intl.NumberFormat("en-US", {
      style: "currency",
      currency,
      maximumFractionDigits: 2,
    }).format(value);
  } catch {
    return `${value.toFixed(2)} ${currency}`;
  }
};

const formatDate = (value?: string) => {
  if (!value) return "Never";
  const normalized =
    value.endsWith("Z") || /[+-]\d\d:\d\d$/.test(value) ? value : `${value}Z`;
  const date = new Date(normalized);
  return Number.isNaN(date.getTime())
    ? value
    : date.toLocaleString([], {
        month: "short",
        day: "numeric",
        hour: "numeric",
        minute: "2-digit",
      });
};

const trafficFor = (store: LocalStore): TrafficData | null =>
  store.traffic || store.latest_traffic || null;

function trafficPeriod(traffic: TrafficData) {
  if (traffic.period_start && traffic.period_end) {
    return traffic.period_start === traffic.period_end
      ? traffic.period_start
      : `${traffic.period_start} to ${traffic.period_end}`;
  }
  return traffic.period || null;
}

function trafficIssue(traffic: TrafficData) {
  const metrics: [string, TrafficMetricStatus | undefined][] = [
    ["Visits", traffic.metric_status?.total_visits],
    ["Global rank", traffic.metric_status?.global_rank],
  ];
  const issue = metrics.find(
    ([, metric]) => metric?.status && metric.status !== "success",
  );
  if (!issue) return null;
  const [label, metric] = issue;
  const reason = metric?.message || metric?.status?.replace(/_/g, " ");
  return reason ? `${label}: ${reason}` : `${label} was unavailable`;
}

function isConfigured(
  status: IntegrationStatus | null,
  provider: "meta" | "gethookd" | "similarweb",
) {
  if (!status) return false;
  if (provider === "meta")
    return Boolean(status.meta?.configured ?? status.meta_configured);
  if (provider === "gethookd") return Boolean(status.gethookd?.configured);
  return Boolean(status.similarweb?.configured ?? status.similarweb_configured);
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

function humanize(value: string) {
  return value
    .replace(/[_-]+/g, " ")
    .replace(/\b\w/g, (character) => character.toUpperCase());
}

function asInsight(value: InsightValue | unknown): IntelligenceInsight | null {
  return isRecord(value) ? (value as IntelligenceInsight) : null;
}

function numericInsightValue(value: unknown): number | null {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  const insight = asInsight(value);
  if (!insight) return null;
  const candidate = insight.central ?? insight.value ?? insight.score;
  return typeof candidate === "number" && Number.isFinite(candidate)
    ? candidate
    : null;
}

function confidenceText(value: unknown) {
  const insight = asInsight(value);
  if (!insight) return null;
  if (insight.confidence_label) return humanize(insight.confidence_label);
  if (typeof insight.confidence_score === "number") {
    const score =
      insight.confidence_score <= 1
        ? insight.confidence_score * 100
        : insight.confidence_score;
    return `${Math.round(score)}% confidence`;
  }
  return null;
}

function insightStatus(value: unknown) {
  const status = asInsight(value)?.status?.toLowerCase();
  return status || null;
}

function isUnavailableInsight(value: unknown) {
  const status = insightStatus(value);
  return Boolean(
    status &&
      [
        "unavailable",
        "insufficient",
        "insufficient_data",
        "missing",
        "not_calculated",
        "unknown",
      ].includes(status),
  );
}

function metricFormatter(
  kind: "number" | "money" | "percent" | "text",
  currency = "USD",
) {
  return (value: number | string | boolean) => {
    if (typeof value !== "number") return String(value);
    if (kind === "money") return formatMoney(value, currency);
    if (kind === "percent") {
      const normalized = Math.abs(value) <= 1 ? value * 100 : value;
      return `${Math.round(normalized * 10) / 10}%`;
    }
    if (kind === "number") return formatNumber(value);
    return String(value);
  };
}

function formatInsightValue(
  value: unknown,
  kind: "number" | "money" | "percent" | "text" = "text",
  currency = "USD",
) {
  const format = metricFormatter(kind, currency);
  if (typeof value === "string" || typeof value === "boolean")
    return String(value);
  if (typeof value === "number") return format(value);
  const insight = asInsight(value);
  if (!insight) return "Insufficient data";
  if (isUnavailableInsight(insight)) return "Insufficient data";
  if (typeof insight.low === "number" && typeof insight.high === "number") {
    return `${format(insight.low)}–${format(insight.high)}`;
  }
  if (
    typeof insight.value === "string" ||
    typeof insight.value === "boolean" ||
    typeof insight.value === "number"
  ) {
    return format(insight.value);
  }
  if (typeof insight.central === "number") return format(insight.central);
  if (typeof insight.score === "number") return format(insight.score);
  return "Insufficient data";
}

function evidenceLabel(evidence: IntelligenceEvidence) {
  const label = evidence.label || evidence.type;
  const value = evidence.value;
  if (label && ["string", "number", "boolean"].includes(typeof value)) {
    return `${humanize(label)}: ${String(value)}`;
  }
  if (evidence.explanation) return evidence.explanation;
  if (label) return humanize(label);
  if (typeof value === "string") return value;
  return evidence.source
    ? `Evidence from ${evidence.source}`
    : "Evidence record";
}

function toTextList(value: unknown): string[] {
  if (value == null) return [];
  if (["string", "number", "boolean"].includes(typeof value))
    return [String(value)];
  if (Array.isArray(value))
    return value.flatMap((item) => toTextList(item)).filter(Boolean);
  if (!isRecord(value)) return [];
  if (
    "type" in value ||
    "label" in value ||
    "explanation" in value ||
    "source" in value
  ) {
    return [evidenceLabel(value as IntelligenceEvidence)];
  }
  return Object.entries(value).flatMap(([key, item]) => {
    if (["string", "number", "boolean"].includes(typeof item)) {
      return [`${humanize(key)}: ${String(item)}`];
    }
    return [];
  });
}

function insightEvidence(value: unknown) {
  const evidence = asInsight(value)?.evidence;
  return Array.isArray(evidence) ? evidence : [];
}

function insightMissingSignals(value: unknown) {
  const missing = asInsight(value)?.missing_signals;
  return Array.isArray(missing) ? missing.filter(Boolean) : [];
}

function insightExplanation(value: unknown) {
  return asInsight(value)?.explanation || null;
}

function StatusPill({ status }: { status: string }) {
  const normalized = status.toLowerCase().replace(/[^a-z0-9]+/g, "-");
  return (
    <span className={`real-status status-${normalized}`}>
      <i />
      {status}
    </span>
  );
}

function PageHeading({
  eyebrow,
  title,
  subtitle,
  actions,
}: {
  eyebrow: string;
  title: string;
  subtitle: string;
  actions?: React.ReactNode;
}) {
  return (
    <div className="page-heading">
      <div>
        <span className="eyebrow">{eyebrow}</span>
        <h1>{title}</h1>
        <p>{subtitle}</p>
      </div>
      {actions && <div className="heading-actions">{actions}</div>}
    </div>
  );
}

function Sidebar({
  view,
  open,
  onNavigate,
  onClose,
}: {
  view: View;
  open: boolean;
  onNavigate: (view: View) => void;
  onClose: () => void;
}) {
  return (
    <>
      {open && (
        <button
          className="sidebar-scrim"
          onClick={onClose}
          aria-label="Close menu"
        />
      )}
      <aside className={`sidebar ${open ? "sidebar-open" : ""}`}>
        <div className="brand-mark">
          <div className="brand-icon">
            <Radar size={21} />
          </div>
          <div>
            <strong>Northstar</strong>
            <span>local commerce intelligence</span>
          </div>
          <button
            className="icon-button sidebar-close"
            onClick={onClose}
            aria-label="Close navigation"
          >
            <X size={19} />
          </button>
        </div>
        <nav className="side-nav">
          <div className="nav-group">
            <p>OBSERVED DATA</p>
            {navItems.map((item) => {
              const Icon = item.icon;
              return (
                <button
                  key={item.id}
                  className={view === item.id ? "active" : ""}
                  onClick={() => {
                    onNavigate(item.id);
                    onClose();
                  }}
                >
                  <Icon size={18} />
                  <span>{item.label}</span>
                </button>
              );
            })}
          </div>
        </nav>
        <div className="sidebar-foot">
          <button
            onClick={() => onNavigate("settings")}
            className={view === "settings" ? "active" : ""}
          >
            <Settings size={18} />
            Settings & sources
          </button>
          <div className="privacy-note">
            <ShieldCheck size={15} />
            <span>
              Private SQLite storage
              <br />
              No billing or cloud account
            </span>
          </div>
        </div>
      </aside>
    </>
  );
}

function Header({
  apiStatus,
  onMenu,
  onRefresh,
}: {
  apiStatus: ApiStatus;
  onMenu: () => void;
  onRefresh: () => void;
}) {
  return (
    <header className="topbar">
      <button className="icon-button mobile-menu" onClick={onMenu}>
        <Menu size={20} />
      </button>
      <div className="header-context">
        <Database size={16} />
        <span>Observed, provider, and derived values stay clearly labeled</span>
      </div>
      <div className="top-actions">
        <div className={`data-status status-${apiStatus}`}>
          <span />
          {apiStatus === "connected"
            ? "Local engine connected"
            : apiStatus === "checking"
              ? "Connecting…"
              : "Local engine offline"}
        </div>
        <button
          className="icon-button"
          onClick={onRefresh}
          aria-label="Refresh"
        >
          <RefreshCw size={17} />
        </button>
        <div className="profile-button">
          <span>AX</span>
          <div>
            <b>Andrew</b>
            <small>Local research</small>
          </div>
        </div>
      </div>
    </header>
  );
}

function EmptyState({
  icon: Icon,
  title,
  body,
  action,
}: {
  icon: LucideIcon;
  title: string;
  body: string;
  action?: React.ReactNode;
}) {
  return (
    <div className="empty-state real-empty">
      <Icon size={32} />
      <h2>{title}</h2>
      <p>{body}</p>
      {action}
    </div>
  );
}

function ConfidenceBadge({ value }: { value: unknown }) {
  const insight = asInsight(value);
  const direct =
    typeof value === "string"
      ? humanize(value)
      : typeof insight?.value === "string"
        ? humanize(insight.value)
        : null;
  const label = direct || confidenceText(value) || "Confidence not rated";
  const tone = label.toLowerCase().includes("high")
    ? "high"
    : label.toLowerCase().includes("medium")
      ? "medium"
      : label.toLowerCase().includes("low")
        ? "low"
        : "unknown";
  return (
    <span className={`report-confidence confidence-${tone}`}>{label}</span>
  );
}

function InsightDetails({
  insight: value,
  label = "Evidence and assumptions",
}: {
  insight: unknown;
  label?: string;
}) {
  const insight = asInsight(value);
  if (!insight) return null;
  const evidence = insightEvidence(insight);
  const assumptions = toTextList(insight.assumptions);
  const missing = insightMissingSignals(insight);
  if (
    !evidence.length &&
    !assumptions.length &&
    !missing.length &&
    !insight.explanation &&
    !insight.estimator_version
  ) {
    return null;
  }
  return (
    <details className="insight-details">
      <summary>{label}</summary>
      {insight.explanation && <p>{insight.explanation}</p>}
      {evidence.length > 0 && (
        <div className="insight-detail-group">
          <b>Evidence</b>
          <ul>
            {evidence.map((item, index) => (
              <li key={`${item.type || item.label || "evidence"}-${index}`}>
                <span>{evidenceLabel(item)}</span>
                {(item.source || item.observed_at) && (
                  <small>
                    {[
                      item.source,
                      item.observed_at && formatDate(item.observed_at),
                    ]
                      .filter(Boolean)
                      .join(" · ")}
                  </small>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}
      {assumptions.length > 0 && (
        <div className="insight-detail-group">
          <b>Assumptions</b>
          <ul>
            {assumptions.map((assumption, index) => (
              <li key={`${assumption}-${index}`}>{assumption}</li>
            ))}
          </ul>
        </div>
      )}
      {missing.length > 0 && (
        <div className="insight-detail-group missing">
          <b>Missing signals</b>
          <ul>
            {missing.map((signal) => (
              <li key={signal}>{humanize(signal)}</li>
            ))}
          </ul>
        </div>
      )}
      {insight.estimator_version && (
        <small className="estimator-version">
          Model {insight.estimator_version}
        </small>
      )}
    </details>
  );
}

function InsightMetricCard({
  label,
  value,
  kind = "text",
  currency = "USD",
  icon: Icon,
}: {
  label: string;
  value: unknown;
  kind?: "number" | "money" | "percent" | "text";
  currency?: string;
  icon?: LucideIcon;
}) {
  const insight = asInsight(value);
  const confidence = confidenceText(value);
  const missing = insightMissingSignals(value);
  const evidenceCount = insightEvidence(value).length;
  const central = insight?.central;
  const hasRange =
    typeof insight?.low === "number" && typeof insight?.high === "number";
  return (
    <article
      className={`insight-metric-card ${isUnavailableInsight(value) ? "metric-unavailable" : ""}`}
    >
      <header>
        {Icon && <Icon size={16} />}
        <span>{label}</span>
      </header>
      <strong>{formatInsightValue(value, kind, currency)}</strong>
      {hasRange && typeof central === "number" && (
        <small>
          Central {metricFormatter(kind, currency)(central)} when justified
        </small>
      )}
      {!hasRange && insightExplanation(value) && (
        <small>{insightExplanation(value)}</small>
      )}
      <footer>
        <span>{confidence || "Confidence not rated"}</span>
        <span>
          {evidenceCount
            ? `${evidenceCount} evidence ${evidenceCount === 1 ? "item" : "items"}`
            : missing.length
              ? `${missing.length} missing ${missing.length === 1 ? "signal" : "signals"}`
              : "No cited evidence"}
        </span>
      </footer>
    </article>
  );
}

function DecisionStatement({
  title,
  value,
  tone,
}: {
  title: string;
  value: unknown;
  tone: "evidence" | "uncertainty" | "next";
}) {
  const items = toTextList(value);
  return (
    <article className={`decision-statement statement-${tone}`}>
      <span>{title}</span>
      {items.length ? (
        <ul>
          {items.slice(0, 4).map((item, index) => (
            <li key={`${item}-${index}`}>{item}</li>
          ))}
        </ul>
      ) : (
        <p>No responsible conclusion is available from the current evidence.</p>
      )}
    </article>
  );
}

function ProductInsightCell({ value }: { value: unknown }) {
  return (
    <div className="product-insight-cell">
      <b>{formatInsightValue(value)}</b>
      <small>{confidenceText(value) || "Confidence not rated"}</small>
    </div>
  );
}

function ProductInsightItem({
  label,
  value,
}: {
  label: string;
  value: unknown;
}) {
  return (
    <div className="product-insight-item">
      <span>{label}</span>
      <ProductInsightCell value={value} />
    </div>
  );
}

function IntelligenceProductsTable({
  products,
  compact = false,
}: {
  products: IntelligenceProduct[];
  compact?: boolean;
}) {
  if (!products.length) {
    return (
      <div className="inline-empty report-inline-empty">
        <PackageSearch size={27} />
        <b>No ranked products yet</b>
        <span>
          Catalog presence alone is not evidence of sales. Northstar needs
          product-level demand signals before ranking anything.
        </span>
      </div>
    );
  }
  const visible = compact ? products.slice(0, 3) : products;
  return (
    <div className={`intelligence-product-grid ${compact ? "compact" : ""}`}>
      {visible.map((product, index) => {
        const rank = product.rank;
        const hasSupportedRank = !isUnavailableInsight(product.momentum);
        const reasons = toTextList(product.reasons);
        const uncertainties = toTextList(product.uncertainties);
        return (
          <article
            className="intelligence-product-card"
            key={product.id ?? `${product.url || product.title}-${index}`}
          >
            <header>
              <span className="product-rank">
                {hasSupportedRank && rank != null ? `#${rank}` : "—"}
              </span>
              <div className="report-product-cell">
                <span>
                  {product.image_url ? (
                    <img src={product.image_url} alt="" loading="lazy" />
                  ) : (
                    <ShoppingBag size={18} />
                  )}
                </span>
                <div>
                  <b>{product.title || "Untitled product"}</b>
                  <small>
                    {formatMoney(product.current_price, product.currency)} · First
                    seen {product.first_seen_at ? formatDate(product.first_seen_at) : "unknown"}
                  </small>
                </div>
              </div>
              <div className="product-card-actions">
                <ConfidenceBadge value={product.confidence} />
                {product.url && (
                  <button
                    className="icon-button"
                    aria-label={`Open ${product.title || "product"}`}
                    onClick={() => window.open(product.url, "_blank", "noopener")}
                  >
                    <ExternalLink size={14} />
                  </button>
                )}
              </div>
            </header>
            <div className="product-insight-grid">
              <ProductInsightItem label="Momentum" value={product.momentum} />
              {!compact && <ProductInsightItem label="Related ads" value={product.active_related_ads} />}
              {!compact && <ProductInsightItem label="Reviews" value={product.review_signal} />}
              <ProductInsightItem label="Sales contribution" value={product.sales_contribution} />
              <ProductInsightItem label="Saturation" value={product.saturation} />
              {!compact && <ProductInsightItem label="Supplier" value={product.supplier_match} />}
              {!compact && <ProductInsightItem label="Estimated margin" value={product.estimated_margin} />}
            </div>
            {(reasons.length > 0 || uncertainties.length > 0) && (
              <details className="product-evidence-details">
                <summary>{hasSupportedRank ? "Why it ranked here" : "Evidence gaps"}</summary>
                {reasons.length > 0 && (
                  <ul>{reasons.slice(0, 4).map((reason) => <li key={reason}>{reason}</li>)}</ul>
                )}
                {uncertainties.length > 0 && <p>Missing: {uncertainties.map(humanize).join("; ")}</p>}
              </details>
            )}
          </article>
        );
      })}
    </div>
  );
}

function ReportOverview({ report }: { report: StoreIntelligenceReportData }) {
  const executive = report.executive_summary || {};
  const metrics = executive.metrics || {};
  const currency = report.store?.currency || "USD";
  const verdict = formatInsightValue(executive.verdict);
  const products = Array.isArray(report.products) ? report.products : [];
  const hasRankedProducts = products.some(
    (product) => !isUnavailableInsight(product.momentum),
  );
  const metricEntries: [string, unknown][] = [
    ["Estimated monthly visits", metrics.monthly_visits],
    ["Estimated monthly orders", metrics.monthly_orders],
    ["Estimated gross revenue", metrics.monthly_revenue],
    ["Estimated AOV", metrics.aov],
    ["Store momentum", metrics.store_momentum],
    ["Advertising status", metrics.advertising_status],
    ["Dropshipping likelihood", metrics.dropshipping_likelihood],
  ];
  const supportedMetricCount = metricEntries.filter(
    ([, value]) => !isUnavailableInsight(value),
  ).length;
  const missingMetricSignals = Array.from(
    new Set(metricEntries.flatMap(([, value]) => insightMissingSignals(value))),
  );
  const technologyRecord = isRecord(report.technology) ? report.technology : {};
  const technologyDetections = Array.isArray(technologyRecord.detections)
    ? technologyRecord.detections
    : [];
  const offersRecord = isRecord(report.offers_and_funnel)
    ? report.offers_and_funnel
    : {};
  const observedOfferCount = Array.isArray(offersRecord.offers)
    ? offersRecord.offers.length
    : 0;
  const observedFunnelCount = Array.isArray(offersRecord.funnel_elements)
    ? offersRecord.funnel_elements.length
    : 0;
  const productsWithImages = products.filter((product) => Boolean(product.image_url)).length;
  return (
    <div className="report-section-stack">
      <section className="decision-summary-grid">
        <article className="panel decision-verdict-card">
          <span className="eyebrow">NORTHSTAR DECISION</span>
          <h2>{verdict}</h2>
          <p>
            {insightExplanation(executive.verdict) ||
              "This conclusion is limited to the evidence Northstar has collected."}
          </p>
          <ConfidenceBadge value={executive.overall_confidence} />
          <InsightDetails insight={executive.verdict} />
        </article>
        <div className="decision-statements">
          <DecisionStatement
            title="Strongest supporting evidence"
            value={executive.strongest_evidence}
            tone="evidence"
          />
          <DecisionStatement
            title="Largest uncertainty"
            value={executive.largest_uncertainty}
            tone="uncertainty"
          />
          <DecisionStatement
            title="Next investigation"
            value={executive.next_step}
            tone="next"
          />
        </div>
      </section>

      <section className="observed-overview-section">
        <div className="section-kicker">
          <span>Observed without provider APIs</span>
          <small>Directly collected from the public storefront</small>
        </div>
        <div className="observed-overview-grid">
          <article>
            <PackageSearch size={16} />
            <span>Catalog products</span>
            <b>{products.length}</b>
            <small>Visible in this intelligence report</small>
          </article>
          <article>
            <Image size={16} />
            <span>Product images</span>
            <b>{productsWithImages} / {products.length}</b>
            <small>Latest product observation coverage</small>
          </article>
          <article>
            <Zap size={16} />
            <span>Technologies</span>
            <b>{technologyDetections.length}</b>
            <small>Public homepage and Shopify app markers</small>
          </article>
          <article>
            <ShoppingBag size={16} />
            <span>Offer & funnel signals</span>
            <b>{observedOfferCount + observedFunnelCount}</b>
            <small>{observedOfferCount} offers · {observedFunnelCount} funnel elements</small>
          </article>
        </div>
      </section>

      <section className="report-readiness-strip">
        <div>
          <span>Decision data readiness</span>
          <b>{supportedMetricCount} of {metricEntries.length} headline metrics supported</b>
          <small>
            {missingMetricSignals.length
              ? "Unavailable metrics need additional providers, history, or collectors—not another identical scan."
              : "The current headline inputs passed their evidence gates."}
          </small>
        </div>
        {missingMetricSignals.length > 0 && (
          <div className="readiness-missing-signals">
            {missingMetricSignals.slice(0, 4).map((signal) => (
              <span key={signal}>{humanize(signal)}</span>
            ))}
            {missingMetricSignals.length > 4 && <span>+{missingMetricSignals.length - 4} more</span>}
          </div>
        )}
      </section>

      <section className="report-metric-grid">
        <InsightMetricCard
          label="Estimated monthly visits"
          value={metrics.monthly_visits}
          kind="number"
          icon={Globe2}
        />
        <InsightMetricCard
          label="Estimated monthly orders"
          value={metrics.monthly_orders}
          kind="number"
          icon={ShoppingBag}
        />
        <InsightMetricCard
          label="Estimated gross revenue"
          value={metrics.monthly_revenue}
          kind="money"
          currency={currency}
          icon={TrendingUp}
        />
        <InsightMetricCard
          label="Estimated AOV"
          value={metrics.aov}
          kind="money"
          currency={currency}
          icon={Gauge}
        />
        <InsightMetricCard
          label="Store momentum"
          value={metrics.store_momentum}
          icon={Activity}
        />
        <InsightMetricCard
          label="Advertising status"
          value={metrics.advertising_status}
          icon={Ad}
        />
        <InsightMetricCard
          label="Dropshipping likelihood"
          value={metrics.dropshipping_likelihood}
          icon={Radar}
        />
      </section>

      <section className="panel report-ranked-products">
        <div className="panel-header">
          <div>
            <h2>
              {hasRankedProducts
                ? "Products most worth investigating"
                : "Collected products — ranking withheld"}
            </h2>
            <p>
              {hasRankedProducts
                ? "Ranked only when there is evidence beyond simple catalog presence."
                : "Northstar has catalog records, but not enough independent demand evidence to rank them."}
            </p>
          </div>
        </div>
        <IntelligenceProductsTable products={products} compact />
      </section>

      <section className="panel metric-methods-panel">
        <div className="panel-header">
          <div>
            <h2>How the headline estimates were formed</h2>
            <p>
              Evidence, assumptions, missing inputs, and estimator versions.
            </p>
          </div>
        </div>
        <div className="metric-method-list">
          {metricEntries.map(([label, value]) => (
            <article key={label}>
              <div>
                <b>{label}</b>
                <span>{formatInsightValue(value)}</span>
              </div>
              <InsightDetails insight={value} label="Inspect basis" />
            </article>
          ))}
        </div>
      </section>
    </div>
  );
}

function trafficPeriodRecord(value: unknown) {
  return isRecord(value) ? value : null;
}

function firstRecordValue(record: Record<string, unknown>, keys: string[]) {
  for (const key of keys) {
    if (record[key] != null) return record[key];
  }
  return null;
}

function ReportTraffic({ traffic }: { traffic?: IntelligenceTraffic }) {
  const data = traffic || {};
  const periods = (Array.isArray(data.periods) ? data.periods : [])
    .map(trafficPeriodRecord)
    .filter((period): period is Record<string, unknown> => Boolean(period));
  const chartData = periods
    .map((period, index) => ({
      period: String(
        firstRecordValue(period, [
          "period",
          "month",
          "period_start",
          "reporting_date",
        ]) || `Period ${index + 1}`,
      ),
      visits: numericInsightValue(
        firstRecordValue(period, ["monthly_visits", "visits", "total_visits"]),
      ),
    }))
    .filter((point): point is { period: string; visits: number } =>
      Number.isFinite(point.visits),
    );
  const unavailable = Array.isArray(data.unavailable_metrics)
    ? data.unavailable_metrics
    : [];
  const channels = isRecord(data.channels)
    ? Object.entries(data.channels)
    : ([] as [string, unknown][]);
  const topCountries = Array.isArray(data.top_countries)
    ? data.top_countries
    : [];
  return (
    <div className="report-section-stack">
      <section className="traffic-report-head">
        <InsightMetricCard
          label="Traffic direction"
          value={data.trend}
          icon={TrendingUp}
        />
        <article className="panel traffic-source-card">
          <span>Source</span>
          <b>{data.provider || "No traffic provider"}</b>
          <StatusPill status={data.status || "insufficient data"} />
          <p>
            {data.source_notice ||
              "No provider statement was returned. Traffic estimates must not be treated as first-party analytics."}
          </p>
        </article>
      </section>

      {chartData.length >= 2 && (
        <section className="panel report-traffic-chart">
          <div className="panel-header">
            <div>
              <h2>Estimated visit direction</h2>
              <p>Provider periods only; gaps are left unfilled.</p>
            </div>
          </div>
          <div>
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart
                data={chartData}
                margin={{ top: 12, right: 22, left: 0, bottom: 0 }}
              >
                <CartesianGrid
                  strokeDasharray="3 3"
                  vertical={false}
                  stroke="#e9e8e4"
                />
                <XAxis
                  dataKey="period"
                  tickLine={false}
                  axisLine={false}
                  tick={{ fill: "#77756f", fontSize: 11 }}
                />
                <YAxis
                  tickFormatter={(value) => formatNumber(value)}
                  tickLine={false}
                  axisLine={false}
                  tick={{ fill: "#77756f", fontSize: 11 }}
                />
                <Tooltip
                  formatter={(value) => formatNumber(Number(value))}
                  contentStyle={{
                    border: "1px solid #e2e0da",
                    borderRadius: 10,
                    fontSize: 11,
                  }}
                />
                <Area
                  type="monotone"
                  dataKey="visits"
                  name="Estimated visits"
                  stroke="#6951d8"
                  strokeWidth={2.3}
                  fill="#eeeafd"
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </section>
      )}

      <section className="panel report-period-panel">
        <div className="panel-header">
          <div>
            <h2>Available reporting periods</h2>
            <p>Only metrics returned by the provider are shown.</p>
          </div>
        </div>
        {periods.length ? (
          <div className="table-scroll">
            <table className="data-table traffic-period-table">
              <thead>
                <tr>
                  <th>Period</th>
                  <th>Est. visits</th>
                  <th>Global rank</th>
                  <th>Country rank</th>
                  <th>Category rank</th>
                  <th>Visit duration</th>
                  <th>Pages / visit</th>
                  <th>Bounce rate</th>
                </tr>
              </thead>
              <tbody>
                {periods.map((period, index) => (
                  <tr key={String(period.period || period.month || index)}>
                    <td>
                      <b>
                        {String(
                          firstRecordValue(period, [
                            "period",
                            "month",
                            "period_start",
                            "reporting_date",
                          ]) || `Period ${index + 1}`,
                        )}
                      </b>
                    </td>
                    <td>
                      {formatInsightValue(
                        firstRecordValue(period, [
                          "monthly_visits",
                          "visits",
                          "total_visits",
                        ]),
                        "number",
                      )}
                    </td>
                    <td>{formatInsightValue(period.global_rank, "number")}</td>
                    <td>{formatInsightValue(period.country_rank, "number")}</td>
                    <td>
                      {formatInsightValue(period.category_rank, "number")}
                    </td>
                    <td>
                      {formatInsightValue(
                        firstRecordValue(period, [
                          "visit_duration",
                          "average_visit_duration",
                        ]),
                      )}
                    </td>
                    <td>
                      {formatInsightValue(
                        firstRecordValue(period, [
                          "pages_per_visit",
                          "pages_per_session",
                        ]),
                        "number",
                      )}
                    </td>
                    <td>{formatInsightValue(period.bounce_rate, "percent")}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="inline-empty report-inline-empty">
            <TrafficCone size={27} />
            <b>No traffic periods available</b>
            <span>
              Northstar will not substitute catalog activity or ad activity for
              missing Similarweb traffic.
            </span>
          </div>
        )}
      </section>
      {(channels.length > 0 || topCountries.length > 0) && (
        <section className="traffic-breakdown-grid">
          {channels.length > 0 && (
            <article className="panel traffic-breakdown-card">
              <div className="panel-header">
                <div>
                  <h2>Traffic channels</h2>
                  <p>Provider-returned share only</p>
                </div>
              </div>
              <dl>
                {channels.map(([channel, share]) => (
                  <div key={channel}>
                    <dt>{humanize(channel)}</dt>
                    <dd>{formatInsightValue(share, "percent")}</dd>
                  </div>
                ))}
              </dl>
            </article>
          )}
          {topCountries.length > 0 && (
            <article className="panel traffic-breakdown-card">
              <div className="panel-header">
                <div>
                  <h2>Top countries</h2>
                  <p>Provider-returned audience distribution</p>
                </div>
              </div>
              <dl>
                {topCountries.map((country, index) => {
                  const countryRecord = isRecord(country) ? country : null;
                  const name = countryRecord
                    ? firstRecordValue(countryRecord, [
                        "country",
                        "name",
                        "country_code",
                      ])
                    : country;
                  const share = countryRecord
                    ? firstRecordValue(countryRecord, [
                        "share",
                        "traffic_share",
                        "percentage",
                      ])
                    : null;
                  return (
                    <div key={`${String(name)}-${index}`}>
                      <dt>{String(name || "Unknown country")}</dt>
                      <dd>{formatInsightValue(share, "percent")}</dd>
                    </div>
                  );
                })}
              </dl>
            </article>
          )}
        </section>
      )}
      {unavailable.length > 0 && (
        <section className="unavailable-metrics-note">
          <AlertCircle size={17} />
          <div>
            <b>Unavailable provider metrics</b>
            <span>{unavailable.map(humanize).join(" · ")}</span>
          </div>
        </section>
      )}
    </div>
  );
}

function looksLikeInsight(value: unknown) {
  if (!isRecord(value)) return false;
  return [
    "status",
    "low",
    "central",
    "high",
    "value",
    "score",
    "confidence_label",
    "evidence",
    "estimator_version",
  ].some((key) => key in value);
}

function sectionItems(value: unknown): unknown[] {
  if (Array.isArray(value)) return value;
  if (!isRecord(value)) return [];
  for (const key of [
    "items",
    "ads",
    "offers",
    "detections",
    "technologies",
    "records",
  ]) {
    if (Array.isArray(value[key])) return value[key] as unknown[];
  }
  return [];
}

function sectionMetricEntries(value: unknown) {
  if (!isRecord(value)) return [] as [string, unknown][];
  const explicit = isRecord(value.metrics)
    ? Object.entries(value.metrics)
    : ([] as [string, unknown][]);
  if (explicit.length) return explicit;
  const reserved = new Set([
    "status",
    "summary",
    "explanation",
    "items",
    "ads",
    "offers",
    "detections",
    "technologies",
    "records",
    "raw_payload",
    "payload",
  ]);
  return Object.entries(value).filter(
    ([key, item]) => !reserved.has(key) && looksLikeInsight(item),
  );
}

function StructuredItem({ value, index }: { value: unknown; index: number }) {
  if (!isRecord(value)) {
    return (
      <article className="structured-item-card">
        <h3>Observed item {index + 1}</h3>
        <p>{String(value)}</p>
      </article>
    );
  }
  const title = firstRecordValue(value, [
    "title",
    "name",
    "headline",
    "product_name",
    "technology",
    "type",
    "category",
  ]);
  const confidence = value.confidence || value.confidence_label;
  const hidden = new Set([
    "id",
    "title",
    "name",
    "headline",
    "product_name",
    "technology",
    "raw_payload",
    "payload",
    "confidence",
    "confidence_label",
  ]);
  const facts = Object.entries(value)
    .filter(
      ([key, item]) =>
        !hidden.has(key) &&
        ["string", "number", "boolean"].includes(typeof item),
    )
    .slice(0, 8);
  return (
    <article className="structured-item-card">
      <header>
        <h3>{title ? String(title) : `Observed item ${index + 1}`}</h3>
        {confidence != null && <ConfidenceBadge value={confidence} />}
      </header>
      {facts.length ? (
        <dl>
          {facts.map(([key, item]) => (
            <div key={key}>
              <dt>{humanize(key)}</dt>
              <dd>
                {typeof item === "string" && /^https?:\/\//i.test(item) ? (
                  <a href={item} target="_blank" rel="noreferrer">
                    Open source <ExternalLink size={12} />
                  </a>
                ) : (
                  String(item)
                )}
              </dd>
            </div>
          ))}
        </dl>
      ) : (
        <p>No supported descriptive fields were returned for this item.</p>
      )}
    </article>
  );
}

function StructuredIntelligenceSection({
  title,
  description,
  value,
  icon: Icon,
}: {
  title: string;
  description: string;
  value: unknown;
  icon: LucideIcon;
}) {
  const record = isRecord(value) ? value : null;
  const status = typeof record?.status === "string" ? record.status : null;
  const summary =
    typeof record?.summary === "string"
      ? record.summary
      : typeof record?.explanation === "string"
        ? record.explanation
        : null;
  const metrics = sectionMetricEntries(value);
  const items = sectionItems(value);
  const hasContent = Boolean(summary || metrics.length || items.length);
  return (
    <div className="report-section-stack">
      <section className="panel structured-section-head">
        <span>
          <Icon size={20} />
        </span>
        <div>
          <h2>{title}</h2>
          <p>{summary || description}</p>
        </div>
        <StatusPill
          status={status || (hasContent ? "observed" : "insufficient")}
        />
      </section>
      {metrics.length > 0 && (
        <section className="report-metric-grid section-metric-grid">
          {metrics.map(([key, metric]) => (
            <InsightMetricCard key={key} label={humanize(key)} value={metric} />
          ))}
        </section>
      )}
      {items.length > 0 && (
        <section className="structured-item-grid">
          {items.map((item, index) => (
            <StructuredItem key={index} value={item} index={index} />
          ))}
        </section>
      )}
      {!hasContent && (
        <EmptyState
          icon={Icon}
          title={`No ${title.toLowerCase()} evidence yet`}
          body="Northstar did not receive enough supported data for this section. It remains blank instead of generating a conclusion."
        />
      )}
    </div>
  );
}

function ReportTechnology({
  technology,
  store,
}: {
  technology: unknown;
  store: IntelligenceStore;
}) {
  const record = isRecord(technology) ? technology : {};
  const detections = Array.isArray(record.detections)
    ? record.detections.filter(isRecord)
    : [];
  const platforms = detections.filter(
    (item) => item.category === "commerce_platform",
  );
  const integrations = detections.filter(
    (item) => item.category !== "commerce_platform",
  );
  const theme = isRecord(store.theme) ? store.theme : null;
  const pagesScanned = typeof record.pages_scanned === "number" ? record.pages_scanned : 0;
  const coverageNotice = typeof record.coverage_notice === "string"
    ? record.coverage_notice
    : "Technology evidence is limited to publicly collected storefront pages.";
  return (
    <div className="report-section-stack">
      <section className="panel technology-summary-head">
        <div>
          <span className="eyebrow">STOREFRONT TECHNOLOGY</span>
          <h2>{integrations.length} apps and integrations observed</h2>
          <p>{coverageNotice}</p>
        </div>
        <div className="technology-coverage-stat">
          <b>{pagesScanned}</b>
          <span>pages inspected</span>
        </div>
      </section>

      <section className="platform-theme-grid">
        <article className="panel platform-theme-card">
          <span>Commerce platform</span>
          <h3>{platforms[0]?.name ? String(platforms[0].name) : humanize(String(store.platform || "unknown"))}</h3>
          <p>Shown as store context and excluded from the app count.</p>
        </article>
        <article className="panel platform-theme-card">
          <span>Shopify theme</span>
          <h3>{theme?.schema_name ? String(theme.schema_name) : theme?.name ? String(theme.name) : "Not identified"}</h3>
          {theme ? (
            <dl>
              {theme.name && <div><dt>Store name</dt><dd>{String(theme.name)}</dd></div>}
              {theme.schema_version && <div><dt>Version</dt><dd>{String(theme.schema_version)}</dd></div>}
              {theme.theme_store_id != null && <div><dt>Theme Store ID</dt><dd>{String(theme.theme_store_id)}</dd></div>}
              {theme.role && <div><dt>Role</dt><dd>{humanize(String(theme.role))}</dd></div>}
            </dl>
          ) : (
            <p>No public Shopify theme object was collected.</p>
          )}
        </article>
      </section>

      {integrations.length ? (
        <section className="technology-app-grid">
          {integrations.map((item, index) => {
            const name = String(item.name || `Integration ${index + 1}`);
            const evidence = Array.isArray(item.evidence) && isRecord(item.evidence[0])
              ? item.evidence[0]
              : null;
            return (
              <article className="panel technology-app-card" key={`${name}-${index}`}>
                <div className="technology-app-icon">
                  <span>{name.charAt(0).toUpperCase()}</span>
                  {typeof item.icon_url === "string" && item.icon_url && (
                    <img
                      src={item.icon_url}
                      alt=""
                      loading="lazy"
                      onError={(event) => { event.currentTarget.style.display = "none"; }}
                    />
                  )}
                </div>
                <div className="technology-app-copy">
                  <header>
                    <div><h3>{name}</h3><span>{humanize(String(item.category || "integration"))}</span></div>
                    <ConfidenceBadge value={item.confidence_label} />
                  </header>
                  <p>{String(item.why_it_matters || "Public storefront integration observed.")}</p>
                  {evidence && (
                    <small>
                      Observed on {humanize(String(evidence.source || "storefront"))}
                      {evidence.observed_at ? ` · ${formatDate(evidence.observed_at)}` : ""}
                    </small>
                  )}
                </div>
              </article>
            );
          })}
        </section>
      ) : (
        <EmptyState icon={Zap} title="No public app evidence yet" body={coverageNotice} />
      )}
    </div>
  );
}

function ReportEvidence({ report }: { report: StoreIntelligenceReportData }) {
  const metrics = report.executive_summary?.metrics || {};
  const versions = Object.values(metrics)
    .map((metric) => asInsight(metric)?.estimator_version)
    .filter((version): version is string => Boolean(version));
  return (
    <div className="report-section-stack">
      <section className="panel evidence-provenance-card">
        <ShieldCheck size={22} />
        <div>
          <h2>Report provenance</h2>
          <p>
            Values are separated into observed facts, provider estimates, and
            derived estimates. A high value does not imply high confidence.
          </p>
        </div>
        <dl>
          <div>
            <dt>Report version</dt>
            <dd>{report.report_version || "Not returned"}</dd>
          </div>
          <div>
            <dt>Calculated</dt>
            <dd>{formatDate(report.generated_at)}</dd>
          </div>
          <div>
            <dt>Estimator versions</dt>
            <dd>
              {versions.length ? [...new Set(versions)].join(", ") : "None"}
            </dd>
          </div>
        </dl>
      </section>
      <StructuredIntelligenceSection
        title="Evidence and assumptions"
        description="No consolidated evidence register was returned. Metric-level evidence is shown below when available."
        value={report.evidence_and_assumptions}
        icon={Database}
      />
      <section className="panel metric-methods-panel">
        <div className="panel-header">
          <div>
            <h2>Headline metric evidence</h2>
            <p>Inspect each estimator independently.</p>
          </div>
        </div>
        <div className="metric-method-list">
          {Object.entries(metrics).map(([key, metric]) => (
            <article key={key}>
              <div>
                <b>{humanize(key)}</b>
                <span>{formatInsightValue(metric)}</span>
              </div>
              <InsightDetails insight={metric} label="Inspect basis" />
            </article>
          ))}
          {!Object.keys(metrics).length && (
            <p className="report-muted-copy">
              No headline estimates have been calculated.
            </p>
          )}
        </div>
      </section>
    </div>
  );
}

function StoreIdentityReview({
  storeId,
  onChanged,
}: {
  storeId: number;
  onChanged: () => void;
}) {
  const [identities, setIdentities] = useState<StoreIdentityCandidate[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [updatingId, setUpdatingId] = useState<number | null>(null);
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError(null);
    apiFetch<StoreIdentityCandidate[]>(
      `/intelligence/stores/${storeId}/identities`,
      { signal: controller.signal },
    )
      .then((rows) => setIdentities(rows))
      .catch((requestError) => {
        if (controller.signal.aborted) return;
        setError(
          requestError instanceof Error
            ? requestError.message
            : "Identity candidates could not be loaded.",
        );
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [storeId, reloadKey]);

  const updateConfirmation = async (
    identity: StoreIdentityCandidate,
    confirmed: boolean,
  ) => {
    setUpdatingId(identity.id);
    setError(null);
    try {
      const updated = await apiFetch<{
        id: number;
        is_confirmed: boolean;
        confirmed_at?: string | null;
      }>(`/intelligence/stores/${storeId}/identities/${identity.id}`, {
        method: "PATCH",
        body: JSON.stringify({ confirmed }),
      });
      setIdentities((current) =>
        current.map((item) =>
          item.id === updated.id
            ? {
                ...item,
                is_confirmed: updated.is_confirmed,
                confirmed_at: updated.confirmed_at,
              }
            : item,
        ),
      );
      onChanged();
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "The identity confirmation could not be saved.",
      );
    } finally {
      setUpdatingId(null);
    }
  };

  return (
    <section className="panel identity-review-panel">
      <div className="panel-header identity-review-header">
        <div>
          <h2>Store identity review</h2>
          <p>
            Confirm only identities that clearly belong to this storefront. A
            confirmed identity can support scoped provider searches and ad matching.
          </p>
        </div>
        <StatusPill
          status={identities.some((identity) => identity.is_confirmed) ? "confirmed" : "review"}
        />
      </div>
      {error && (
        <div className="identity-review-error" role="alert">
          <AlertCircle size={16} />
          <span>{error}</span>
          <button
            className="text-button"
            onClick={() => setReloadKey((value) => value + 1)}
          >
            Retry
          </button>
        </div>
      )}
      {loading ? (
        <div className="identity-review-loading">
          <LoaderCircle className="spin" size={18} />
          Loading identity candidates…
        </div>
      ) : identities.length ? (
        <div className="identity-candidate-grid">
          {identities.map((identity) => {
            const sourceUrl =
              identity.source_url && /^https?:\/\//i.test(identity.source_url)
                ? identity.source_url
                : null;
            const busy = updatingId === identity.id;
            return (
              <article
                className={`identity-candidate-card${identity.is_confirmed ? " confirmed" : ""}`}
                key={identity.id}
              >
                <header>
                  <div>
                    <span className="identity-network">
                      {humanize(identity.identity_type)}
                    </span>
                    <h3>{identity.display_value}</h3>
                  </div>
                  {identity.is_confirmed && (
                    <span className="identity-confirmed-label">
                      <CheckCircle2 size={13} /> Confirmed
                    </span>
                  )}
                </header>
                <dl>
                  <div>
                    <dt>Found via</dt>
                    <dd>{humanize(identity.source_type)}</dd>
                  </div>
                  <div>
                    <dt>Collector confidence</dt>
                    <dd>{Math.round(identity.confidence_score * 100)}%</dd>
                  </div>
                </dl>
                <footer>
                  {sourceUrl && (
                    <button
                      className="text-button"
                      onClick={() => window.open(sourceUrl, "_blank", "noopener")}
                    >
                      Inspect source <ExternalLink size={12} />
                    </button>
                  )}
                  <button
                    className={identity.is_confirmed ? "button secondary" : "button primary"}
                    disabled={updatingId !== null}
                    onClick={() => updateConfirmation(identity, !identity.is_confirmed)}
                  >
                    {busy ? (
                      <LoaderCircle className="spin" size={14} />
                    ) : identity.is_confirmed ? (
                      <X size={14} />
                    ) : (
                      <Check size={14} />
                    )}
                    {busy
                      ? "Saving"
                      : identity.is_confirmed
                        ? "Remove confirmation"
                        : "Confirm identity"}
                  </button>
                </footer>
              </article>
            );
          })}
        </div>
      ) : (
        <div className="identity-review-empty">
          <CircleHelp size={18} />
          <div>
            <b>No identity candidates collected</b>
            <span>
              Rescan after the storefront publishes a brand or Facebook/Instagram
              identity on its homepage.
            </span>
          </div>
        </div>
      )}
    </section>
  );
}

function StoreIntelligenceReport({
  storeId,
  tab,
  onTabChange,
  onBack,
  onScan,
}: {
  storeId: number;
  tab: ReportTab;
  onTabChange: (tab: ReportTab) => void;
  onBack: () => void;
  onScan: () => void;
}) {
  const [report, setReport] = useState<StoreIntelligenceReportData | null>(
    null,
  );
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError(null);
    apiFetch<StoreIntelligenceReportData>(`/intelligence/stores/${storeId}`, {
      signal: controller.signal,
    })
      .then((data) => setReport(data))
      .catch((requestError) => {
        if (controller.signal.aborted) return;
        const message =
          requestError instanceof Error
            ? requestError.message
            : "The intelligence report could not be loaded.";
        setError(
          message.toLowerCase() === "not found" || message.includes("404")
            ? "The scan may still be collecting enough information to create this report."
            : message,
        );
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [storeId, reloadKey]);

  if (loading) {
    return (
      <div className="page-content report-loading-page">
        <LoaderCircle className="spin" size={28} />
        <h2>Building the store intelligence report</h2>
        <p>Loading available evidence and estimates without filling gaps.</p>
      </div>
    );
  }

  if (error || !report) {
    return (
      <div className="page-content">
        <EmptyState
          icon={AlertCircle}
          title="Store report is not available yet"
          body={
            error ||
            "The scan may still be collecting evidence. Retry without submitting another scan."
          }
          action={
            <div className="report-error-actions">
              <button className="button secondary" onClick={onBack}>
                Back to stores
              </button>
              <button
                className="button primary"
                onClick={() => setReloadKey((value) => value + 1)}
              >
                <RefreshCw size={15} />
                Retry report
              </button>
            </div>
          }
        />
      </div>
    );
  }

  const store = report.store || {};
  const reportProducts = Array.isArray(report.products) ? report.products : [];
  const hasRankedProducts = reportProducts.some(
    (product) => !isUnavailableInsight(product.momentum),
  );
  const domain = store.domain || `Store ${storeId}`;
  const brand = store.brand_name || store.name || domain;
  const metadata = [
    store.platform,
    store.primary_category || store.category,
    store.main_country || store.market,
  ].filter((item): item is string => typeof item === "string" && Boolean(item));
  const storeUrl =
    typeof store.url === "string" && /^https?:\/\//i.test(store.url)
      ? store.url
      : store.domain
        ? `https://${store.domain}`
        : null;

  return (
    <div className="page-content store-report-page">
      <button className="report-back-button" onClick={onBack}>
        <ChevronRight size={15} />
        All stores
      </button>
      <PageHeading
        eyebrow="STORE INTELLIGENCE REPORT"
        title={String(brand)}
        subtitle={`${domain}${metadata.length ? ` · ${metadata.join(" · ")}` : ""}`}
        actions={
          <>
            <InvestigationAction entityType="store" entityId={storeId} />
            {storeUrl && (
              <button
                className="button secondary"
                onClick={() => window.open(storeUrl, "_blank", "noopener")}
              >
                <ExternalLink size={15} />
                Open store
              </button>
            )}
            <button className="button primary" onClick={onScan}>
              <RefreshCw size={15} />
              New scan
            </button>
          </>
        }
      />
      <div className="report-meta-strip">
        <div>
          <Database size={15} />
          <span>
            Report {report.report_version || "version not returned"} ·
            calculated {formatDate(report.generated_at)}
          </span>
        </div>
        <ConfidenceBadge value={report.executive_summary?.overall_confidence} />
      </div>
      <nav className="report-tabs" aria-label="Store intelligence sections">
        {reportTabs.map((item) => {
          const Icon = item.icon;
          return (
            <button
              key={item.id}
              className={tab === item.id ? "active" : ""}
              aria-current={tab === item.id ? "page" : undefined}
              onClick={() => onTabChange(item.id)}
            >
              <Icon size={15} />
              {item.label}
            </button>
          );
        })}
      </nav>
      <div className="report-tab-content">
        {tab === "overview" && <ReportOverview report={report} />}
        {tab === "products" && (
          <section className="panel report-ranked-products full-product-report">
            <div className="panel-header">
              <div>
                <h2>
                  {hasRankedProducts
                    ? "Ranked product intelligence"
                    : "Product intelligence — ranking withheld"}
                </h2>
                <p>
                  {hasRankedProducts
                    ? "Scores and classifications remain separate from evidence confidence."
                    : "Every product remains unranked until independent demand evidence passes the publication gate."}
                </p>
              </div>
            </div>
            <IntelligenceProductsTable
              products={reportProducts}
            />
          </section>
        )}
        {tab === "traffic" && <ReportTraffic traffic={report.traffic} />}
        {tab === "ads" && (
          <div className="report-section-stack">
            <StoreIdentityReview
              storeId={storeId}
              onChanged={() => setReloadKey((value) => value + 1)}
            />
            <StructuredIntelligenceSection
              title="Ads and creatives"
              description="No advertising identity or creative evidence was returned for this store."
              value={report.ads}
              icon={Ad}
            />
          </div>
        )}
        {tab === "offers" && (
          <StructuredIntelligenceSection
            title="Offers and funnel"
            description="No normalized offer or landing-page evidence was returned."
            value={report.offers_and_funnel}
            icon={ShoppingBag}
          />
        )}
        {tab === "technology" && (
          <ReportTechnology technology={report.technology} store={store} />
        )}
        {tab === "evidence" && <ReportEvidence report={report} />}
        {tab === "diagnostics" && (
          <div className="diagnostics-report-section">
            <div className="diagnostics-warning">
              <CircleHelp size={17} />
              <span>
                Technical collection details are kept here for debugging and do
                not represent business performance.
              </span>
            </div>
            <StructuredIntelligenceSection
              title="Scan diagnostics"
              description="No scan diagnostics were returned with this report."
              value={report.diagnostics}
              icon={Activity}
            />
          </div>
        )}
      </div>
    </div>
  );
}

function OverviewPage({
  library,
  integrations,
  onScan,
  onNavigate,
  onOpenStore,
}: {
  library: LocalLibraryData;
  integrations: IntegrationStatus | null;
  onScan: () => void;
  onNavigate: (view: View) => void;
  onOpenStore: (storeId: number) => void;
}) {
  return (
    <div className="page-content">
      <PageHeading
        eyebrow="RESEARCH WORKSPACE"
        title="Start with a store. End with a decision."
        subtitle="Northstar combines only available public and provider evidence, then leaves unsupported conclusions blank."
        actions={
          <button className="button primary" onClick={onScan}>
            <Plus size={17} />
            Investigate a store
          </button>
        }
      />
      <section className="research-entry-card">
        <span>
          <Radar size={25} />
        </span>
        <div>
          <h2>Paste a public store URL</h2>
          <p>
            Northstar will build one report around traffic, estimated sales,
            product evidence, ads, offers, technology, and uncertainty.
          </p>
        </div>
        <button className="button primary" onClick={onScan}>
          <Globe2 size={16} />
          Scan store
        </button>
      </section>

      <section className="panel overview-report-list">
        <div className="panel-header">
          <div>
            <h2>Store intelligence reports</h2>
            <p>
              Open a store to see conclusions, evidence, and missing signals.
            </p>
          </div>
          <button className="text-button" onClick={() => onNavigate("stores")}>
            View all stores <ArrowRight size={14} />
          </button>
        </div>
        {library.stores.length ? (
          <div className="overview-report-rows">
            {library.stores.slice(0, 6).map((store) => {
              const traffic = trafficFor(store);
              const visits = traffic?.visits ?? traffic?.total_visits;
              return (
                <button key={store.id} onClick={() => onOpenStore(store.id)}>
                  <span className="live-store-logo">
                    {store.domain.charAt(0).toUpperCase()}
                  </span>
                  <div>
                    <b>{store.domain}</b>
                    <small>
                      {store.platform} · {store.product_count} catalog
                      observations
                    </small>
                  </div>
                  <div>
                    <span>Provider traffic</span>
                    <b>{formatNumber(visits)}</b>
                  </div>
                  <StatusPill status={store.observation_state || "observed"} />
                  <ChevronRight size={16} />
                </button>
              );
            })}
          </div>
        ) : (
          <div className="inline-empty report-inline-empty">
            <Store size={27} />
            <b>No store reports yet</b>
            <span>Scan a public storefront to begin the first report.</span>
            <button className="button primary" onClick={onScan}>
              Investigate a store
            </button>
          </div>
        )}
      </section>

      <section className="evidence-readiness-strip">
        <div>
          <span className="health-source-icon shopify">◈</span>
          <p>
            <b>Storefront evidence</b>
            <small>{library.summary.products} catalog observations</small>
          </p>
          <StatusPill status="active" />
        </div>
        <button onClick={() => onNavigate("ads")}>
          <span className="health-source-icon meta">M</span>
          <p>
            <b>Advertising evidence</b>
            <small>
              {isConfigured(integrations, "meta")
                ? "Meta credential configured"
                : "Meta not connected"}
            </small>
          </p>
          <StatusPill
            status={
              isConfigured(integrations, "meta") ? "configured" : "offline"
            }
          />
        </button>
        <button onClick={() => onNavigate("settings")}>
          <span className="health-source-icon similarweb">S</span>
          <p>
            <b>Traffic evidence</b>
            <small>
              {isConfigured(integrations, "similarweb")
                ? "Similarweb key configured"
                : "Similarweb not connected"}
            </small>
          </p>
          <StatusPill
            status={
              isConfigured(integrations, "similarweb")
                ? "configured"
                : "offline"
            }
          />
        </button>
      </section>
    </div>
  );
}

function ProductTable({
  products,
  onOpen,
}: {
  products: LocalProduct[];
  onOpen?: (product: LocalProduct) => void;
}) {
  if (!products.length)
    return (
      <div className="inline-empty">
        <PackageSearch size={27} />
        <b>No products collected</b>
        <span>Scan a public store or product URL to populate this table.</span>
      </div>
    );
  return (
    <div className="local-product-grid">
      {products.map((product) => (
        <article className="local-product-card" key={product.id}>
          <div className="local-product-card-image">
            {product.image_url ? (
              <img src={product.image_url} alt="" loading="lazy" />
            ) : (
              <ShoppingBag size={22} />
            )}
          </div>
          <div className="local-product-card-body">
            <header>
              <div>
                <b>{product.title}</b>
                <small>{product.store_domain || "Unknown store"}</small>
              </div>
              <StatusPill status="observed" />
            </header>
            <div className="local-product-card-facts">
              <div>
                <span>Observed price</span>
                <b>{formatMoney(product.price_min, product.currency)}</b>
                {product.price_max != null && product.price_max !== product.price_min && (
                  <small>to {formatMoney(product.price_max, product.currency)}</small>
                )}
              </div>
              <div>
                <span>First seen</span>
                <b>{product.first_seen_at ? formatDate(product.first_seen_at) : "Not recorded"}</b>
              </div>
              <div>
                <span>Variants</span>
                <b>{product.variant_count ?? "Unknown"}</b>
              </div>
            </div>
            <footer>
              <small>Catalog presence only; demand is evaluated in the store report.</small>
              <div className="table-row-actions">
                {onOpen && <button className="text-button" onClick={() => onOpen(product)}>Inspect</button>}
                <button
                  className="icon-button"
                  aria-label={`Open ${product.title}`}
                  onClick={() => window.open(product.canonical_url, "_blank", "noopener")}
                >
                  <ExternalLink size={15} />
                </button>
              </div>
            </footer>
          </div>
        </article>
      ))}
    </div>
  );
}

function ProductsPage({
  products,
  onScan,
  onOpen,
}: {
  products: LocalProduct[];
  onScan: () => void;
  onOpen: (product: LocalProduct) => void;
}) {
  const [query, setQuery] = useState("");
  const [storeFilter, setStoreFilter] = useState("");
  const [availabilityFilter, setAvailabilityFilter] = useState("");
  const [minPrice, setMinPrice] = useState("");
  const [maxPrice, setMaxPrice] = useState("");
  const [minVariants, setMinVariants] = useState("");
  const [firstObservedWithin, setFirstObservedWithin] = useState("");
  const [sortBy, setSortBy] = useState("last_seen_desc");
  const [presetName, setPresetName] = useState("");
  const [presets, setPresets] = useState<Array<{ name: string; filters: Record<string, string> }>>(() => {
    try { return JSON.parse(window.localStorage.getItem("northstarProductViews") || "[]"); } catch { return []; }
  });
  const stores = Array.from(new Set(products.map((product) => product.store_domain).filter((value): value is string => Boolean(value)))).sort();
  const filtered = products.filter((product) => {
    const matchesQuery = `${product.title} ${product.store_domain || ""}`
      .toLowerCase()
      .includes(query.toLowerCase());
    const matchesStore = !storeFilter || product.store_domain === storeFilter;
    const matchesAvailability = !availabilityFilter || (availabilityFilter === "available" ? product.available === true : availabilityFilter === "unavailable" ? product.available === false : product.available == null);
    const matchesMinPrice = !minPrice || (product.price_min != null && product.price_min >= Number(minPrice));
    const matchesMaxPrice = !maxPrice || (product.price_min != null && product.price_min <= Number(maxPrice));
    const matchesVariants = !minVariants || (product.variant_count != null && product.variant_count >= Number(minVariants));
    const matchesAge = !firstObservedWithin || (product.first_seen_at != null && Date.now() - Date.parse(product.first_seen_at) <= Number(firstObservedWithin) * 86400000);
    return matchesQuery && matchesStore && matchesAvailability && matchesMinPrice && matchesMaxPrice && matchesVariants && matchesAge;
  }).sort((left, right) => {
    if (sortBy === "first_seen_desc") return (Date.parse(right.first_seen_at || "") || 0) - (Date.parse(left.first_seen_at || "") || 0);
    if (sortBy === "price_asc") return (left.price_min ?? Number.POSITIVE_INFINITY) - (right.price_min ?? Number.POSITIVE_INFINITY);
    if (sortBy === "price_desc") return (right.price_max ?? Number.NEGATIVE_INFINITY) - (left.price_max ?? Number.NEGATIVE_INFINITY);
    if (sortBy === "variants_desc") return (right.variant_count ?? -1) - (left.variant_count ?? -1);
    return (Date.parse(right.last_seen_at || "") || 0) - (Date.parse(left.last_seen_at || "") || 0);
  });
  const exportCsv = () => {
    const safe = (value: unknown) => {
      let text = value == null ? "" : String(value);
      if (/^[=+\-@]/.test(text)) text = `'${text}`;
      return `"${text.replaceAll('"', '""')}"`;
    };
    const header = ["product_id", "title", "store_domain", "canonical_url", "currency", "price_low", "price_high", "available", "variant_count", "first_observed_at", "last_observed_at"];
    const lines = [header.map(safe).join(","), ...filtered.map((product) => [product.id, product.title, product.store_domain, product.canonical_url, product.currency, product.price_min, product.price_max, product.available, product.variant_count, product.first_seen_at, product.last_seen_at].map(safe).join(","))];
    const url = URL.createObjectURL(new Blob([lines.join("\r\n")], { type: "text/csv;charset=utf-8" }));
    const link = document.createElement("a");
    link.href = url;
    link.download = `northstar-observed-products-${new Date().toISOString().slice(0, 10)}.csv`;
    link.click();
    URL.revokeObjectURL(url);
  };
  const resetFilters = () => { setQuery(""); setStoreFilter(""); setAvailabilityFilter(""); setMinPrice(""); setMaxPrice(""); setMinVariants(""); setFirstObservedWithin(""); setSortBy("last_seen_desc"); };
  const savePreset = () => {
    const name = presetName.trim();
    if (!name) return;
    const next = [...presets.filter((preset) => preset.name.toLowerCase() !== name.toLowerCase()), { name, filters: { query, storeFilter, availabilityFilter, minPrice, maxPrice, minVariants, firstObservedWithin, sortBy } }];
    setPresets(next);
    window.localStorage.setItem("northstarProductViews", JSON.stringify(next));
    setPresetName("");
  };
  const applyPreset = (filters: Record<string, string>) => { setQuery(filters.query || ""); setStoreFilter(filters.storeFilter || ""); setAvailabilityFilter(filters.availabilityFilter || ""); setMinPrice(filters.minPrice || ""); setMaxPrice(filters.maxPrice || ""); setMinVariants(filters.minVariants || ""); setFirstObservedWithin(filters.firstObservedWithin || ""); setSortBy(filters.sortBy || "last_seen_desc"); };
  const removePreset = (name: string) => { const next = presets.filter((preset) => preset.name !== name); setPresets(next); window.localStorage.setItem("northstarProductViews", JSON.stringify(next)); };
  return (
    <div className="page-content">
      <PageHeading
        eyebrow="PRODUCT DISCOVERY"
        title="Shopify product explorer"
        subtitle="Search and filter products collected across your Northstar store corpus. These are observed catalog records—not a claim of global demand or sales."
        actions={
          <><button className="button secondary" disabled={!filtered.length} onClick={exportCsv}><Download size={15} />Export {filtered.length} CSV</button><button className="button primary" onClick={onScan}><Plus size={17} />Scan a product</button></>
        }
      />
      <div className="filterbar real-filterbar">
        <div className="filter-search">
          <Search size={16} />
          <input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Search collected products..."
          />
        </div>
        <select value={storeFilter} onChange={(event) => setStoreFilter(event.target.value)} aria-label="Filter products by store"><option value="">All stores</option>{stores.map((store) => <option key={store} value={store}>{store}</option>)}</select>
        <select value={availabilityFilter} onChange={(event) => setAvailabilityFilter(event.target.value)} aria-label="Filter products by availability"><option value="">Any availability</option><option value="available">Available</option><option value="unavailable">Unavailable</option><option value="unknown">Not observed</option></select>
        <input className="filter-number" type="number" min="0" step="1" value={minPrice} onChange={(event) => setMinPrice(event.target.value)} placeholder="Min price" aria-label="Minimum observed price" />
        <input className="filter-number" type="number" min="0" step="1" value={maxPrice} onChange={(event) => setMaxPrice(event.target.value)} placeholder="Max price" aria-label="Maximum observed price" />
        <input className="filter-number" type="number" min="0" step="1" value={minVariants} onChange={(event) => setMinVariants(event.target.value)} placeholder="Min variants" aria-label="Minimum variants" />
        <select value={firstObservedWithin} onChange={(event) => setFirstObservedWithin(event.target.value)} aria-label="Filter by first observation date"><option value="">Any first observation</option><option value="7">First seen within 7 days</option><option value="30">First seen within 30 days</option><option value="90">First seen within 90 days</option></select>
        <select value={sortBy} onChange={(event) => setSortBy(event.target.value)} aria-label="Sort products"><option value="last_seen_desc">Recently updated</option><option value="first_seen_desc">Newest discovered</option><option value="price_asc">Price: low to high</option><option value="price_desc">Price: high to low</option><option value="variants_desc">Most variants</option></select>
        <button className="text-button" onClick={resetFilters}>Reset</button>
        <span className="filter-count">
          {filtered.length} catalog observations
        </span>
      </div>
      <details className="panel product-saved-views">
        <summary>Saved product research views <span>{presets.length}</span></summary>
        <div className="saved-view-create"><input value={presetName} maxLength={80} onChange={(event) => setPresetName(event.target.value)} placeholder="Name the current filter view…" /><button className="button secondary" disabled={!presetName.trim()} onClick={savePreset}><Save size={14} />Save current view</button></div>
        {presets.length ? <div className="saved-view-list">{presets.map((preset) => <div key={preset.name}><button onClick={() => applyPreset(preset.filters)}><Bookmark size={13} />{preset.name}</button><button className="icon-button" aria-label={`Delete ${preset.name}`} onClick={() => removePreset(preset.name)}><X size={13} /></button></div>)}</div> : <small>No saved views yet. Configure filters above, then save them with a useful name.</small>}
      </details>
      <section className="panel local-products-panel">
        <ProductTable products={filtered} onOpen={onOpen} />
      </section>
    </div>
  );
}

function StoresPage({
  stores,
  trafficConfigured,
  onScan,
  onOpenReport,
  onRefreshTraffic,
  onSettings,
  refreshingStoreId,
}: {
  stores: LocalStore[];
  trafficConfigured: boolean;
  onScan: () => void;
  onOpenReport: (storeId: number) => void;
  onRefreshTraffic: (store: LocalStore) => void;
  onSettings: () => void;
  refreshingStoreId: number | null;
}) {
  const [query, setQuery] = useState("");
  const filtered = stores.filter((store) =>
    store.domain.toLowerCase().includes(query.toLowerCase()),
  );
  return (
    <div className="page-content">
      <PageHeading
        eyebrow="STORES & PROVIDER TRAFFIC"
        title="Store records"
        subtitle="Crawler-confirmed storefronts are marked observed; submitted targets remain labeled until a fetch succeeds. Similarweb figures are provider estimates."
        actions={
          <button className="button primary" onClick={onScan}>
            <Plus size={17} />
            Scan a store
          </button>
        }
      />
      {!trafficConfigured && (
        <div className="provider-callout">
          <TrafficCone size={20} />
          <div>
            <b>Traffic data is not connected</b>
            <span>
              Add a Similarweb API key to retrieve real provider rankings and,
              when your plan permits, estimated visits.
            </span>
          </div>
          <button className="button tertiary" onClick={onSettings}>
            <KeyRound size={15} />
            Configure Similarweb
          </button>
        </div>
      )}
      {trafficConfigured && (
        <div className="provider-credit-note">
          <CircleHelp size={15} />
          <span>
            Each previous-month refresh requests visits and global rank and may
            use up to two Similarweb data credits.
          </span>
        </div>
      )}
      <div className="filterbar real-filterbar">
        <div className="filter-search">
          <Search size={16} />
          <input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Search domains..."
          />
        </div>
        <span className="filter-count">{filtered.length} stores</span>
      </div>
      {filtered.length ? (
        <div className="store-live-grid">
          {filtered.map((store) => {
            const traffic = trafficFor(store);
            const visits = traffic?.visits ?? traffic?.total_visits;
            const fetchStatus = traffic?.fetch_status || traffic?.status;
            const period = traffic ? trafficPeriod(traffic) : null;
            const providerIssue = traffic ? trafficIssue(traffic) : null;
            return (
              <article className="panel live-store-card" key={store.id}>
                <header>
                  <span className="live-store-logo">
                    {store.domain.charAt(0).toUpperCase()}
                  </span>
                  <div>
                    <button
                      className="store-report-title"
                      onClick={() => onOpenReport(store.id)}
                    >
                      <h2>{store.domain}</h2>
                      <span>
                        Intelligence report <ChevronRight size={12} />
                      </span>
                    </button>
                    <p>
                      {store.platform} ·{" "}
                      {store.observation_state === "submitted"
                        ? "awaiting a successful storefront fetch"
                        : "public storefront observed"}
                    </p>
                  </div>
                  <button
                    className="icon-button"
                    aria-label={`Open ${store.domain}`}
                    onClick={() =>
                      window.open(
                        `https://${store.domain}`,
                        "_blank",
                        "noopener",
                      )
                    }
                  >
                    <ExternalLink size={15} />
                  </button>
                </header>
                <div className="store-observed-metrics">
                  <div>
                    <span>Collected products</span>
                    <b>{store.product_count}</b>
                    <small>Observed</small>
                  </div>
                  <div>
                    <span>Est. monthly visits</span>
                    <b>{formatNumber(visits)}</b>
                    <small>
                      {visits != null
                        ? "Similarweb estimate"
                        : "No provider data"}
                    </small>
                  </div>
                  <div>
                    <span>Global rank</span>
                    <b>
                      {traffic?.global_rank
                        ? `#${formatNumber(traffic.global_rank)}`
                        : "—"}
                    </b>
                    <small>
                      {traffic?.global_rank ? "Similarweb" : "Not fetched"}
                    </small>
                  </div>
                </div>
                {traffic?.data_notice && (
                  <p className="traffic-data-notice">{traffic.data_notice}</p>
                )}
                <footer>
                  <div
                    className={`traffic-provider-state traffic-${fetchStatus || "none"}`}
                  >
                    {fetchStatus === "success" ? (
                      <CheckCircle2 size={14} />
                    ) : (
                      <AlertCircle size={14} />
                    )}
                    <span>
                      <b>
                        {fetchStatus === "success"
                          ? "Provider snapshot available"
                          : fetchStatus === "partial"
                            ? "Partial provider snapshot"
                            : fetchStatus === "unavailable"
                              ? "Provider metrics unavailable"
                              : "No traffic snapshot"}
                      </b>
                      <small>
                        {traffic
                          ? [
                              period ? `Period ${period}` : null,
                              providerIssue ||
                                `Fetched ${formatDate(traffic.fetched_at)}`,
                            ]
                              .filter(Boolean)
                              .join(" · ")
                          : "Fetch after connecting Similarweb"}
                      </small>
                    </span>
                  </div>
                  <button
                    className="button secondary"
                    disabled={
                      !trafficConfigured || refreshingStoreId === store.id
                    }
                    onClick={() => onRefreshTraffic(store)}
                  >
                    {refreshingStoreId === store.id ? (
                      <LoaderCircle className="spin" size={14} />
                    ) : (
                      <RefreshCw size={14} />
                    )}
                    {refreshingStoreId === store.id
                      ? "Fetching"
                      : "Fetch previous month"}
                  </button>
                </footer>
              </article>
            );
          })}
        </div>
      ) : (
        <EmptyState
          icon={Store}
          title="No stores collected"
          body="Scan a public storefront to create the first observed store record."
          action={
            <button className="button primary" onClick={onScan}>
              Scan a store
            </button>
          }
        />
      )}
    </div>
  );
}

function MetaAdsExplorer({
  ads,
  metaConfigured,
  onSearchMeta,
  onSettings,
  searching,
}: {
  ads: RealAd[];
  metaConfigured: boolean;
  onSearchMeta: (query: string, country: string) => void;
  onSettings: () => void;
  searching: boolean;
}) {
  const [query, setQuery] = useState("");
  const [country, setCountry] = useState("GB");
  const [localQuery, setLocalQuery] = useState("");
  const filtered = ads.filter(
    (ad) =>
      ad.data_provider === "meta_ad_library" &&
      `${ad.advertiser_name || ""} ${ad.ad_text || ""} ${ad.headline || ""}`
        .toLowerCase()
        .includes(localQuery.toLowerCase()),
  );
  return (
    <div className="ad-source-content">
      {!metaConfigured ? (
        <div className="provider-callout meta-callout">
          <Ad size={20} />
          <div>
            <b>Meta Ad Library is not connected</b>
            <span>
              Add an eligible Meta access token. Northstar will not scrape the
              Ad Library website.
            </span>
          </div>
          <button className="button tertiary" onClick={onSettings}>
            <KeyRound size={15} />
            Configure Meta
          </button>
        </div>
      ) : (
        <form
          className="provider-search"
          onSubmit={(event) => {
            event.preventDefault();
            if (query.trim()) onSearchMeta(query.trim(), country);
          }}
        >
          <div>
            <Search size={17} />
            <input
              value={query}
              maxLength={100}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search a brand, product, or keyword in Meta..."
            />
          </div>
          <select
            value={country}
            onChange={(event) => setCountry(event.target.value)}
          >
            <option value="GB">United Kingdom — all ad types</option>
            <option value="DE">Germany — all ad types</option>
            <option value="FR">France — all ad types</option>
            <option value="US">
              United States — political/issue API coverage
            </option>
            <option value="CA">Canada — political/issue API coverage</option>
            <option value="AU">Australia — political/issue API coverage</option>
          </select>
          <button
            className="button primary"
            disabled={searching || !query.trim()}
          >
            {searching ? (
              <>
                <LoaderCircle className="spin" size={15} />
                Searching
              </>
            ) : (
              <>
                <Search size={15} />
                Search Meta
              </>
            )}
          </button>
        </form>
      )}
      <div className="coverage-callout">
        <CircleHelp size={17} />
        <span>
          The official API can automate all ad types delivered in the UK and EU.
          For commercial ads outside that coverage, search Meta’s full active-ad
          library directly.
        </span>
        <button
          className="text-button"
          onClick={() =>
            window.open(
              "https://www.facebook.com/ads/library/",
              "_blank",
              "noopener",
            )
          }
        >
          Search official library <ExternalLink size={13} />
        </button>
      </div>
      <div className="filterbar real-filterbar">
        <div className="filter-search">
          <Search size={16} />
          <input
            value={localQuery}
            onChange={(event) => setLocalQuery(event.target.value)}
            placeholder="Filter imported ads..."
          />
        </div>
        <span className="filter-count">{filtered.length} imported ads</span>
      </div>
      {filtered.length ? (
        <div className="real-ad-grid">
          {filtered.map((ad) => {
            const snapshot = ad.ad_snapshot_url || ad.creative_urls?.[0];
            return (
              <article className="panel real-ad-card" key={ad.id}>
                <header>
                  <span className="real-ad-logo">
                    {(ad.advertiser_name || "M").charAt(0)}
                  </span>
                  <div>
                    <b>{ad.advertiser_name || "Unknown advertiser"}</b>
                    <small>
                      {ad.platform} · Meta delivery start{" "}
                      {ad.delivery_start_time
                        ? formatDate(ad.delivery_start_time)
                        : "not returned"}
                    </small>
                  </div>
                </header>
                <div className="real-ad-copy">
                  {ad.headline && <h3>{ad.headline}</h3>}
                  <p>
                    {ad.ad_text ||
                      "Meta did not return ad body text for this record."}
                  </p>
                </div>
                <div className="real-ad-meta">
                  <span>
                    Creative format <b>{humanize(ad.creative_type)}</b>
                  </span>
                  <span>
                    Publisher platforms{" "}
                    <b>
                      {ad.publisher_platforms?.length
                        ? ad.publisher_platforms.map(humanize).join(", ")
                        : "Not returned"}
                    </b>
                  </span>
                  <span>
                    Delivery start{" "}
                    <b>
                      {ad.delivery_start_time
                        ? formatDate(ad.delivery_start_time)
                        : "Not returned"}
                    </b>
                  </span>
                  <span>
                    Delivery stop{" "}
                    <b>
                      {ad.delivery_stop_time
                        ? formatDate(ad.delivery_stop_time)
                        : "Not returned"}
                    </b>
                  </span>
                </div>
                <footer>
                  {ad.landing_url && (
                    <button
                      className="text-button"
                      onClick={() =>
                        window.open(ad.landing_url, "_blank", "noopener")
                      }
                    >
                      Landing page <ExternalLink size={13} />
                    </button>
                  )}
                  {snapshot && (
                    <button
                      className="button secondary"
                      onClick={() =>
                        window.open(snapshot, "_blank", "noopener")
                      }
                    >
                      <Eye size={14} />
                      View Meta snapshot
                    </button>
                  )}
                </footer>
              </article>
            );
          })}
        </div>
      ) : (
        <EmptyState
          icon={Ad}
          title="No Meta ads imported"
          body={
            metaConfigured
              ? "Run a Meta search above. Results returned by the official API will appear here."
              : "Configure an eligible Meta access token to import real Ad Library records."
          }
          action={
            !metaConfigured ? (
              <button className="button primary" onClick={onSettings}>
                Configure Meta
              </button>
            ) : undefined
          }
        />
      )}
    </div>
  );
}

function formatAdMetric(metric: AdMetricData) {
  if (metric.value_kind === "range") {
    return `${metric.range_low ?? "?"}–${metric.range_high ?? "?"}${metric.unit ? ` ${metric.unit}` : ""}`;
  }
  const value = metric.value_numeric ?? metric.value_text;
  return `${value ?? "Unavailable"}${metric.unit && metric.value_numeric != null ? ` ${metric.unit}` : ""}`;
}

function AdAnalyticsDrawer({ ad, onClose }: { ad: RealAd; onClose: () => void }) {
  const [analytics, setAnalytics] = useState<AdAnalyticsData | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    apiFetch<AdAnalyticsData>(`/ads/${ad.id}/analytics`)
      .then((data) => {
        if (active) setAnalytics(data);
      })
      .catch((requestError) => {
        if (active) {
          setError(
            requestError instanceof Error
              ? requestError.message
              : "Ad analytics could not be loaded.",
          );
        }
      });
    return () => {
      active = false;
    };
  }, [ad.id]);

  useEffect(() => {
    const escape = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", escape);
    return () => window.removeEventListener("keydown", escape);
  }, [onClose]);

  return (
    <div className="drawer-layer">
      <button className="drawer-scrim" onClick={onClose} aria-label="Close ad analytics" />
      <aside className="product-drawer ad-analytics-drawer" role="dialog" aria-modal="true">
        <header>
          <button className="icon-button" onClick={onClose} aria-label="Close ad analytics">
            <X size={18} />
          </button>
          <span>Ad analytics</span>
          <StatusPill status={ad.data_provider} />
        </header>
        <div className="ad-analytics-content">
          <div className="ad-analytics-title">
            <span className="real-ad-logo">{(ad.advertiser_name || "?").charAt(0)}</span>
            <div>
              <h2>{ad.headline || ad.advertiser_name || `Ad ${ad.id}`}</h2>
              <p>{humanize(ad.platform)} · {humanize(ad.source_type)}</p>
            </div>
          </div>
          {!analytics && !error && (
            <div className="identity-review-loading"><LoaderCircle className="spin" size={18} />Loading analytics…</div>
          )}
          {error && <div className="ad-search-error"><AlertCircle size={16} />{error}</div>}
          {analytics && (
            <>
              <section>
                <div className="analytics-section-head">
                  <div>
                    <h3>Source-reported metrics</h3>
                    <p>Values remain exact, rounded, ranged, percentile, or classified as supplied.</p>
                  </div>
                  <StatusPill status={analytics.metrics.length ? "available" : "insufficient"} />
                </div>
                {analytics.metrics.length ? (
                  <div className="ad-analytics-metric-grid">
                    {analytics.metrics.map((metric) => (
                      <article key={metric.id}>
                        <span>{humanize(metric.metric_key)}</span>
                        <strong>{formatAdMetric(metric)}</strong>
                        <small>
                          {humanize(metric.value_kind)} · {humanize(metric.provider)}
                          {metric.geography ? ` · ${metric.geography}` : ""}
                        </small>
                      </article>
                    ))}
                  </div>
                ) : (
                  <p className="analytics-empty-copy">No public performance metric was saved with this ad.</p>
                )}
              </section>

              <section>
                <div className="analytics-section-head">
                  <div>
                    <h3>Northstar and provider observations</h3>
                    <p>Collection and delivery facts are not treated as performance.</p>
                  </div>
                </div>
                <div className="analytics-observation-list">
                  {analytics.observed_signals.map((signal) => (
                    <article key={signal.metric_key}>
                      <div>
                        <b>{humanize(signal.metric_key)}</b>
                        <span>
                          {signal.value_kind === "timestamp"
                            ? formatDate(String(signal.value))
                            : `${String(signal.value)}${signal.unit ? ` ${signal.unit}` : ""}`}
                        </span>
                      </div>
                      <p>{signal.explanation}</p>
                    </article>
                  ))}
                </div>
              </section>

              <details className="analytics-unavailable">
                <summary>{analytics.unavailable_metrics.length} unavailable competitor metrics</summary>
                <div>
                  {analytics.unavailable_metrics.map((metric) => (
                    <p key={metric.metric_key}>
                      <b>{humanize(metric.metric_key)}</b>
                      <span>{metric.reason}</span>
                    </p>
                  ))}
                </div>
              </details>
              <div className="coverage-callout"><CircleHelp size={17} /><span>{analytics.data_notice}</span></div>
            </>
          )}
        </div>
      </aside>
    </div>
  );
}

function AdAutopsyPage({
  adId,
  onBack,
  onOpenAd,
  onOpenStore,
  onInvestigate,
}: {
  adId: number;
  onBack: () => void;
  onOpenAd: (id: number) => void;
  onOpenStore: (id: number) => void;
  onInvestigate: (url: string) => void;
}) {
  const [data, setData] = useState<AdAutopsyData | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    setData(null);
    setError(null);
    apiFetch<AdAutopsyData>(`/ads/${adId}/autopsy`)
      .then((result) => active && setData(result))
      .catch((requestError) =>
        active && setError(requestError instanceof Error ? requestError.message : "Ad Autopsy could not be loaded."),
      );
    return () => { active = false; };
  }, [adId]);

  if (!data && !error) {
    return <div className="page-content"><div className="identity-review-loading"><LoaderCircle className="spin" size={18} />Loading Ad Autopsy…</div></div>;
  }
  if (error || !data) {
    return <div className="page-content"><button className="text-button" onClick={onBack}><ArrowLeft size={14} />Back to ads</button><EmptyState icon={AlertCircle} title="Ad Autopsy unavailable" body={error || "This ad could not be loaded."} /></div>;
  }

  const { ad, analytics } = data;
  const creative = ad.creative_urls?.[0];
  const investigateUrl = ad.landing_url || data.landing_pages[0]?.url;
  const captureMetadata = ad.provider_metadata?.capture as {
    adapter_id?: string;
    adapter_version?: string;
    confidence?: string;
    warnings?: string[];
  } | undefined;
  return (
    <div className="page-content ad-autopsy-page">
      <button className="text-button ad-autopsy-back" onClick={onBack}><ArrowLeft size={14} />Back to ad library</button>
      <section className="panel ad-autopsy-hero">
        <div className="ad-autopsy-heading">
          <span className="real-ad-logo">{(ad.advertiser_name || "?").charAt(0)}</span>
          <div>
            <span className="eyebrow">AD AUTOPSY · {humanize(ad.platform)}</span>
            <h1>{ad.headline || ad.advertiser_name || `Ad ${ad.id}`}</h1>
            <p>{ad.advertiser_name || "Unknown advertiser"} · {humanize(ad.data_provider)} · {humanize(ad.source_type)}</p>
          </div>
        </div>
        <div className={`ad-autopsy-conclusion ${data.conclusion.status}`}>
          <StatusPill status={data.conclusion.status} />
          <h2>{data.conclusion.label}</h2>
          <p>{data.conclusion.explanation}</p>
          <small>{data.conclusion.next_step}</small>
        </div>
      </section>

      <div className="ad-autopsy-grid">
        <section className="panel ad-autopsy-creative">
          <div className="analytics-section-head"><div><h2>Creative & copy</h2><p>Saved public evidence, not a performance claim.</p></div><StatusPill status={ad.creative_type} /></div>
          {creative && /\.(png|jpe?g|webp|gif)(\?|$)/i.test(creative) && <img src={creative} alt="Saved ad creative" />}
          <h3>{ad.headline || "No headline saved"}</h3>
          <p className="ad-autopsy-copy">{ad.ad_text || "No ad copy was saved with this record."}</p>
          <div className="creative-analysis-state">
            <div><span>Saved media</span><StatusPill status={data.creative_analysis.media_state} /></div>
            <div><span>Audio transcript</span><StatusPill status={data.creative_analysis.transcript_status} /></div>
            <div><span>On-screen OCR</span><StatusPill status={data.creative_analysis.ocr_status} /></div>
            <p><CircleHelp size={15} />{data.creative_analysis.notice}</p>
          </div>
          <div className="ad-autopsy-actions">
            <InvestigationAction entityType="ad" entityId={ad.id} />
            {(ad.source_url || ad.ad_snapshot_url) && <button className="button secondary" onClick={() => window.open(ad.source_url || ad.ad_snapshot_url, "_blank", "noopener")}><ExternalLink size={14} />Source record</button>}
            {creative && <button className="button secondary" onClick={() => window.open(creative, "_blank", "noopener")}><Eye size={14} />Creative</button>}
            {investigateUrl && <button className="button primary" onClick={() => onInvestigate(investigateUrl)}><Radar size={14} />Investigate landing page</button>}
          </div>
        </section>

        <section className="panel">
          <div className="analytics-section-head"><div><h2>Provenance & delivery</h2><p>Provider dates remain distinct from Northstar observation dates.</p></div></div>
          <div className="ad-autopsy-facts">
            <span>Provider <b>{humanize(ad.data_provider)}</b></span>
            <span>Northstar first saved <b>{formatDate(ad.first_seen_at)}</b></span>
            <span>Delivery start <b>{ad.delivery_start_time ? formatDate(ad.delivery_start_time) : "Not returned"}</b></span>
            <span>Delivery stop <b>{ad.delivery_stop_time ? formatDate(ad.delivery_stop_time) : "Not returned"}</b></span>
            <span>CTA <b>{ad.cta || "Not saved"}</b></span>
            <span>Publisher platforms <b>{ad.publisher_platforms?.length ? ad.publisher_platforms.map(humanize).join(", ") : "Not returned"}</b></span>
            <span>Capture adapter <b>{captureMetadata?.adapter_id ? `${humanize(captureMetadata.adapter_id)} · ${captureMetadata.adapter_version || "version unknown"}` : "Not recorded"}</b></span>
            <span>Capture confidence <b>{captureMetadata?.confidence ? humanize(captureMetadata.confidence) : "Not recorded"}</b></span>
          </div>
          {captureMetadata?.warnings?.length ? <div className="capture-provenance-warnings"><AlertCircle size={15} /><div><b>Capture warnings</b>{captureMetadata.warnings.map((warning) => <span key={warning}>{warning}</span>)}</div></div> : null}
        </section>
      </div>

      <section className="panel ad-autopsy-section">
        <div className="analytics-section-head"><div><h2>Source-scoped analytics</h2><p>Exact, rounded, ranged, percentile, and unavailable values stay structurally distinct.</p></div><StatusPill status={analytics.metrics.length ? "available" : "insufficient"} /></div>
        {analytics.metrics.length ? <div className="ad-analytics-metric-grid">{analytics.metrics.map((metric) => <article key={metric.id}><span>{humanize(metric.metric_key)}</span><strong>{formatAdMetric(metric)}</strong><small>{humanize(metric.value_kind)} · {humanize(metric.provider)}{metric.geography ? ` · ${metric.geography}` : ""}</small></article>)}</div> : <p className="analytics-empty-copy">No public performance metrics were saved for this ad.</p>}
        <details className="analytics-unavailable"><summary>{analytics.unavailable_metrics.length} unavailable competitor metrics</summary><div>{analytics.unavailable_metrics.map((metric) => <p key={metric.metric_key}><b>{humanize(metric.metric_key)}</b><span>{metric.reason}</span></p>)}</div></details>
      </section>

      <section className="panel ad-autopsy-section">
        <div className="analytics-section-head"><div><h2>Landing path</h2><p>Collection state and product associations from stored evidence.</p></div><StatusPill status={data.products.length ? "resolved" : data.landing_pages.length ? "partial" : "not collected"} /></div>
        {data.store && <button className="ad-autopsy-store" onClick={() => onOpenStore(data.store!.id)}><Store size={17} /><span><b>{data.store.domain}</b><small>{humanize(data.store.platform)} · open intelligence report</small></span><ChevronRight size={16} /></button>}
        {data.landing_pages.length ? <div className="landing-path-list">{data.landing_pages.map((landing) => <article key={landing.source_url_id}><div><b>{landing.final_url || landing.url}</b><span>{humanize(landing.fetch_status || "queued")} {landing.last_http_status ? `· HTTP ${landing.last_http_status}` : ""}</span></div><small>{landing.snapshot_fetched_at ? `Snapshot ${formatDate(landing.snapshot_fetched_at)}` : "No landing snapshot collected yet"}</small></article>)}</div> : <p className="analytics-empty-copy">No landing collection record exists yet. Use Investigate landing page to create one.</p>}
        {data.products.length > 0 && <div className="autopsy-product-list">{data.products.map((product) => <button key={product.id} onClick={() => window.open(product.canonical_url, "_blank", "noopener")}><PackageSearch size={16} /><span><b>{product.title}</b><small>{product.store_domain}</small></span><ExternalLink size={14} /></button>)}</div>}
      </section>

      <section className="panel ad-autopsy-section">
        <div className="analytics-section-head"><div><h2>Related saved ads</h2><p>Matched only by stored provider, advertiser, or landing evidence.</p></div><span className="filter-count">{data.related_ads.length}</span></div>
        {data.related_ads.length ? <div className="related-ad-list">{data.related_ads.map((item) => <button key={item.ad.id} onClick={() => onOpenAd(item.ad.id)}><span><b>{item.ad.headline || item.ad.advertiser_name || `Ad ${item.ad.id}`}</b><small>{item.reasons.join(" · ")}</small></span><ChevronRight size={16} /></button>)}</div> : <p className="analytics-empty-copy">No related saved ads were found in your private corpus.</p>}
      </section>
      <div className="coverage-callout"><CircleHelp size={17} /><span>{analytics.data_notice}</span></div>
    </div>
  );
}

function OwnAdLibrary({
  ads,
  onImported,
  onOpenAd,
}: {
  ads: RealAd[];
  onImported: () => Promise<void>;
  onOpenAd: (id: number) => void;
}) {
  const [importOpen, setImportOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState("");
  const [libraryPlatform, setLibraryPlatform] = useState("");
  const [libraryProvider, setLibraryProvider] = useState("");
  const [libraryFormat, setLibraryFormat] = useState("");
  const [librarySort, setLibrarySort] = useState("newest");
  const [advertiserFilter, setAdvertiserFilter] = useState("");
  const [domainFilter, setDomainFilter] = useState("");
  const [metricFilter, setMetricFilter] = useState("");
  const [geographyFilter, setGeographyFilter] = useState("");
  const [observedWithin, setObservedWithin] = useState("");
  const [facets, setFacets] = useState<AdLibraryFacets | null>(null);
  const [platform, setPlatform] = useState("meta");
  const [sourceUrl, setSourceUrl] = useState("");
  const [advertiser, setAdvertiser] = useState("");
  const [headline, setHeadline] = useState("");
  const [adText, setAdText] = useState("");
  const [creativeType, setCreativeType] = useState("unknown");
  const [creativeUrl, setCreativeUrl] = useState("");
  const [landingUrl, setLandingUrl] = useState("");
  const [cta, setCta] = useState("");
  const [metricGeography, setMetricGeography] = useState("");
  const [visibleMetrics, setVisibleMetrics] = useState({
    impressions: "",
    reach: "",
    likes: "",
    comments: "",
    shares: "",
    ctr: "",
  });
  const [selectedAd, setSelectedAd] = useState<RealAd | null>(null);
  const providers = Array.from(new Set(ads.map((ad) => ad.data_provider))).sort();
  const advertisers = Array.from(new Set(ads.map((ad) => ad.advertiser_name).filter((value): value is string => Boolean(value)))).sort();
  const landingDomains = Array.from(new Set(ads.map((ad) => { try { return ad.landing_url ? new URL(ad.landing_url).hostname.replace(/^www\./, "") : null; } catch { return null; } }).filter((value): value is string => Boolean(value)))).sort();
  useEffect(() => {
    apiFetch<AdLibraryFacets>("/ads/facets").then(setFacets).catch(() => undefined);
  }, [ads.length]);
  const filtered = ads
    .filter((ad) =>
      `${ad.advertiser_name || ""} ${ad.headline || ""} ${ad.ad_text || ""} ${ad.landing_url || ""}`
        .toLowerCase()
        .includes(filter.toLowerCase()),
    )
    .filter((ad) => !libraryPlatform || ad.platform === libraryPlatform)
    .filter((ad) => !libraryProvider || ad.data_provider === libraryProvider)
    .filter((ad) => !libraryFormat || ad.creative_type === libraryFormat)
    .filter((ad) => !advertiserFilter || ad.advertiser_name === advertiserFilter)
    .filter((ad) => {
      if (!domainFilter) return true;
      try { return Boolean(ad.landing_url && new URL(ad.landing_url).hostname.replace(/^www\./, "") === domainFilter); } catch { return false; }
    })
    .filter((ad) => !metricFilter || (facets?.metric_keys_by_ad[String(ad.id)] || []).includes(metricFilter))
    .filter((ad) => !geographyFilter || (facets?.geographies_by_ad[String(ad.id)] || []).includes(geographyFilter))
    .filter((ad) => !observedWithin || Date.now() - Date.parse(ad.last_seen_at) <= Number(observedWithin) * 86400000)
    .sort((left, right) => {
      if (librarySort === "oldest") return Date.parse(left.first_seen_at) - Date.parse(right.first_seen_at);
      if (librarySort === "recently_observed") return Date.parse(right.last_seen_at) - Date.parse(left.last_seen_at);
      if (librarySort === "delivery_duration") {
        const duration = (ad: RealAd) => ad.delivery_start_time && ad.delivery_stop_time ? Date.parse(ad.delivery_stop_time) - Date.parse(ad.delivery_start_time) : -1;
        return duration(right) - duration(left);
      }
      return Date.parse(right.first_seen_at) - Date.parse(left.first_seen_at);
    });

  const clearForm = () => {
    setSourceUrl("");
    setAdvertiser("");
    setHeadline("");
    setAdText("");
    setCreativeType("unknown");
    setCreativeUrl("");
    setLandingUrl("");
    setCta("");
    setMetricGeography("");
    setVisibleMetrics({ impressions: "", reach: "", likes: "", comments: "", shares: "", ctr: "" });
  };

  return (
    <div className="own-ad-library">
      <section className="panel own-library-head">
        <div>
          <h2>Northstar ad library</h2>
          <p>
            Your durable research collection. Official Meta imports and public ads
            you save yourself retain their exact provider and source provenance.
          </p>
        </div>
        <button className="button primary" onClick={() => setImportOpen((open) => !open)}>
          {importOpen ? <X size={15} /> : <Plus size={15} />}
          {importOpen ? "Close import" : "Save public ad"}
        </button>
      </section>

      {importOpen && (
        <form
          className="panel manual-ad-form"
          onSubmit={async (event) => {
            event.preventDefault();
            setSaving(true);
            setError(null);
            try {
              await apiFetch<RealAd>("/ingest/ad", {
                method: "POST",
                body: JSON.stringify({
                  platform,
                  source_url: sourceUrl || null,
                  advertiser_name: advertiser || null,
                  headline: headline || null,
                  ad_text: adText || null,
                  creative_type: creativeType,
                  creative_urls: creativeUrl ? [creativeUrl] : null,
                  landing_url: landingUrl || null,
                  cta: cta || null,
                  metrics: Object.entries(visibleMetrics)
                    .filter(([, value]) => value.trim())
                    .map(([metricKey, value]) => ({
                      metric_key: metricKey,
                      value_kind:
                        metricKey === "ctr" && /(top|percentile)/i.test(value)
                          ? "percentile"
                          : "reported_value",
                      value_text: value.trim(),
                      unit: metricKey === "ctr" ? "provider_reported_ctr" : "count",
                      provider:
                        platform === "tiktok"
                          ? "tiktok_creative_center"
                          : platform === "google"
                            ? "google_ads_transparency"
                            : platform === "meta"
                              ? "meta_ad_library"
                              : "manual_public_source",
                      source_type: "manual_public_capture",
                      geography: metricGeography || null,
                    })),
                }),
              });
              clearForm();
              setImportOpen(false);
              await onImported();
            } catch (requestError) {
              setError(
                requestError instanceof Error
                  ? requestError.message
                  : "The public ad could not be saved.",
              );
            } finally {
              setSaving(false);
            }
          }}
        >
          <div className="manual-ad-form-head">
            <div>
              <h3>Save an ad you found</h3>
              <p>
                Copy the public ad/library URL and any visible evidence. Northstar
                does not log in to or scrape the source platform.
              </p>
            </div>
            <StatusPill status="manual public import" />
          </div>
          <div className="manual-ad-fields">
            <label>
              Platform
              <select value={platform} onChange={(event) => setPlatform(event.target.value)}>
                <option value="meta">Meta</option>
                <option value="tiktok">TikTok</option>
                <option value="google">Google</option>
                <option value="manual">Other</option>
              </select>
            </label>
            <label className="wide">
              Public source URL
              <input
                type="url"
                value={sourceUrl}
                onChange={(event) => setSourceUrl(event.target.value)}
                placeholder="https://www.facebook.com/ads/library/?id=…"
              />
            </label>
            <label>
              Advertiser
              <input value={advertiser} onChange={(event) => setAdvertiser(event.target.value)} />
            </label>
            <label>
              Creative format
              <select value={creativeType} onChange={(event) => setCreativeType(event.target.value)}>
                <option value="unknown">Unknown</option>
                <option value="video">Video</option>
                <option value="image">Image</option>
                <option value="carousel">Carousel</option>
              </select>
            </label>
            <label className="wide">
              Headline
              <input value={headline} onChange={(event) => setHeadline(event.target.value)} />
            </label>
            <label className="full">
              Ad copy
              <textarea value={adText} onChange={(event) => setAdText(event.target.value)} rows={3} />
            </label>
            <label className="wide">
              Creative/media URL
              <input type="url" value={creativeUrl} onChange={(event) => setCreativeUrl(event.target.value)} />
            </label>
            <label className="wide">
              Landing-page URL
              <input type="url" value={landingUrl} onChange={(event) => setLandingUrl(event.target.value)} />
            </label>
            <label>
              CTA
              <input value={cta} onChange={(event) => setCta(event.target.value)} placeholder="Shop now" />
            </label>
            <div className="manual-metric-fields full">
              <div>
                <h4>Visible analytics (optional)</h4>
                <p>Copy only what the public source displays. Values such as “34K” or “Top 18%” remain reported text.</p>
              </div>
              {Object.entries(visibleMetrics).map(([key, value]) => (
                <label key={key}>
                  {humanize(key)}
                  <input
                    value={value}
                    onChange={(event) =>
                      setVisibleMetrics((current) => ({ ...current, [key]: event.target.value }))
                    }
                    placeholder={key === "ctr" ? "Top 18%" : "34K"}
                  />
                </label>
              ))}
              <label>
                Geography
                <input value={metricGeography} onChange={(event) => setMetricGeography(event.target.value)} placeholder="US, EU…" />
              </label>
            </div>
          </div>
          {error && <div className="ad-search-error"><AlertCircle size={15} />{error}</div>}
          <footer>
            <small>At least one source, creative, or landing URL is required.</small>
            <button
              className="button primary"
              disabled={saving || (!sourceUrl && !creativeUrl && !landingUrl)}
            >
              {saving ? <LoaderCircle className="spin" size={15} /> : <Check size={15} />}
              {saving ? "Saving" : "Save to Northstar"}
            </button>
          </footer>
        </form>
      )}

      <div className="filterbar real-filterbar">
        <div className="filter-search">
          <Search size={16} />
          <input value={filter} onChange={(event) => setFilter(event.target.value)} placeholder="Search your saved ads…" />
        </div>
        <select value={libraryPlatform} onChange={(event) => setLibraryPlatform(event.target.value)} aria-label="Filter by platform">
          <option value="">All platforms</option>
          {Array.from(new Set(ads.map((ad) => ad.platform))).sort().map((value) => <option key={value} value={value}>{humanize(value)}</option>)}
        </select>
        <select value={libraryProvider} onChange={(event) => setLibraryProvider(event.target.value)} aria-label="Filter by provider">
          <option value="">All providers</option>
          {providers.map((value) => <option key={value} value={value}>{humanize(value)}</option>)}
        </select>
        <select value={libraryFormat} onChange={(event) => setLibraryFormat(event.target.value)} aria-label="Filter by creative format">
          <option value="">All formats</option>
          {Array.from(new Set(ads.map((ad) => ad.creative_type))).sort().map((value) => <option key={value} value={value}>{humanize(value)}</option>)}
        </select>
        <select value={librarySort} onChange={(event) => setLibrarySort(event.target.value)} aria-label="Order saved ads">
          <option value="newest">Newest saved</option>
          <option value="recently_observed">Recently observed</option>
          <option value="oldest">Oldest saved</option>
          <option value="delivery_duration">Longest completed delivery</option>
        </select>
        <span className="filter-count">{filtered.length} durable ads</span>
      </div>
      <details className="panel ad-library-advanced">
        <summary>Advanced private-corpus filters</summary>
        <div>
          <label>Advertiser<select value={advertiserFilter} onChange={(event) => setAdvertiserFilter(event.target.value)}><option value="">All advertisers</option>{advertisers.map((value) => <option key={value} value={value}>{value}</option>)}</select></label>
          <label>Landing domain<select value={domainFilter} onChange={(event) => setDomainFilter(event.target.value)}><option value="">All landing domains</option>{landingDomains.map((value) => <option key={value} value={value}>{value}</option>)}</select></label>
          <label>Saved metric<select value={metricFilter} onChange={(event) => setMetricFilter(event.target.value)}><option value="">Any metric coverage</option>{facets?.metric_keys.map((value) => <option key={value} value={value}>{humanize(value)}</option>)}</select></label>
          <label>Metric geography<select value={geographyFilter} onChange={(event) => setGeographyFilter(event.target.value)}><option value="">Any geography</option>{facets?.geographies.map((value) => <option key={value} value={value}>{value}</option>)}</select></label>
          <label>Last observed<select value={observedWithin} onChange={(event) => setObservedWithin(event.target.value)}><option value="">Any date</option><option value="7">Within 7 days</option><option value="30">Within 30 days</option><option value="90">Within 90 days</option></select></label>
          <button className="text-button" onClick={() => { setAdvertiserFilter(""); setDomainFilter(""); setMetricFilter(""); setGeographyFilter(""); setObservedWithin(""); }}>Reset advanced</button>
        </div>
        <small>{facets?.data_notice || "Loading saved metric facets…"}</small>
      </details>

      {filtered.length ? (
        <div className="real-ad-grid">
          {filtered.map((ad) => {
            const creative = ad.creative_urls?.[0];
            return (
              <article className="panel real-ad-card saved-ad-card" key={ad.id}>
                <header>
                  <span className="real-ad-logo">{(ad.advertiser_name || "?").charAt(0)}</span>
                  <div>
                    <b>{ad.advertiser_name || "Unknown advertiser"}</b>
                    <small>{humanize(ad.platform)} · {humanize(ad.data_provider)}</small>
                  </div>
                  <StatusPill status={ad.source_type} />
                </header>
                <div className="real-ad-copy">
                  {ad.headline && <h3>{ad.headline}</h3>}
                  <p>{ad.ad_text || "No ad copy was saved with this record."}</p>
                </div>
                <div className="saved-ad-provenance">
                  <span>Source <b>{humanize(ad.source_type)}</b></span>
                  <span>Saved <b>{formatDate(ad.first_seen_at)}</b></span>
                </div>
                <footer>
                  {(ad.source_url || ad.ad_snapshot_url) && (
                    <button className="text-button" onClick={() => window.open(ad.source_url || ad.ad_snapshot_url, "_blank", "noopener")}>
                      Source record <ExternalLink size={12} />
                    </button>
                  )}
                  {(creative || ad.landing_url) && (
                    <button className="button secondary" onClick={() => window.open(creative || ad.landing_url, "_blank", "noopener")}>
                      <Eye size={14} /> Open evidence
                    </button>
                  )}
                  <button className="button secondary" onClick={() => setSelectedAd(ad)}>
                    <Gauge size={14} /> Analytics
                  </button>
                  <button className="button primary" onClick={() => onOpenAd(ad.id)}>
                    <Search size={14} /> Autopsy
                  </button>
                </footer>
              </article>
            );
          })}
        </div>
      ) : (
        <EmptyState
          icon={Ad}
          title="Your ad library is empty"
          body="Save a public ad you find or import records through the official Meta API."
          action={<button className="button primary" onClick={() => setImportOpen(true)}>Save public ad</button>}
        />
      )}
      {selectedAd && <AdAnalyticsDrawer ad={selectedAd} onClose={() => setSelectedAd(null)} />}
    </div>
  );
}

function GetHookdExplorer({
  configured,
  onSettings,
}: {
  configured: boolean;
  onSettings: () => void;
}) {
  const [query, setQuery] = useState("");
  const [platform, setPlatform] = useState("");
  const [status, setStatus] = useState("active");
  const [adFormat, setAdFormat] = useState("");
  const [minimumDays, setMinimumDays] = useState("");
  const [searching, setSearching] = useState(false);
  const [result, setResult] = useState<GetHookdSearchResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const search = async () => {
    if (!query.trim()) return;
    setSearching(true);
    setError(null);
    try {
      const data = await apiFetch<GetHookdSearchResult>("/ads/gethookd/search", {
        method: "POST",
        body: JSON.stringify({
          query: query.trim(),
          limit: 30,
          platform: platform || null,
          status: status || null,
          ad_format: adFormat || null,
          minimum_days_active: minimumDays ? Number(minimumDays) : null,
          sort_column: "days_active",
          sort_direction: "desc",
        }),
      });
      setResult(data);
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "GetHookd search could not be completed.",
      );
    } finally {
      setSearching(false);
    }
  };

  if (!configured) {
    return (
      <div className="provider-callout gethookd-callout">
        <Search size={20} />
        <div>
          <b>GetHookd ad search is not connected</b>
          <span>
            Add a GetHookd public API token to search its ad library from Northstar.
            Provider search results consume GetHookd credits.
          </span>
        </div>
        <button className="button tertiary" onClick={onSettings}>
          <KeyRound size={15} />
          Configure GetHookd
        </button>
      </div>
    );
  }

  return (
    <div className="gethookd-explorer">
      <form
        className="ad-discovery-search panel"
        onSubmit={(event) => {
          event.preventDefault();
          void search();
        }}
      >
        <div className="ad-discovery-query">
          <Search size={18} />
          <input
            value={query}
            maxLength={200}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Search products, problems, hooks, brands, or ad copy…"
          />
          <button className="button primary" disabled={searching || !query.trim()}>
            {searching ? <LoaderCircle className="spin" size={15} /> : <Search size={15} />}
            {searching ? "Searching" : "Find ads"}
          </button>
        </div>
        <div className="ad-discovery-filters">
          <label>
            Platform
            <select value={platform} onChange={(event) => setPlatform(event.target.value)}>
              <option value="">All platforms</option>
              <option value="facebook">Facebook</option>
              <option value="instagram">Instagram</option>
              <option value="tiktok">TikTok</option>
              <option value="google">Google</option>
            </select>
          </label>
          <label>
            Status
            <select value={status} onChange={(event) => setStatus(event.target.value)}>
              <option value="">Any status</option>
              <option value="active">Active</option>
              <option value="inactive">Inactive</option>
            </select>
          </label>
          <label>
            Format
            <select value={adFormat} onChange={(event) => setAdFormat(event.target.value)}>
              <option value="">Any format</option>
              <option value="video">Video</option>
              <option value="image">Image</option>
              <option value="carousels">Carousel</option>
            </select>
          </label>
          <label>
            Minimum run time
            <select
              value={minimumDays}
              onChange={(event) => setMinimumDays(event.target.value)}
            >
              <option value="">Any duration</option>
              <option value="7">7+ days</option>
              <option value="14">14+ days</option>
              <option value="30">30+ days</option>
              <option value="60">60+ days</option>
            </select>
          </label>
        </div>
        <small>
          Live provider search. Up to 30 results may consume GetHookd credits; no
          result is saved to Northstar in this release.
        </small>
      </form>

      {error && (
        <div className="ad-search-error" role="alert">
          <AlertCircle size={16} /> {error}
        </div>
      )}

      {result && (
        <div className="ad-search-summary">
          <span>
            <b>{result.ads.length}</b> ads returned for “{result.query}”
          </span>
          <span>
            Used {result.used_credits ?? "unknown"} credits · remaining {result.remaining_credits ?? "unknown"}
          </span>
        </div>
      )}

      {result?.ads.length ? (
        <div className="discovery-ad-grid">
          {result.ads.map((ad, index) => {
            const creativeUrl = ad.provider_url || ad.creative_urls[0];
            return (
              <article
                className="panel discovery-ad-card"
                key={`${ad.provider_ad_id || ad.external_ad_id || index}`}
              >
                <div className="discovery-ad-media">
                  {ad.thumbnail_url ? (
                    <img src={ad.thumbnail_url} alt="" loading="lazy" />
                  ) : (
                    <Ad size={30} />
                  )}
                  <span>{humanize(ad.creative_type)}</span>
                </div>
                <header>
                  {ad.advertiser_logo_url ? (
                    <img src={ad.advertiser_logo_url} alt="" loading="lazy" />
                  ) : (
                    <span>{(ad.advertiser_name || "?").charAt(0)}</span>
                  )}
                  <div>
                    <b>{ad.advertiser_name || "Unknown advertiser"}</b>
                    <small>{ad.platforms.map(humanize).join(" · ") || "Platform not returned"}</small>
                  </div>
                  <StatusPill status={ad.is_active ? "active" : "inactive"} />
                </header>
                <div className="discovery-ad-copy">
                  {ad.headline && <h3>{ad.headline}</h3>}
                  <p>{ad.ad_text || "Provider did not return ad copy."}</p>
                </div>
                <dl>
                  <div>
                    <dt>Run duration</dt>
                    <dd>{ad.days_active != null ? `${ad.days_active} days` : "Unknown"}</dd>
                  </div>
                  <div>
                    <dt>Provider classification</dt>
                    <dd>{ad.provider_classification || "Not returned"}</dd>
                  </div>
                  <div>
                    <dt>Started</dt>
                    <dd>{formatDate(ad.delivery_start_time)}</dd>
                  </div>
                  <div>
                    <dt>CTA</dt>
                    <dd>{ad.cta || "Not returned"}</dd>
                  </div>
                </dl>
                <footer>
                  {ad.landing_url && (
                    <button
                      className="text-button"
                      onClick={() => window.open(ad.landing_url!, "_blank", "noopener")}
                    >
                      Landing page <ExternalLink size={12} />
                    </button>
                  )}
                  {creativeUrl && (
                    <button
                      className="button secondary"
                      onClick={() => window.open(creativeUrl, "_blank", "noopener")}
                    >
                      <Eye size={14} /> View creative
                    </button>
                  )}
                </footer>
              </article>
            );
          })}
        </div>
      ) : result && !searching ? (
        <EmptyState
          icon={Search}
          title="No ads returned"
          body="Try a broader product, problem, brand, or hook query and relax one or more filters."
        />
      ) : !result && !error ? (
        <EmptyState
          icon={Ad}
          title="Search the ad library"
          body="Start with a product name, customer problem, brand, or phrase used in ad copy."
        />
      ) : null}

      {result && <div className="coverage-callout"><CircleHelp size={17} /><span>{result.data_notice}</span></div>}
    </div>
  );
}

function AdWatchlistExplorer({ onImported }: { onImported: () => Promise<void> }) {
  const [data, setData] = useState<AdWatchListData | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [name, setName] = useState("");
  const [searchTerms, setSearchTerms] = useState("");
  const [advertiserId, setAdvertiserId] = useState("");
  const [provider, setProvider] = useState("meta_ad_library");
  const [countries, setCountries] = useState("GB");
  const [intervalHours, setIntervalHours] = useState("24");

  const load = async () => {
    setLoading(true);
    try {
      setData(await apiFetch<AdWatchListData>("/ad-watches"));
      setError("");
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Could not load ad watches.");
    } finally {
      setLoading(false);
    }
  };
  useEffect(() => { void load(); }, []);

  const create = async () => {
    if (!name.trim() || (!searchTerms.trim() && !advertiserId.trim())) return;
    setSaving(true);
    try {
      const automated = provider === "meta_ad_library";
      await apiFetch("/ad-watches", {
        method: "POST",
        body: JSON.stringify({
          name: name.trim(), provider,
          search_terms: searchTerms.trim() || null,
          advertiser_id: advertiserId.trim() || null,
          countries: countries.split(",").map((item) => item.trim()).filter(Boolean),
          interval_hours: Number(intervalHours), result_limit: 50,
          is_enabled: automated,
        }),
      });
      setName(""); setSearchTerms(""); setAdvertiserId("");
      await load();
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Could not create watch.");
    } finally { setSaving(false); }
  };

  const runNow = async (watch: AdWatch) => {
    try {
      await apiFetch(`/ad-watches/${watch.id}/run`, { method: "POST" });
      await load();
      window.setTimeout(() => { void load(); void onImported(); }, 1800);
    } catch (requestError) { setError(requestError instanceof Error ? requestError.message : "Could not queue watch."); }
  };
  const toggle = async (watch: AdWatch) => {
    try {
      await apiFetch(`/ad-watches/${watch.id}`, { method: "PATCH", body: JSON.stringify({ is_enabled: !watch.is_enabled }) });
      await load();
    } catch (requestError) { setError(requestError instanceof Error ? requestError.message : "Could not update watch."); }
  };
  const remove = async (watch: AdWatch) => {
    if (!window.confirm(`Delete the watch “${watch.name}”? Collected ads remain in the library.`)) return;
    try { await apiFetch(`/ad-watches/${watch.id}`, { method: "DELETE" }); await load(); }
    catch (requestError) { setError(requestError instanceof Error ? requestError.message : "Could not delete watch."); }
  };

  return (
    <div className="ad-watch-workspace">
      <section className="panel ad-watch-intro">
        <div><span className="eyebrow">DURABLE COLLECTION</span><h2>Advertiser watchlist</h2><p>Repeat official-source queries and build recurrence history. Northstar keeps compact old evidence when it remains useful instead of treating every inactive-looking record as worthless.</p></div>
        <div className="ad-watch-summary"><span><b>{data?.summary.total ?? 0}</b> watches</span><span><b>{data?.summary.enabled ?? 0}</b> scheduled</span><span><b>{data?.summary.failed ?? 0}</b> need attention</span></div>
      </section>

      <section className="panel ad-watch-create">
        <header><div><h3>Add a collection target</h3><p>Meta watches can run automatically. TikTok, Google and manual targets remain paused until an official adapter or user capture is available.</p></div></header>
        <div className="ad-watch-form">
          <input value={name} onChange={(event) => setName(event.target.value)} placeholder="Watch name" />
          <select value={provider} onChange={(event) => setProvider(event.target.value)}><option value="meta_ad_library">Meta official API</option><option value="tiktok_commercial_content">TikTok Commercial Content</option><option value="google_transparency">Google Transparency</option><option value="manual_capture">Browser/manual capture</option></select>
          <input value={searchTerms} onChange={(event) => setSearchTerms(event.target.value)} placeholder="Brand, product or keyword" />
          <input value={advertiserId} onChange={(event) => setAdvertiserId(event.target.value)} placeholder={provider === "meta_ad_library" ? "Meta Page ID (optional)" : "Advertiser ID (optional)"} />
          <input value={countries} onChange={(event) => setCountries(event.target.value.toUpperCase())} placeholder="Countries: GB,DE" />
          <select value={intervalHours} onChange={(event) => setIntervalHours(event.target.value)}><option value="6">Every 6 hours</option><option value="12">Every 12 hours</option><option value="24">Daily</option><option value="72">Every 3 days</option><option value="168">Weekly</option></select>
          <button className="button primary" disabled={saving || !name.trim() || (!searchTerms.trim() && !advertiserId.trim())} onClick={create}>{saving ? <LoaderCircle className="spin" size={15} /> : <Plus size={15} />}Add watch</button>
        </div>
      </section>

      {error && <div className="provider-callout danger"><AlertCircle size={18} /><div><b>Watchlist needs attention</b><span>{error}</span></div></div>}
      {loading && !data ? <div className="loading-panel"><LoaderCircle className="spin" /> Loading watches…</div> : null}
      {data?.watches.length ? <section className="ad-watch-grid">{data.watches.map((watch) => (
        <article className="panel ad-watch-card" key={watch.id}>
          <header><div><span>{humanize(watch.provider)}</span><h3>{watch.name}</h3></div><StatusPill status={watch.last_status} /></header>
          <p>{watch.advertiser_id ? `Advertiser/Page ${watch.advertiser_id}` : watch.search_terms} · {watch.countries.join(", ")}</p>
          <div className="ad-watch-metrics"><span><b>{watch.ad_count}</b> ads</span><span><b>{watch.retention_tiers.creative || 0}</b> creative priority</span><span><b>{watch.latest_run?.recurring_count || 0}</b> recurring last run</span></div>
          <dl><div><dt>Schedule</dt><dd>{watch.is_enabled ? `Every ${watch.interval_hours}h` : "Paused"}</dd></div><div><dt>Last collection</dt><dd>{watch.last_run_at ? formatDate(watch.last_run_at) : "Never"}</dd></div><div><dt>Next due</dt><dd>{watch.next_run_at ? formatDate(watch.next_run_at) : "Not scheduled"}</dd></div></dl>
          {watch.last_error && <small className="ad-watch-error">{watch.last_error}</small>}
          <footer><button className="text-button" onClick={() => void toggle(watch)}>{watch.is_enabled ? "Pause schedule" : "Enable schedule"}</button><button className="icon-button" aria-label={`Delete ${watch.name}`} onClick={() => void remove(watch)}><X size={14} /></button><button className="button secondary" disabled={watch.last_status === "queued" || watch.last_status === "running"} onClick={() => void runNow(watch)}><RefreshCw size={14} />Run now</button></footer>
        </article>
      ))}</section> : !loading ? <EmptyState icon={Radar} title="No advertiser watches yet" body="Add a focused brand, product keyword, or provider advertiser ID above. Targeted history is cheaper and more useful than indiscriminate global collection." /> : null}

      {data && <details className="panel retention-policy"><summary>How Northstar decides what old evidence to retain</summary><div>{Object.entries(data.retention_policy).map(([key, value]) => <p key={key}><b>{humanize(key)}</b><span>{value}</span></p>)}</div></details>}
    </div>
  );
}

function AdsPage({
  ads,
  metaConfigured,
  gethookdConfigured,
  onSearchMeta,
  onImported,
  onSettings,
  searching,
  onOpenAd,
}: {
  ads: RealAd[];
  metaConfigured: boolean;
  gethookdConfigured: boolean;
  onSearchMeta: (query: string, country: string) => void;
  onImported: () => Promise<void>;
  onSettings: () => void;
  searching: boolean;
  onOpenAd: (id: number) => void;
}) {
  const [source, setSource] = useState<"library" | "watches" | "gethookd" | "meta">("library");
  return (
    <div className="page-content">
      <PageHeading
        eyebrow="AD DISCOVERY"
        title="Ad & product library"
        subtitle="Browse saved ads or search connected providers, then inspect creatives, linked products, landing pages, and observable run signals."
        actions={
          <button className="button secondary" onClick={onSettings}>
            <Settings size={15} /> Providers
          </button>
        }
      />
      <div className="ad-source-switch" role="tablist" aria-label="Ad data source">
        <button
          className={source === "library" ? "active" : ""}
          onClick={() => setSource("library")}
        >
          Northstar library
          <span className="source-count">{ads.length}</span>
        </button>
        <button className={source === "watches" ? "active" : ""} onClick={() => setSource("watches")}>
          Advertiser watches
        </button>
        <button
          className={source === "gethookd" ? "active" : ""}
          onClick={() => setSource("gethookd")}
        >
          GetHookd search
          <StatusPill status={gethookdConfigured ? "connected" : "offline"} />
        </button>
        <button
          className={source === "meta" ? "active" : ""}
          onClick={() => setSource("meta")}
        >
          Official Meta API
          <StatusPill status={metaConfigured ? "connected" : "offline"} />
        </button>
      </div>
      {source === "library" ? (
        <OwnAdLibrary ads={ads} onImported={onImported} onOpenAd={onOpenAd} />
      ) : source === "watches" ? (
        <AdWatchlistExplorer onImported={onImported} />
      ) : source === "gethookd" ? (
        <GetHookdExplorer configured={gethookdConfigured} onSettings={onSettings} />
      ) : (
        <MetaAdsExplorer
          ads={ads}
          metaConfigured={metaConfigured}
          onSearchMeta={onSearchMeta}
          onSettings={onSettings}
          searching={searching}
        />
      )}
    </div>
  );
}

function IntegrationCard({
  provider,
  title,
  description,
  configured,
  maskedKey,
  onSave,
  onRemove,
  docsUrl,
  activeSource,
}: {
  provider: "meta" | "gethookd" | "similarweb";
  title: string;
  description: string;
  configured: boolean;
  maskedKey?: string;
  onSave: (provider: "meta" | "gethookd" | "similarweb", key: string) => Promise<void>;
  onRemove: (provider: "meta" | "gethookd" | "similarweb") => Promise<void>;
  docsUrl: string;
  activeSource?: string | null;
}) {
  const [key, setKey] = useState("");
  const [busy, setBusy] = useState(false);
  const environmentManaged = activeSource === "environment";
  return (
    <article className="integration-real-card">
      <span className={`integration-logo integration-${provider}`}>
        {provider === "meta" ? "M" : provider === "gethookd" ? "G" : "S"}
      </span>
      <div className="integration-copy">
        <div>
          <h2>{title}</h2>
          <StatusPill status={configured ? "configured" : "offline"} />
        </div>
        <p>{description}</p>
        {configured && (
          <code>
            {environmentManaged ? "Managed by .env · " : ""}
            {maskedKey || "Credential configured"}
          </code>
        )}
        {environmentManaged && (
          <small className="environment-credential-note">
            Edit the environment file and restart Northstar to replace or remove
            this credential.
          </small>
        )}
        <a href={docsUrl} target="_blank" rel="noreferrer">
          Provider documentation <ExternalLink size={12} />
        </a>
      </div>
      {!environmentManaged && (
        <form
          onSubmit={async (event) => {
            event.preventDefault();
            if (!key.trim()) return;
            setBusy(true);
            try {
              await onSave(provider, key.trim());
              setKey("");
            } finally {
              setBusy(false);
            }
          }}
        >
          <input
            type="password"
            value={key}
            onChange={(event) => setKey(event.target.value)}
            placeholder={
              configured ? "Replace credential" : "Paste API credential"
            }
          />
          <button className="button primary" disabled={busy || !key.trim()}>
            {busy ? "Saving…" : configured ? "Replace" : "Connect"}
          </button>
          {configured && (
            <button
              type="button"
              className="button secondary"
              onClick={() => onRemove(provider)}
            >
              Remove
            </button>
          )}
        </form>
      )}
    </article>
  );
}

const defaultMomentumWeights: Record<string, number> = {
  advertising: 0.3,
  reviews: 0.25,
  merchandising: 0.15,
  inventory: 0.15,
  persistence: 0.1,
  offer_page: 0.05,
};

type EstimationFormState = {
  conversionLow: string;
  conversionCentral: string;
  conversionHigh: string;
  basketLow: string;
  basketCentral: string;
  basketHigh: string;
  trafficLow: string;
  trafficHigh: string;
  freshnessDays: string;
  minimumEvidence: string;
  weights: Record<string, string>;
};

function estimationForm(profile: EstimationProfileSettings): EstimationFormState {
  const weights = { ...defaultMomentumWeights, ...(profile.score_weights || {}) };
  return {
    conversionLow: String(profile.conversion_rate_low * 100),
    conversionCentral: String(
      (profile.conversion_rate_central ?? profile.conversion_rate_low) * 100,
    ),
    conversionHigh: String(profile.conversion_rate_high * 100),
    basketLow: String(profile.basket_multiplier_low),
    basketCentral: String(
      profile.basket_multiplier_central ?? profile.basket_multiplier_low,
    ),
    basketHigh: String(profile.basket_multiplier_high),
    trafficLow: String(profile.traffic_reliability_low),
    trafficHigh: String(profile.traffic_reliability_high),
    freshnessDays: String(profile.freshness_limit_days),
    minimumEvidence: String(profile.minimum_evidence_count),
    weights: Object.fromEntries(
      Object.entries(weights).map(([key, value]) => [
        key,
        String(value * 100),
      ]),
    ),
  };
}

function EstimationSettingsCard() {
  const [profile, setProfile] = useState<EstimationProfileSettings | null>(null);
  const [form, setForm] = useState<EstimationFormState | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    apiFetch<EstimationProfileSettings[]>("/intelligence/settings")
      .then((profiles) => {
        if (!active) return;
        const selected =
          profiles.find(
            (item) =>
              item.is_default && item.category_key === "general_ecommerce",
          ) || profiles.find((item) => item.is_default) || profiles[0] || null;
        setProfile(selected);
        setForm(selected ? estimationForm(selected) : null);
        setError(null);
      })
      .catch((requestError) => {
        if (!active) return;
        setError(
          requestError instanceof Error
            ? requestError.message
            : "Estimation settings could not be loaded.",
        );
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);

  const setField = (key: keyof Omit<EstimationFormState, "weights">, value: string) =>
    setForm((current) => (current ? { ...current, [key]: value } : current));

  if (loading) {
    return (
      <section className="panel estimation-settings-panel settings-loading">
        <LoaderCircle className="spin" size={19} />
        <span>Loading estimation assumptions…</span>
      </section>
    );
  }

  if (error || !profile || !form) {
    return (
      <section className="panel estimation-settings-panel settings-error">
        <AlertCircle size={19} />
        <div>
          <h2>Estimation assumptions unavailable</h2>
          <p>{error || "The backend did not return an active profile."}</p>
        </div>
      </section>
    );
  }

  const numberValue = (value: string) => Number(value);
  return (
    <section className="panel estimation-settings-panel">
      <div className="panel-header estimation-settings-header">
        <div>
          <h2>Estimation assumptions</h2>
          <p>
            These are editable planning priors—not facts about a scanned store.
            Every report preserves the exact values used for its calculation.
          </p>
        </div>
        <StatusPill status="configured" />
      </div>
      <form
        onSubmit={async (event) => {
          event.preventDefault();
          setSaving(true);
          setMessage(null);
          setError(null);
          try {
            const scoreWeights = Object.fromEntries(
              Object.entries(form.weights).map(([key, value]) => [
                key,
                numberValue(value) / 100,
              ]),
            );
            const saved = await apiFetch<EstimationProfileSettings>(
              `/intelligence/settings/${profile.category_key}`,
              {
                method: "PUT",
                body: JSON.stringify({
                  conversion_rate_low: numberValue(form.conversionLow) / 100,
                  conversion_rate_central:
                    numberValue(form.conversionCentral) / 100,
                  conversion_rate_high: numberValue(form.conversionHigh) / 100,
                  basket_multiplier_low: numberValue(form.basketLow),
                  basket_multiplier_central: numberValue(form.basketCentral),
                  basket_multiplier_high: numberValue(form.basketHigh),
                  traffic_reliability_low: numberValue(form.trafficLow),
                  traffic_reliability_central: 1,
                  traffic_reliability_high: numberValue(form.trafficHigh),
                  freshness_limit_days: numberValue(form.freshnessDays),
                  minimum_evidence_count: numberValue(form.minimumEvidence),
                  score_weights: scoreWeights,
                }),
              },
            );
            setProfile(saved);
            setForm(estimationForm(saved));
            setMessage("A new versioned assumption profile was saved.");
          } catch (requestError) {
            setError(
              requestError instanceof Error
                ? requestError.message
                : "The assumptions could not be saved.",
            );
          } finally {
            setSaving(false);
          }
        }}
      >
        <div className="assumption-group">
          <div>
            <h3>Conversion-rate range</h3>
            <p>Used only when monthly visits are available.</p>
          </div>
          <div className="assumption-input-grid three">
            {(
              [
                ["Low", "conversionLow"],
                ["Central", "conversionCentral"],
                ["High", "conversionHigh"],
              ] as const
            ).map(([label, field]) => (
              <label key={field}>
                {label} (%)
                <input
                  type="number"
                  min="0"
                  max="100"
                  step="0.1"
                  value={form[field]}
                  onChange={(event) => setField(field, event.target.value)}
                  required
                />
              </label>
            ))}
          </div>
        </div>
        <div className="assumption-group">
          <div>
            <h3>Items per order</h3>
            <p>Multiplies eligible catalog price anchors for the AOV range.</p>
          </div>
          <div className="assumption-input-grid three">
            {(
              [
                ["Low", "basketLow"],
                ["Central", "basketCentral"],
                ["High", "basketHigh"],
              ] as const
            ).map(([label, field]) => (
              <label key={field}>
                {label}
                <input
                  type="number"
                  min="0.1"
                  max="20"
                  step="0.05"
                  value={form[field]}
                  onChange={(event) => setField(field, event.target.value)}
                  required
                />
              </label>
            ))}
          </div>
        </div>
        <div className="assumption-group">
          <div>
            <h3>Traffic reliability envelope</h3>
            <p>
              Northstar planning multipliers around a provider point—not a
              Similarweb confidence interval.
            </p>
          </div>
          <div className="assumption-input-grid two">
            <label>
              Low multiplier
              <input
                type="number"
                min="0.1"
                max="5"
                step="0.05"
                value={form.trafficLow}
                onChange={(event) => setField("trafficLow", event.target.value)}
                required
              />
            </label>
            <label>
              High multiplier
              <input
                type="number"
                min="1"
                max="5"
                step="0.05"
                value={form.trafficHigh}
                onChange={(event) => setField("trafficHigh", event.target.value)}
                required
              />
            </label>
          </div>
        </div>
        <div className="assumption-group compact-assumption-group">
          <div>
            <h3>Evidence gates</h3>
            <p>Stale or thin evidence lowers confidence or withholds a score.</p>
          </div>
          <div className="assumption-input-grid two">
            <label>
              Freshness limit (days)
              <input
                type="number"
                min="1"
                max="365"
                step="1"
                value={form.freshnessDays}
                onChange={(event) =>
                  setField("freshnessDays", event.target.value)
                }
                required
              />
            </label>
            <label>
              Minimum independent groups
              <input
                type="number"
                min="1"
                max="6"
                step="1"
                value={form.minimumEvidence}
                onChange={(event) =>
                  setField("minimumEvidence", event.target.value)
                }
                required
              />
            </label>
          </div>
        </div>
        <div className="assumption-group weight-assumption-group">
          <div>
            <h3>Product momentum evidence weights</h3>
            <p>Correlated facts inside one group are collapsed before weighting.</p>
          </div>
          <div className="weight-input-grid">
            {Object.entries(form.weights).map(([key, value]) => (
              <label key={key}>
                {key.replace(/_/g, " ")} (%)
                <input
                  type="number"
                  min="0"
                  max="100"
                  step="1"
                  value={value}
                  onChange={(event) =>
                    setForm((current) =>
                      current
                        ? {
                            ...current,
                            weights: {
                              ...current.weights,
                              [key]: event.target.value,
                            },
                          }
                        : current,
                    )
                  }
                  required
                />
              </label>
            ))}
          </div>
        </div>
        {(message || error) && (
          <div className={`settings-form-message ${error ? "error" : "success"}`}>
            {error ? <AlertCircle size={15} /> : <CheckCircle2 size={15} />}
            <span>{error || message}</span>
          </div>
        )}
        <footer className="estimation-settings-footer">
          <small>
            Active profile: {profile.version} · updated {formatDate(profile.updated_at)}
          </small>
          <button className="button primary" disabled={saving}>
            {saving ? <LoaderCircle className="spin" size={15} /> : <Check size={15} />}
            {saving ? "Saving" : "Save new profile version"}
          </button>
        </footer>
      </form>
    </section>
  );
}

function SettingsPage({
  apiStatus,
  integrations,
  onSaveIntegration,
  onRemoveIntegration,
}: {
  apiStatus: ApiStatus;
  integrations: IntegrationStatus | null;
  onSaveIntegration: (
    provider: "meta" | "gethookd" | "similarweb",
    key: string,
  ) => Promise<void>;
  onRemoveIntegration: (provider: "meta" | "gethookd" | "similarweb") => Promise<void>;
}) {
  return (
    <div className="page-content narrow-page">
      <PageHeading
        eyebrow="PRIVATE LOCAL CONFIGURATION"
        title="Settings & data sources"
        subtitle="Credentials stay on this computer and are never bundled into the browser."
      />
      <section className="panel local-engine-card">
        <div className={`connection-icon connection-${apiStatus}`}>
          <Database size={19} />
        </div>
        <div>
          <h2>Northstar local engine</h2>
          <p>
            SQLite persistence and the background crawler at 127.0.0.1:8000.
          </p>
        </div>
        <StatusPill status={apiStatus} />
      </section>
      <section className="panel integrations-real-panel">
        <div className="panel-header">
          <div>
            <h2>External intelligence providers</h2>
            <p>
              Northstar shows no provider data until a valid credential is
              connected.
            </p>
          </div>
        </div>
        <div className="credential-storage-note">
          <AlertCircle size={15} />
          <span>
            Credentials saved here are stored as plaintext in the local backend
            data folder. Use <code>.env</code> if you manage secrets separately.
          </span>
        </div>
        <IntegrationCard
          provider="meta"
          title="Meta Ad Library API"
          description="Imports ads returned by Meta’s official transparency API. Availability and fields depend on Meta’s access rules and your token."
          configured={isConfigured(integrations, "meta")}
          maskedKey={
            integrations?.meta?.masked_token || integrations?.meta?.masked_key
          }
          onSave={onSaveIntegration}
          onRemove={onRemoveIntegration}
          docsUrl="https://www.facebook.com/ads/library/api/"
          activeSource={integrations?.meta?.active_source}
        />
        <IntegrationCard
          provider="gethookd"
          title="GetHookd public API"
          description="Searches GetHookd’s ad library live. Searches can consume provider credits; classifications and duration are signals, not proof of profitability."
          configured={isConfigured(integrations, "gethookd")}
          maskedKey={
            integrations?.gethookd?.masked_token || integrations?.gethookd?.masked_key
          }
          onSave={onSaveIntegration}
          onRemove={onRemoveIntegration}
          docsUrl="https://www.gethookd.ai/api/"
          activeSource={integrations?.gethookd?.active_source}
        />
        <IntegrationCard
          provider="similarweb"
          title="Similarweb API"
          description="Retrieves Similarweb global rank and, when enabled for your account, estimated monthly visits. Similarweb—not Northstar—models these figures."
          configured={isConfigured(integrations, "similarweb")}
          maskedKey={integrations?.similarweb?.masked_key}
          onSave={onSaveIntegration}
          onRemove={onRemoveIntegration}
          docsUrl="https://developers.similarweb.com/reference/visits"
          activeSource={integrations?.similarweb?.active_source}
        />
      </section>
      <EstimationSettingsCard />
      <section className="panel disclosure-card">
        <ShieldCheck size={22} />
        <div>
          <h2>Data labeling policy</h2>
          <p>
            Observed storefront fields are labeled Observed. Similarweb numbers
            are labeled Provider estimate. Meta records are labeled Imported.
            Derived ranges identify their evidence and assumptions; unsupported
            conclusions remain marked insufficient data.
          </p>
        </div>
      </section>
    </div>
  );
}

function ProductComparisonPage({ products }: { products: LocalProduct[] }) {
  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState<number[]>([]);
  const [comparison, setComparison] = useState<ProductComparisonData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const filtered = products.filter((product) => `${product.title} ${product.store_domain || ""}`.toLowerCase().includes(query.toLowerCase()));
  const toggle = (productId: number) => {
    setComparison(null);
    setSelected((current) => current.includes(productId) ? current.filter((id) => id !== productId) : current.length < 5 ? [...current, productId] : current);
  };
  const compare = async () => {
    if (selected.length < 2) return;
    setLoading(true);
    setError(null);
    try {
      setComparison(await apiFetch<ProductComparisonData>(`/comparisons/products?ids=${selected.join(",")}`));
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "The products could not be compared.");
    } finally {
      setLoading(false);
    }
  };
  const exportJson = () => {
    if (!comparison) return;
    const url = URL.createObjectURL(new Blob([JSON.stringify(comparison, null, 2)], { type: "application/json" }));
    const link = document.createElement("a");
    link.href = url;
    link.download = `northstar-product-comparison-${new Date().toISOString().slice(0, 10)}.json`;
    link.click();
    URL.revokeObjectURL(url);
  };
  const moneyRange = (low: number | string | null | undefined, high: number | string | null | undefined, currency = "USD") => low == null && high == null ? "Unavailable" : Number(low) === Number(high) ? formatMoney(Number(low), currency) : `${low == null ? "?" : formatMoney(Number(low), currency)}–${high == null ? "?" : formatMoney(Number(high), currency)}`;
  const roasRange = (low?: string | number | null, high?: string | number | null) => low == null && high == null ? "Unavailable" : `${low == null ? "?" : `${Number(low).toFixed(2)}×`}–${high == null ? "?" : `${Number(high).toFixed(2)}×`}`;

  const rows: Array<{ label: string; render: (product: ProductComparisonData["products"][number]) => React.ReactNode }> = [
    { label: "Store / platform", render: (product) => <><b>{product.store_domain}</b><small>{humanize(product.platform)}</small></> },
    { label: "Observed price", render: (product) => moneyRange(product.price_low, product.price_high, product.currency || "USD") },
    { label: "Variants / images", render: (product) => `${product.variant_count ?? "?"} variants · ${product.image_count} images` },
    { label: "Availability", render: (product) => product.available == null ? "Not observed" : product.available ? "Available" : "Unavailable" },
    { label: "Northstar observation span", render: (product) => <>{product.observation_days} days<small>Not product age</small></> },
    { label: "Related collected ads", render: (product) => <>{product.related_ad_count}<small>Known corpus only</small></> },
    { label: "Normalized evidence", render: (product) => <>{product.evidence_count} records<small>{product.evidence_types.length ? product.evidence_types.map(humanize).join(", ") : "No typed product evidence"}</small></> },
    { label: "Economics status", render: (product) => product.economics ? <><StatusPill status={product.economics.status} /><small>{product.economics.scenario_name} · user entered</small></> : "No saved scenario" },
    { label: "Break-even CPA", render: (product) => product.economics ? moneyRange(product.economics.break_even_cpa_low, product.economics.break_even_cpa_high, product.economics.currency) : "Unavailable" },
    { label: "Target CPA", render: (product) => product.economics ? moneyRange(product.economics.target_cpa_low, product.economics.target_cpa_high, product.economics.currency) : "Unavailable" },
    { label: "Target ROAS", render: (product) => product.economics ? roasRange(product.economics.target_roas_low, product.economics.target_roas_high) : "Unavailable" },
    { label: "Important unknowns", render: (product) => product.unavailable.map(humanize).join(", ") },
  ];

  return (
    <div className="page-content comparison-page">
      <PageHeading eyebrow="KNOWN-CORPUS COMPARISON" title="Compare products" subtitle="Compare collected storefront facts, evidence coverage, related ads, and your own economics scenarios without worldwide-market or sales claims." actions={comparison ? <button className="button secondary" onClick={exportJson}><Download size={15} />Export JSON</button> : undefined} />
      <section className="panel comparison-picker"><div className="comparison-picker-head"><div className="filter-search"><Search size={15} /><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Find collected products…" /></div><span>{selected.length}/5 selected</span><button className="button primary" disabled={selected.length < 2 || loading} onClick={compare}>{loading ? <LoaderCircle className="spin" size={15} /> : <GitCompareArrows size={15} />}{loading ? "Comparing" : "Compare selected"}</button></div><div className="comparison-product-picker">{filtered.map((product) => <button key={product.id} className={selected.includes(product.id) ? "selected" : ""} onClick={() => toggle(product.id)}><span className="comparison-check">{selected.includes(product.id) ? <Check size={13} /> : null}</span><span><b>{product.title}</b><small>{product.store_domain || "Store unavailable"} · {formatMoney(product.price_min, product.currency)}</small></span></button>)}</div><small className="comparison-boundary">Select 2–5 products. Exact-title or visual similarity is not assumed.</small></section>
      {error && <div className="ad-search-error"><AlertCircle size={15} />{error}</div>}
      {comparison && <><div className="comparison-corpus-strip"><span>Known corpus <b>{comparison.known_corpus.product_count} products</b></span><span><b>{comparison.known_corpus.store_count} stores</b></span><span>Generated <b>{formatDate(comparison.generated_at)}</b></span></div><section className="panel comparison-table-wrap"><table className="comparison-table"><thead><tr><th>Dimension</th>{comparison.products.map((product) => <th key={product.product_id}><a href={product.canonical_url} target="_blank" rel="noreferrer">{product.title}<ExternalLink size={12} /></a></th>)}</tr></thead><tbody>{rows.map((row) => <tr key={row.label}><th>{row.label}</th>{comparison.products.map((product) => <td key={product.product_id}>{row.render(product)}</td>)}</tr>)}</tbody></table></section><div className="coverage-callout"><CircleHelp size={17} /><span>{comparison.data_notice}</span></div></>}
      {!comparison && !loading && <EmptyState icon={GitCompareArrows} title="Select products to compare" body="Choose between two and five collected products. The matrix will keep unavailable demand, supplier, and performance fields explicit." />}
    </div>
  );
}

function InvestigationAction({ entityType, entityId }: { entityType: "store" | "product" | "ad"; entityId: number }) {
  const [item, setItem] = useState<InvestigationItem | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(false);

  useEffect(() => {
    let active = true;
    apiFetch<InvestigationItem[]>(`/investigations?entity_type=${entityType}&entity_id=${entityId}`)
      .then((rows) => active && setItem(rows[0] || null))
      .catch(() => undefined);
    return () => { active = false; };
  }, [entityType, entityId]);

  const save = async () => {
    if (item) return;
    setBusy(true);
    setError(false);
    try {
      const created = await apiFetch<InvestigationItem>("/investigations", {
        method: "POST",
        body: JSON.stringify({ entity_type: entityType, entity_id: entityId, workflow_stage: "inbox", decision: "undecided", priority: "medium" }),
      });
      setItem(created);
    } catch {
      setError(true);
    } finally {
      setBusy(false);
    }
  };

  return <button className={item ? "button tertiary shortlist-saved" : "button secondary"} disabled={busy || Boolean(item)} onClick={save}>{busy ? <LoaderCircle className="spin" size={14} /> : <Bookmark size={14} />}{error ? "Retry shortlist" : item ? "In shortlist" : "Add to shortlist"}</button>;
}

function ShortlistPage({ onOpen }: { onOpen: (item: InvestigationItem) => void }) {
  const [items, setItems] = useState<InvestigationItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [entityFilter, setEntityFilter] = useState("");
  const [stageFilter, setStageFilter] = useState("");
  const [query, setQuery] = useState("");
  const [editingId, setEditingId] = useState<number | null>(null);
  const [saving, setSaving] = useState(false);
  const [edit, setEdit] = useState({ workflow_stage: "researching", decision: "investigate", priority: "medium", thesis: "", risks: "", next_action: "" });

  const load = () => {
    setLoading(true);
    apiFetch<InvestigationItem[]>("/investigations")
      .then(setItems)
      .catch((requestError) => setError(requestError instanceof Error ? requestError.message : "The shortlist could not be loaded."))
      .finally(() => setLoading(false));
  };
  useEffect(load, []);

  const beginEdit = (item: InvestigationItem) => {
    setEditingId(item.id);
    setEdit({ workflow_stage: item.workflow_stage, decision: item.decision, priority: item.priority, thesis: item.thesis || "", risks: item.risks || "", next_action: item.next_action || "" });
  };
  const save = async (item: InvestigationItem) => {
    setSaving(true);
    setError(null);
    try {
      const updated = await apiFetch<InvestigationItem>(`/investigations/${item.id}`, { method: "PUT", body: JSON.stringify({ ...edit, evidence_ids: item.evidence.map((row) => row.id) }) });
      setItems((current) => current.map((row) => row.id === updated.id ? updated : row));
      setEditingId(null);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "The investigation could not be saved.");
    } finally {
      setSaving(false);
    }
  };
  const archive = async (item: InvestigationItem) => {
    setSaving(true);
    try {
      await apiFetch(`/investigations/${item.id}`, { method: "DELETE" });
      setItems((current) => current.filter((row) => row.id !== item.id));
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "The investigation could not be archived.");
    } finally {
      setSaving(false);
    }
  };
  const exportDossier = async (item: InvestigationItem) => {
    setSaving(true);
    setError(null);
    try {
      const dossier = await apiFetch<Record<string, unknown>>(`/exports/investigations/${item.id}`);
      const url = URL.createObjectURL(new Blob([JSON.stringify(dossier, null, 2)], { type: "application/json" }));
      const link = document.createElement("a");
      link.href = url;
      link.download = `northstar-investigation-${item.id}.json`;
      link.click();
      URL.revokeObjectURL(url);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "The dossier could not be exported.");
    } finally {
      setSaving(false);
    }
  };
  const filtered = items.filter((item) => (!entityFilter || item.entity_type === entityFilter) && (!stageFilter || item.workflow_stage === stageFilter) && `${item.entity_title} ${item.entity_subtitle || ""} ${item.thesis || ""} ${item.risks || ""} ${item.next_action || ""}`.toLowerCase().includes(query.toLowerCase()));
  const counts = { active: items.length, test: items.filter((item) => item.decision === "test").length, blocked: items.filter((item) => !item.next_action).length };

  return (
    <div className="page-content shortlist-page">
      <PageHeading eyebrow="DECISION WORKSPACE" title="Investigation shortlist" subtitle="Turn saved stores, products, and ads into an explicit thesis, risk register, next verification action, and test or reject decision." />
      <div className="shortlist-summary"><div><span>Active investigations</span><b>{counts.active}</b></div><div><span>Marked test</span><b>{counts.test}</b></div><div><span>Missing next action</span><b>{counts.blocked}</b></div></div>
      <div className="filterbar real-filterbar"><div className="filter-search"><Search size={15} /><input value={query} placeholder="Filter titles and notes…" onChange={(event) => setQuery(event.target.value)} /></div><select value={entityFilter} onChange={(event) => setEntityFilter(event.target.value)}><option value="">All entity types</option><option value="store">Stores</option><option value="product">Products</option><option value="ad">Ads</option></select><select value={stageFilter} onChange={(event) => setStageFilter(event.target.value)}><option value="">All stages</option><option value="inbox">Inbox</option><option value="researching">Researching</option><option value="ready_to_test">Ready to test</option><option value="testing">Testing</option><option value="decided">Decided</option></select><span className="filter-count">{filtered.length} items</span></div>
      {error && <div className="ad-search-error"><AlertCircle size={15} />{error}</div>}
      {loading ? <div className="identity-review-loading"><LoaderCircle className="spin" size={18} />Loading investigations…</div> : filtered.length ? <div className="shortlist-grid">{filtered.map((item) => <article className="panel shortlist-card" key={item.id}><header><div><span className="shortlist-entity">{humanize(item.entity_type)}</span><button onClick={() => onOpen(item)}><h2>{item.entity_title}</h2><small>{item.entity_subtitle || `Northstar ${item.entity_type} ${item.entity_id}`}</small></button></div><StatusPill status={item.priority} /></header>{editingId === item.id ? <div className="shortlist-edit"><div className="shortlist-selects"><label>Stage<select value={edit.workflow_stage} onChange={(event) => setEdit((current) => ({ ...current, workflow_stage: event.target.value }))}><option value="inbox">Inbox</option><option value="researching">Researching</option><option value="ready_to_test">Ready to test</option><option value="testing">Testing</option><option value="decided">Decided</option></select></label><label>Decision<select value={edit.decision} onChange={(event) => setEdit((current) => ({ ...current, decision: event.target.value }))}><option value="undecided">Undecided</option><option value="investigate">Investigate</option><option value="test">Test</option><option value="reject">Reject</option></select></label><label>Priority<select value={edit.priority} onChange={(event) => setEdit((current) => ({ ...current, priority: event.target.value }))}><option value="low">Low</option><option value="medium">Medium</option><option value="high">High</option></select></label></div><label>Thesis<textarea rows={3} value={edit.thesis} onChange={(event) => setEdit((current) => ({ ...current, thesis: event.target.value }))} /></label><label>Risks<textarea rows={3} value={edit.risks} onChange={(event) => setEdit((current) => ({ ...current, risks: event.target.value }))} /></label><label>Next verification action<textarea rows={2} value={edit.next_action} onChange={(event) => setEdit((current) => ({ ...current, next_action: event.target.value }))} /></label><footer><button className="text-button" onClick={() => archive(item)}>Archive</button><div><button className="button secondary" onClick={() => setEditingId(null)}>Cancel</button><button className="button primary" disabled={saving} onClick={() => save(item)}>{saving ? <LoaderCircle className="spin" size={14} /> : <Save size={14} />}Save</button></div></footer></div> : <><div className="shortlist-state"><StatusPill status={item.workflow_stage} /><span>Decision <b>{humanize(item.decision)}</b></span><span>{item.evidence.length} cited evidence records</span></div><dl><div><dt>Thesis</dt><dd>{item.thesis || "Not written yet"}</dd></div><div><dt>Risks</dt><dd>{item.risks || "Not written yet"}</dd></div><div><dt>Next action</dt><dd>{item.next_action || "Missing — define the next verification step"}</dd></div></dl><footer><small>Updated {formatDate(item.updated_at)}</small><div><button className="button secondary" disabled={saving} onClick={() => exportDossier(item)}><Download size={14} />Dossier</button><button className="button secondary" onClick={() => beginEdit(item)}>Edit investigation</button></div></footer></>}</article>)}</div> : <EmptyState icon={ClipboardList} title="Your investigation shortlist is empty" body="Add a store, product, or ad from its report or detail view, then record the thesis, risks, and next verification action here." />}
    </div>
  );
}

type EconomicsFormState = {
  name: string;
  currency: string;
  sellingPrice: string;
  productCostLow: string;
  productCostHigh: string;
  shippingCostLow: string;
  shippingCostHigh: string;
  fulfillmentCostLow: string;
  fulfillmentCostHigh: string;
  otherCostLow: string;
  otherCostHigh: string;
  paymentFeePercent: string;
  paymentFeeFixed: string;
  refundPercent: string;
  targetMarginPercent: string;
  notes: string;
};

function economicsForm(product: LocalProduct, scenario?: ProductEconomicsScenario): EconomicsFormState {
  const percent = (value: string | number) => String(Math.round(Number(value) * 10000) / 100);
  return {
    name: scenario?.name || "Base case",
    currency: scenario?.currency || product.currency || "USD",
    sellingPrice: String(scenario?.selling_price ?? product.price_min ?? ""),
    productCostLow: String(scenario?.product_cost_low ?? ""),
    productCostHigh: String(scenario?.product_cost_high ?? ""),
    shippingCostLow: String(scenario?.shipping_cost_low ?? "0"),
    shippingCostHigh: String(scenario?.shipping_cost_high ?? "0"),
    fulfillmentCostLow: String(scenario?.fulfillment_cost_low ?? "0"),
    fulfillmentCostHigh: String(scenario?.fulfillment_cost_high ?? "0"),
    otherCostLow: String(scenario?.other_variable_cost_low ?? "0"),
    otherCostHigh: String(scenario?.other_variable_cost_high ?? "0"),
    paymentFeePercent: scenario ? percent(scenario.payment_fee_rate) : "2.9",
    paymentFeeFixed: String(scenario?.payment_fee_fixed ?? "0.30"),
    refundPercent: scenario ? percent(scenario.refund_allowance_rate) : "5",
    targetMarginPercent: scenario ? percent(scenario.target_profit_margin) : "20",
    notes: scenario?.notes || "",
  };
}

function ProductEconomicsPlanner({ product }: { product: LocalProduct }) {
  const [scenarios, setScenarios] = useState<ProductEconomicsScenario[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [form, setForm] = useState<EconomicsFormState>(() => economicsForm(product));
  const [editing, setEditing] = useState(false);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    setLoading(true);
    apiFetch<ProductEconomicsScenario[]>(`/products/${product.id}/economics`)
      .then((rows) => {
        if (!active) return;
        setScenarios(rows);
        setSelectedId(rows[0]?.id || null);
      })
      .catch((requestError) => active && setError(requestError instanceof Error ? requestError.message : "Economics scenarios could not be loaded."))
      .finally(() => active && setLoading(false));
    return () => { active = false; };
  }, [product.id]);

  const selected = scenarios.find((scenario) => scenario.id === selectedId) || scenarios[0] || null;
  const setValue = (key: keyof EconomicsFormState, value: string) => setForm((current) => ({ ...current, [key]: value }));
  const moneyRange = (low: string | number, high: string | number, currency: string) => {
    const left = formatMoney(Number(low), currency);
    const right = formatMoney(Number(high), currency);
    return Number(low) === Number(high) ? left : `${left}–${right}`;
  };
  const ratioRange = (low?: string | number | null, high?: string | number | null) => {
    if (low == null && high == null) return "Unavailable";
    const left = low == null ? "?" : `${Number(low).toFixed(2)}×`;
    const right = high == null ? "?" : `${Number(high).toFixed(2)}×`;
    return left === right ? left : `${left}–${right}`;
  };

  const beginNew = () => {
    setSelectedId(null);
    setForm(economicsForm(product));
    setEditing(true);
    setError(null);
  };
  const beginEdit = (scenario: ProductEconomicsScenario) => {
    setSelectedId(scenario.id);
    setForm(economicsForm(product, scenario));
    setEditing(true);
    setError(null);
  };

  const saveScenario = async (event: React.FormEvent) => {
    event.preventDefault();
    setSaving(true);
    setError(null);
    const number = (value: string) => Number(value || 0);
    try {
      const payload = {
        name: form.name,
        currency: form.currency,
        selling_price: number(form.sellingPrice),
        product_cost_low: number(form.productCostLow),
        product_cost_high: number(form.productCostHigh),
        shipping_cost_low: number(form.shippingCostLow),
        shipping_cost_high: number(form.shippingCostHigh),
        fulfillment_cost_low: number(form.fulfillmentCostLow),
        fulfillment_cost_high: number(form.fulfillmentCostHigh),
        other_variable_cost_low: number(form.otherCostLow),
        other_variable_cost_high: number(form.otherCostHigh),
        payment_fee_rate: number(form.paymentFeePercent) / 100,
        payment_fee_fixed: number(form.paymentFeeFixed),
        refund_allowance_rate: number(form.refundPercent) / 100,
        target_profit_margin: number(form.targetMarginPercent) / 100,
        notes: form.notes || null,
      };
      const revised = selectedId != null && selected;
      const saved = await apiFetch<ProductEconomicsScenario>(
        revised ? `/products/${product.id}/economics/${selected.id}` : `/products/${product.id}/economics`,
        { method: revised ? "PUT" : "POST", body: JSON.stringify(payload) },
      );
      setScenarios((current) => [saved, ...current.filter((row) => row.id !== selected?.id)]);
      setSelectedId(saved.id);
      setEditing(false);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "The scenario could not be saved.");
    } finally {
      setSaving(false);
    }
  };

  const archiveScenario = async (scenario: ProductEconomicsScenario) => {
    setSaving(true);
    setError(null);
    try {
      await apiFetch(`/products/${product.id}/economics/${scenario.id}`, { method: "DELETE" });
      const remaining = scenarios.filter((row) => row.id !== scenario.id);
      setScenarios(remaining);
      setSelectedId(remaining[0]?.id || null);
      setEditing(false);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "The scenario could not be archived.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <section className="economics-planner">
      <div className="economics-head">
        <div><span className="economics-icon"><Calculator size={17} /></span><div><h3>Test economics</h3><p>User-entered planning inputs · no supplier costs inferred</p></div></div>
        <button className="button secondary" onClick={beginNew}><Plus size={14} />New scenario</button>
      </div>
      {loading && <div className="identity-review-loading"><LoaderCircle className="spin" size={16} />Loading scenarios…</div>}
      {error && <div className="ad-search-error"><AlertCircle size={15} />{error}</div>}

      {!loading && scenarios.length > 0 && !editing && (
        <>
          <div className="economics-scenario-tabs">
            {scenarios.map((scenario) => <button key={scenario.id} className={selected?.id === scenario.id ? "active" : ""} onClick={() => setSelectedId(scenario.id)}>{scenario.name}<small>r{scenario.revision}</small></button>)}
          </div>
          {selected && (
            <div className="economics-result">
              <div className={`economics-verdict ${selected.calculation.status}`}><StatusPill status={selected.calculation.status} /><div><b>{selected.calculation.label}</b><p>{selected.calculation.explanation}</p></div></div>
              <div className="economics-metrics">
                <div><span>Variable cost</span><b>{moneyRange(selected.calculation.landed_variable_cost_low, selected.calculation.landed_variable_cost_high, selected.currency)}</b><small>Product, shipping, fulfillment, other</small></div>
                <div><span>Pre-ad contribution</span><b>{moneyRange(selected.calculation.pre_ad_contribution_low, selected.calculation.pre_ad_contribution_high, selected.currency)}</b><small>{(Number(selected.calculation.contribution_margin_low) * 100).toFixed(1)}%–{(Number(selected.calculation.contribution_margin_high) * 100).toFixed(1)}% margin</small></div>
                <div><span>Break-even CPA</span><b>{moneyRange(selected.calculation.break_even_cpa_low, selected.calculation.break_even_cpa_high, selected.currency)}</b><small>Before target profit reserve</small></div>
                <div><span>Break-even ROAS</span><b>{ratioRange(selected.calculation.break_even_roas_low, selected.calculation.break_even_roas_high)}</b><small>Revenue ÷ break-even CPA</small></div>
                <div><span>Target CPA</span><b>{moneyRange(selected.calculation.target_cpa_low, selected.calculation.target_cpa_high, selected.currency)}</b><small>Reserves {(Number(selected.target_profit_margin) * 100).toFixed(0)}% profit margin</small></div>
                <div><span>Target ROAS</span><b>{ratioRange(selected.calculation.target_roas_low, selected.calculation.target_roas_high)}</b><small>Required at target margin</small></div>
              </div>
              <div className="economics-notice"><CircleHelp size={15} /><span>{selected.calculation.formula_notice}</span></div>
              <footer><span>{selected.input_source.replaceAll("_", " ")} · {selected.version} · updated {formatDate(selected.updated_at)}</span><div><button className="text-button" disabled={saving} onClick={() => archiveScenario(selected)}>Archive</button><button className="button secondary" onClick={() => beginEdit(selected)}>Edit assumptions</button></div></footer>
            </div>
          )}
        </>
      )}

      {!loading && !scenarios.length && !editing && <div className="economics-empty"><Calculator size={22} /><div><b>Plan a controlled product test</b><p>Enter your own cost range to calculate contribution, break-even CPA/ROAS, and target acquisition limits.</p></div><button className="button primary" onClick={beginNew}>Build scenario</button></div>}

      {editing && (
        <form className="economics-form" onSubmit={saveScenario}>
          <div className="economics-form-grid">
            <label className="wide">Scenario name<input required value={form.name} onChange={(event) => setValue("name", event.target.value)} /></label>
            <label>Currency<input required maxLength={10} value={form.currency} onChange={(event) => setValue("currency", event.target.value.toUpperCase())} /></label>
            <label>Selling price<input required min="0.01" step="0.01" type="number" value={form.sellingPrice} onChange={(event) => setValue("sellingPrice", event.target.value)} /></label>
            {[
              ["Product cost", "productCostLow", "productCostHigh"],
              ["Shipping", "shippingCostLow", "shippingCostHigh"],
              ["Fulfillment", "fulfillmentCostLow", "fulfillmentCostHigh"],
              ["Other variable cost", "otherCostLow", "otherCostHigh"],
            ].map(([label, low, high]) => <div className="economics-range-field" key={label}><span>{label}</span><label>Low<input min="0" step="0.01" type="number" value={form[low as keyof EconomicsFormState]} onChange={(event) => setValue(low as keyof EconomicsFormState, event.target.value)} /></label><label>High<input min="0" step="0.01" type="number" value={form[high as keyof EconomicsFormState]} onChange={(event) => setValue(high as keyof EconomicsFormState, event.target.value)} /></label></div>)}
            <label>Payment fee %<input min="0" max="100" step="0.01" type="number" value={form.paymentFeePercent} onChange={(event) => setValue("paymentFeePercent", event.target.value)} /></label>
            <label>Fixed payment fee<input min="0" step="0.01" type="number" value={form.paymentFeeFixed} onChange={(event) => setValue("paymentFeeFixed", event.target.value)} /></label>
            <label>Refund allowance %<input min="0" max="100" step="0.1" type="number" value={form.refundPercent} onChange={(event) => setValue("refundPercent", event.target.value)} /></label>
            <label>Target profit margin %<input min="0" max="99" step="0.1" type="number" value={form.targetMarginPercent} onChange={(event) => setValue("targetMarginPercent", event.target.value)} /></label>
            <label className="full">Notes<textarea rows={2} value={form.notes} onChange={(event) => setValue("notes", event.target.value)} placeholder="Source and rationale for your assumptions…" /></label>
          </div>
          <div className="economics-input-boundary"><ShieldCheck size={15} /><span>All values are labeled user-entered. Saving an edit creates a new immutable revision.</span></div>
          <footer><button type="button" className="button secondary" onClick={() => setEditing(false)}>Cancel</button><button className="button primary" disabled={saving}>{saving ? <LoaderCircle className="spin" size={14} /> : <Save size={14} />}{saving ? "Saving" : selectedId ? "Save new revision" : "Save scenario"}</button></footer>
        </form>
      )}
    </section>
  );
}

function ProductDrawer({
  product,
  onClose,
}: {
  product: LocalProduct;
  onClose: () => void;
}) {
  useEffect(() => {
    const handleEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handleEscape);
    return () => window.removeEventListener("keydown", handleEscape);
  }, [onClose]);
  return (
    <div className="drawer-layer">
      <button
        className="drawer-scrim"
        onClick={onClose}
        aria-label="Close product details"
      />
      <aside
        className="product-drawer real-product-drawer"
        role="dialog"
        aria-modal="true"
        aria-label={`${product.title} catalog evidence`}
      >
        <header>
          <button
            className="icon-button"
            onClick={onClose}
            aria-label="Close product details"
          >
            <X size={18} />
          </button>
          <span>Catalog evidence</span>
          <button
            className="icon-button"
            aria-label={`Open ${product.title}`}
            onClick={() =>
              window.open(product.canonical_url, "_blank", "noopener")
            }
          >
            <ExternalLink size={17} />
          </button>
        </header>
        <div className="real-product-hero">
          {product.image_url ? (
            <img src={product.image_url} alt="" />
          ) : (
            <ShoppingBag size={58} />
          )}
        </div>
        <div className="drawer-content">
          <div className="drawer-tags">
            <span>Observed</span>
            <span>{product.store_domain}</span>
          </div>
          <div className="product-shortlist-action"><InvestigationAction entityType="product" entityId={product.id} /></div>
          <h2>{product.title}</h2>
          <a href={product.canonical_url} target="_blank" rel="noreferrer">
            {product.canonical_url} <ExternalLink size={13} />
          </a>
          <div className="drawer-metrics">
            <div>
              <span>Current observed price</span>
              <b>{formatMoney(product.price_min, product.currency)}</b>
              <small>
                {product.price_max !== product.price_min
                  ? `maximum ${formatMoney(product.price_max, product.currency)}`
                  : "Public catalog observation"}
              </small>
            </div>
            <div>
              <span>First observed</span>
              <b>
                {product.first_seen_at
                  ? formatDate(product.first_seen_at)
                  : "Not recorded"}
              </b>
              <small>Not the product launch date</small>
            </div>
            <div>
              <span>Demand conclusion</span>
              <b>Insufficient data</b>
              <small>Presence alone does not imply sales</small>
            </div>
          </div>
          <section className="evidence-card">
            <div>
              <h3>What this record supports</h3>
              <span>Observed fact</span>
            </div>
            <ul className="catalog-proof-list">
              <li>
                <CheckCircle2 size={15} />
                <span>The product appeared on a public storefront page.</span>
              </li>
              <li>
                <CheckCircle2 size={15} />
                <span>The displayed price was collected from that page.</span>
              </li>
            </ul>
          </section>
          <ProductEconomicsPlanner product={product} />
          <section className="why-card catalog-limitations-card">
            <h3>
              <AlertCircle size={16} />
              What this record does not prove
            </h3>
            <ul>
              <li>That the product has sold or is currently gaining demand.</li>
              <li>That availability changes represent customer purchases.</li>
              <li>
                That the displayed price is a profitable or effective offer.
              </li>
            </ul>
            <p className="drawer-empty-copy">
              Open this product from a Store Intelligence Report once Northstar
              has advertising, traffic, review, historical, or competitor
              evidence.
            </p>
          </section>
        </div>
      </aside>
    </div>
  );
}

function ScanModal({
  onClose,
  onSubmit,
}: {
  onClose: () => void;
  onSubmit: (url: string) => Promise<void>;
}) {
  const [url, setUrl] = useState("");
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    const handleEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape" && !busy) onClose();
    };
    window.addEventListener("keydown", handleEscape);
    return () => window.removeEventListener("keydown", handleEscape);
  }, [busy, onClose]);
  return (
    <div className="modal-layer">
      <button
        className="modal-scrim"
        onClick={onClose}
        aria-label="Close scan dialog"
      />
      <form
        className="modal-card"
        role="dialog"
        aria-modal="true"
        aria-labelledby="scan-dialog-title"
        onSubmit={async (event) => {
          event.preventDefault();
          if (!url.trim()) return;
          setBusy(true);
          try {
            await onSubmit(url.trim());
          } finally {
            setBusy(false);
          }
        }}
      >
        <div className="modal-icon">
          <Radar size={24} />
        </div>
        <button
          type="button"
          className="icon-button modal-close"
          onClick={onClose}
        >
          <X size={18} />
        </button>
        <h2 id="scan-dialog-title">Scan a public store or product</h2>
        <p>
          Northstar will respect robots.txt, collect public catalog fields, and
          save an observed snapshot locally.
        </p>
        <div className="scan-mode scan-live">
          <span />
          <b>Live local crawler</b> · real records only
        </div>
        <label>
          Public URL
          <div className="url-input">
            <Globe2 size={16} />
            <input
              autoFocus
              value={url}
              onChange={(event) => setUrl(event.target.value)}
              placeholder="https://example-store.com"
            />
          </div>
        </label>
        <div className="modal-checks">
          <span>
            <Check size={14} />
            Public pages only
          </span>
          <span>
            <Check size={14} />
            Robots-aware
          </span>
          <span>
            <Check size={14} />
            Local persistence
          </span>
        </div>
        <footer>
          <button type="button" className="button secondary" onClick={onClose}>
            Cancel
          </button>
          <button className="button primary" disabled={busy || !url.trim()}>
            {busy ? (
              <>
                <LoaderCircle className="spin" size={15} />
                Submitting
              </>
            ) : (
              <>
                <Radar size={16} />
                Start real scan
              </>
            )}
          </button>
        </footer>
      </form>
    </div>
  );
}

function ToastMessage({
  toast,
  onClose,
}: {
  toast: NonNullable<Toast>;
  onClose: () => void;
}) {
  return (
    <div className={`toast ${toast.tone === "error" ? "toast-error" : ""}`}>
      <span>
        {toast.tone === "error" ? (
          <AlertCircle size={15} />
        ) : (
          <Check size={15} />
        )}
      </span>
      <div>
        <b>{toast.title}</b>
        {toast.body && <p>{toast.body}</p>}
      </div>
      <button onClick={onClose}>
        <X size={15} />
      </button>
    </div>
  );
}

export default function App() {
  const initialRoute = useMemo(parseLocationRoute, []);
  const [view, setView] = useState<View>(initialRoute.view);
  const [reportStoreId, setReportStoreId] = useState<number | null>(
    initialRoute.storeId,
  );
  const [reportAdId, setReportAdId] = useState<number | null>(initialRoute.adId);
  const [reportTab, setReportTab] = useState<ReportTab>(initialRoute.reportTab);
  const [apiStatus, setApiStatus] = useState<ApiStatus>("checking");
  const [library, setLibrary] = useState<LocalLibraryData>(emptyLibrary);
  const [ads, setAds] = useState<RealAd[]>([]);
  const [integrations, setIntegrations] = useState<IntegrationStatus | null>(
    null,
  );
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [scanOpen, setScanOpen] = useState(false);
  const [selectedProduct, setSelectedProduct] = useState<LocalProduct | null>(
    null,
  );
  const [toast, setToast] = useState<Toast>(null);
  const [metaSearching, setMetaSearching] = useState(false);
  const [trafficRefreshingStoreId, setTrafficRefreshingStoreId] = useState<
    number | null
  >(null);
  const trafficRefreshesInFlight = useRef(new Set<number>());

  const refresh = async (quiet = false) => {
    try {
      await apiFetch("/snapshots/health");
      if (!getToken()) await localLogin();
      else await apiFetch("/auth/me").catch(() => localLogin());
      const [libraryData, adData, metaStatus, gethookdStatus, similarwebStatus] =
        await Promise.all([
          apiFetch<LocalLibraryData>("/library"),
          apiFetch<RealAd[]>(
            "/ads?sort=newest",
          ),
          apiFetch<IntegrationProviderStatus>(
            "/integrations/meta/status",
          ).catch(() => null),
          apiFetch<IntegrationProviderStatus>(
            "/integrations/gethookd/status",
          ).catch(() => null),
          apiFetch<IntegrationProviderStatus>(
            "/integrations/similarweb/status",
          ).catch(() => null),
        ]);
      setLibrary(libraryData);
      setAds(adData);
      setIntegrations({
        meta: metaStatus || { configured: false },
        gethookd: gethookdStatus || { configured: false },
        similarweb: similarwebStatus || { configured: false },
      });
      setApiStatus("connected");
    } catch {
      setApiStatus("offline");
      if (!quiet)
        setToast({
          title: "Local engine is offline",
          body: "Run start-northstar.ps1 and this page will reconnect automatically.",
          tone: "error",
        });
    }
  };

  useEffect(() => {
    refresh(true);
    const intervalMs = library.summary.active_jobs > 0 ? 3000 : 30000;
    const timer = window.setInterval(() => {
      if (document.visibilityState === "visible") refresh(true);
    }, intervalMs);
    return () => window.clearInterval(timer);
  }, [library.summary.active_jobs]);

  useEffect(() => {
    const handleHistoryNavigation = () => {
      const route = parseLocationRoute();
      setView(route.view);
      setReportStoreId(route.storeId);
      setReportAdId(route.adId);
      setReportTab(route.reportTab);
      setSelectedProduct(null);
      window.scrollTo({ top: 0 });
    };
    window.addEventListener("popstate", handleHistoryNavigation);
    return () =>
      window.removeEventListener("popstate", handleHistoryNavigation);
  }, []);

  const navigate = (next: View) => {
    if (next === "store-report" || next === "ad-detail") return;
    const pathByView: Record<Exclude<View, "store-report" | "ad-detail">, string> = {
      overview: "/",
      products: "/shopify-product",
      stores: "/stores",
      ads: "/library-product",
      shortlist: "/shortlist",
      compare: "/compare",
      settings: "/settings",
    };
    setView(next);
    setReportStoreId(null);
    setReportAdId(null);
    window.history.pushState({}, "", pathByView[next]);
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  const openStoreReport = (storeId: number, tab: ReportTab = "overview") => {
    setView("store-report");
    setReportStoreId(storeId);
    setReportAdId(null);
    setReportTab(tab);
    setSelectedProduct(null);
    window.history.pushState({}, "", `/stores/${storeId}/${tab}`);
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  const openAdAutopsy = (adId: number) => {
    setView("ad-detail");
    setReportStoreId(null);
    setReportAdId(adId);
    setSelectedProduct(null);
    window.history.pushState({}, "", `/ads/${adId}`);
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  const openInvestigationEntity = (item: InvestigationItem) => {
    if (item.entity_type === "store") {
      openStoreReport(item.entity_id);
      return;
    }
    if (item.entity_type === "ad") {
      openAdAutopsy(item.entity_id);
      return;
    }
    const product = library.products.find((row) => row.id === item.entity_id);
    if (product) setSelectedProduct(product);
    else window.open(item.entity_url, "_blank", "noopener");
  };

  const changeReportTab = (tab: ReportTab) => {
    if (reportStoreId == null) return;
    setReportTab(tab);
    window.history.pushState({}, "", `/stores/${reportStoreId}/${tab}`);
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  const submitScan = async (rawUrl: string) => {
    const url = /^https?:\/\//i.test(rawUrl) ? rawUrl : `https://${rawUrl}`;
    try {
      const result = await apiFetch<{
        job_id: string;
        store_id?: number | null;
      }>("/ingest/url", {
        method: "POST",
        body: JSON.stringify({ url }),
      });
      setScanOpen(false);
      setToast({
        title: "Real scan queued",
        body: result.store_id
          ? `Opening the intelligence report while job ${result.job_id.slice(0, 8)} collects new evidence.`
          : `Job ${result.job_id.slice(0, 8)} is collecting ${url}. The store will appear when it is identified.`,
      });
      if (result.store_id) openStoreReport(result.store_id);
      else navigate("stores");
      await refresh(true);
    } catch {
      setToast({
        title: "Scan was rejected",
        body: "Check that the URL is a valid public HTTP or HTTPS storefront.",
        tone: "error",
      });
    }
  };

  const searchMeta = async (query: string, country: string) => {
    setMetaSearching(true);
    try {
      const result = await apiFetch<MetaSearchResult>("/ads/meta/search", {
        method: "POST",
        body: JSON.stringify({
          search_terms: query,
          ad_reached_countries: [country],
          ad_type: "ALL",
          ad_active_status: "ACTIVE",
          limit: 50,
        }),
      });
      await refresh(true);
      const imported = result.inserted_count + result.updated_count;
      setToast({
        title: `Meta returned ${result.fetched_count} ads`,
        body: `${imported} imported (${result.inserted_count} new, ${result.updated_count} updated); ${result.skipped_count} skipped.`,
      });
    } catch (error) {
      setToast({
        title: "Meta search failed",
        body:
          error instanceof Error
            ? error.message
            : "The token may be missing, expired, or ineligible for this Ad Library query.",
        tone: "error",
      });
    } finally {
      setMetaSearching(false);
    }
  };

  const saveIntegration = async (
    provider: "meta" | "gethookd" | "similarweb",
    key: string,
  ) => {
    try {
      await apiFetch(`/integrations/${provider}/config`, {
        method: "PUT",
        body: JSON.stringify(
          provider === "meta"
            ? { access_token: key }
            : provider === "gethookd"
              ? { api_token: key }
              : { api_key: key },
        ),
      });
      setToast({
        title: `${provider === "meta" ? "Meta" : provider === "gethookd" ? "GetHookd" : "Similarweb"} credential saved`,
        body: "The credential is stored only in the local Northstar data directory.",
      });
      await refresh(true);
    } catch (error) {
      setToast({
        title: "Credential could not be saved",
        body:
          error instanceof Error
            ? error.message
            : "The integration endpoint rejected the credential.",
        tone: "error",
      });
    }
  };

  const removeIntegration = async (provider: "meta" | "gethookd" | "similarweb") => {
    try {
      await apiFetch(`/integrations/${provider}/config`, { method: "DELETE" });
      setToast({
        title: `${provider === "meta" ? "Meta" : provider === "gethookd" ? "GetHookd" : "Similarweb"} disconnected`,
      });
      await refresh(true);
    } catch {
      setToast({ title: "Could not remove credential", tone: "error" });
    }
  };

  const refreshTraffic = async (store: LocalStore) => {
    if (trafficRefreshesInFlight.current.has(store.id)) return;
    trafficRefreshesInFlight.current.add(store.id);
    setTrafficRefreshingStoreId(store.id);
    try {
      const result = await apiFetch<TrafficData>(
        `/traffic/stores/${store.id}/refresh`,
        { method: "POST" },
      );
      await refresh(true);
      const period = trafficPeriod(result);
      const issue = trafficIssue(result);
      if (result.fetch_status === "success") {
        setToast({
          title: "Traffic data saved",
          body: `${store.domain}${period ? ` · period ${period}` : ""}.`,
        });
      } else if (result.fetch_status === "partial") {
        setToast({
          title: "Partial provider data saved",
          body: issue || "Similarweb returned only one requested metric.",
        });
      } else {
        setToast({
          title: "Provider data unavailable",
          body:
            issue ||
            "Similarweb did not return visits or global rank for this request.",
          tone: "error",
        });
      }
    } catch (error) {
      setToast({
        title: "Traffic request failed",
        body:
          error instanceof Error
            ? error.message
            : "Check the Similarweb key and its endpoint capabilities.",
        tone: "error",
      });
    } finally {
      trafficRefreshesInFlight.current.delete(store.id);
      setTrafficRefreshingStoreId((current) =>
        current === store.id ? null : current,
      );
    }
  };

  return (
    <div className="app-shell">
      <Sidebar
        view={view}
        open={sidebarOpen}
        onNavigate={navigate}
        onClose={() => setSidebarOpen(false)}
      />
      <div className="app-frame">
        <Header
          apiStatus={apiStatus}
          onMenu={() => setSidebarOpen(true)}
          onRefresh={() => refresh()}
        />
        <main className="main-area">
          {apiStatus === "offline" && view !== "settings" ? (
            <div className="page-content">
              <EmptyState
                icon={WifiOff}
                title="Local engine is offline"
                body="Start Northstar with start-northstar.ps1. This screen will reconnect automatically and remain empty until real records are available."
                action={
                  <button
                    className="button secondary"
                    onClick={() => refresh()}
                  >
                    Retry connection
                  </button>
                }
              />
            </div>
          ) : (
            <>
              {view === "overview" && (
                <OverviewPage
                  library={library}
                  integrations={integrations}
                  onScan={() => setScanOpen(true)}
                  onNavigate={navigate}
                  onOpenStore={openStoreReport}
                />
              )}
              {view === "products" && (
                <ProductsPage
                  products={library.products}
                  onScan={() => setScanOpen(true)}
                  onOpen={setSelectedProduct}
                />
              )}
              {view === "stores" && (
                <StoresPage
                  stores={library.stores}
                  trafficConfigured={isConfigured(integrations, "similarweb")}
                  onScan={() => setScanOpen(true)}
                  onOpenReport={openStoreReport}
                  onRefreshTraffic={refreshTraffic}
                  onSettings={() => navigate("settings")}
                  refreshingStoreId={trafficRefreshingStoreId}
                />
              )}
              {view === "store-report" && reportStoreId != null && (
                <StoreIntelligenceReport
                  storeId={reportStoreId}
                  tab={reportTab}
                  onTabChange={changeReportTab}
                  onBack={() => navigate("stores")}
                  onScan={() => setScanOpen(true)}
                />
              )}
              {view === "ads" && (
                <AdsPage
                  ads={ads}
                  metaConfigured={isConfigured(integrations, "meta")}
                  gethookdConfigured={isConfigured(integrations, "gethookd")}
                  onSearchMeta={searchMeta}
                  onImported={() => refresh(true)}
                  onSettings={() => navigate("settings")}
                  searching={metaSearching}
                  onOpenAd={openAdAutopsy}
                />
              )}
              {view === "ad-detail" && reportAdId != null && (
                <AdAutopsyPage
                  adId={reportAdId}
                  onBack={() => navigate("ads")}
                  onOpenAd={openAdAutopsy}
                  onOpenStore={openStoreReport}
                  onInvestigate={submitScan}
                />
              )}
              {view === "shortlist" && (
                <ShortlistPage onOpen={openInvestigationEntity} />
              )}
              {view === "compare" && (
                <ProductComparisonPage products={library.products} />
              )}
              {view === "settings" && (
                <SettingsPage
                  apiStatus={apiStatus}
                  integrations={integrations}
                  onSaveIntegration={saveIntegration}
                  onRemoveIntegration={removeIntegration}
                />
              )}
            </>
          )}
        </main>
      </div>
      {scanOpen && (
        <ScanModal onClose={() => setScanOpen(false)} onSubmit={submitScan} />
      )}
      {selectedProduct && (
        <ProductDrawer
          product={selectedProduct}
          onClose={() => setSelectedProduct(null)}
        />
      )}
      {toast && <ToastMessage toast={toast} onClose={() => setToast(null)} />}
    </div>
  );
}
