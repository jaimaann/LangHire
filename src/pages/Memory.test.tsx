import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import Memory from "./Memory";
import {
  getMemoryStats,
  getMemoryDomains,
  getMemoriesForDomain,
  searchMemories,
  cleanupMemories,
  decayMemories,
  exportMemories,
} from "../lib/api";
import { trackEvent } from "../lib/analytics";
import type { DomainInfo, Memory as MemoryType } from "../lib/types";

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (k: string, o?: Record<string, unknown>) =>
      o ? `${k}:${JSON.stringify(o)}` : k,
    i18n: { changeLanguage: vi.fn() },
  }),
}));

vi.mock("../lib/analytics", () => ({ trackEvent: vi.fn() }));
vi.mock("../lib/perf", () => ({ markStart: vi.fn(), measureAndTrack: vi.fn() }));

vi.mock("../lib/api", () => ({
  getMemoryStats: vi.fn(),
  getMemoryDomains: vi.fn(),
  getMemoriesForDomain: vi.fn(),
  searchMemories: vi.fn(),
  cleanupMemories: vi.fn(),
  decayMemories: vi.fn(),
  exportMemories: vi.fn(),
}));

const mockGetMemoryStats = vi.mocked(getMemoryStats);
const mockGetMemoryDomains = vi.mocked(getMemoryDomains);
const mockGetMemoriesForDomain = vi.mocked(getMemoriesForDomain);
const mockSearchMemories = vi.mocked(searchMemories);
const mockCleanupMemories = vi.mocked(cleanupMemories);
const mockDecayMemories = vi.mocked(decayMemories);
const mockExportMemories = vi.mocked(exportMemories);
const mockTrackEvent = vi.mocked(trackEvent);

const domains: DomainInfo[] = [
  {
    website_domain: "greenhouse.io",
    ats_platform: "Greenhouse",
    count: 12,
    avg_confidence: 0.85,
    success_count: 10,
    failure_count: 2,
  },
  {
    website_domain: "lever.co",
    ats_platform: "Lever",
    count: 5,
    avg_confidence: 0.7,
    success_count: 4,
    failure_count: 1,
  },
];

function makeMemory(over: Partial<MemoryType> = {}): MemoryType {
  return {
    id: 1,
    website_domain: "greenhouse.io",
    ats_platform: "Greenhouse",
    category: "navigation",
    content: "Click the apply button at the top right.",
    success: true,
    confidence: 0.9,
    job_url: "https://job",
    created_at: "2026-01-01",
    updated_at: "2026-01-02",
    access_count: 3,
    ...over,
  };
}

describe("Memory page", () => {
  beforeEach(() => {
    mockGetMemoryStats.mockResolvedValue({
      total_memories: 17,
      unique_domains: 2,
      by_category: { navigation: 9, form_strategy: 8 },
    } as never);
    mockGetMemoryDomains.mockResolvedValue(domains as never);
    mockGetMemoriesForDomain.mockResolvedValue([
      makeMemory({ id: 1, content: "Click the apply button." }),
      makeMemory({ id: 2, content: "Fill phone with country code.", success: false }),
    ] as never);
    mockSearchMemories.mockResolvedValue([
      makeMemory({ id: 9, content: "Search hit memory.", website_domain: "lever.co" }),
    ] as never);
    mockDecayMemories.mockResolvedValue({ success: true, affected: 4 } as never);
    mockCleanupMemories.mockResolvedValue({ success: true, deleted: 2 } as never);
    mockExportMemories.mockResolvedValue([makeMemory()] as never);

    vi.spyOn(window, "confirm").mockReturnValue(true);
    vi.spyOn(window, "alert").mockImplementation(() => {});
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("shows the loading spinner before stats/domains resolve", () => {
    mockGetMemoryStats.mockReturnValue(new Promise(() => {}) as never);
    render(<Memory />);
    expect(screen.queryByText("domains.title")).not.toBeInTheDocument();
  });

  it("renders domain list and category chips after load", async () => {
    render(<Memory />);
    expect(await screen.findByText("greenhouse.io")).toBeInTheDocument();
    expect(screen.getByText("lever.co")).toBeInTheDocument();
    // Category chips ("navigation: 9").
    expect(screen.getByText("navigation: 9")).toBeInTheDocument();
  });

  it("selecting a domain loads and renders its memories", async () => {
    const user = userEvent.setup();
    render(<Memory />);
    await screen.findByText("greenhouse.io");

    await user.click(screen.getByText("greenhouse.io"));

    expect(await screen.findByText("Click the apply button.")).toBeInTheDocument();
    expect(screen.getByText("Fill phone with country code.")).toBeInTheDocument();
    expect(mockGetMemoriesForDomain).toHaveBeenCalledWith("greenhouse.io");
  });

  it("searching calls searchMemories and renders results", async () => {
    const user = userEvent.setup();
    render(<Memory />);
    await screen.findByText("greenhouse.io");

    await user.type(screen.getByPlaceholderText("search.placeholder"), "phone");
    await user.click(screen.getByRole("button", { name: "search.button" }));

    expect(await screen.findByText("Search hit memory.")).toBeInTheDocument();
    expect(mockSearchMemories).toHaveBeenCalledWith("phone");
  });

  it("decay action confirms, calls API, and tracks the event", async () => {
    const user = userEvent.setup();
    render(<Memory />);
    await screen.findByText("greenhouse.io");

    await user.click(screen.getByRole("button", { name: /actions\.decay/ }));

    await waitFor(() => expect(mockDecayMemories).toHaveBeenCalledWith(30));
    expect(mockTrackEvent).toHaveBeenCalledWith("memory_decay", { affected: 4 });
  });

  it("cleanup action confirms, calls API, and tracks the event", async () => {
    const user = userEvent.setup();
    render(<Memory />);
    await screen.findByText("greenhouse.io");

    await user.click(screen.getByRole("button", { name: /actions\.cleanup/ }));

    await waitFor(() => expect(mockCleanupMemories).toHaveBeenCalled());
    expect(mockTrackEvent).toHaveBeenCalledWith("memory_cleanup", { deleted: 2 });
  });

  it("export action fetches memories and tracks the event", async () => {
    // jsdom doesn't implement URL.createObjectURL / anchor download clicks;
    // assign stubs (spyOn can't wrap a property that doesn't exist).
    const createUrl = vi.fn(() => "blob:fake");
    URL.createObjectURL = createUrl as unknown as typeof URL.createObjectURL;
    URL.revokeObjectURL = vi.fn() as unknown as typeof URL.revokeObjectURL;
    vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});

    const user = userEvent.setup();
    render(<Memory />);
    await screen.findByText("greenhouse.io");

    await user.click(screen.getByRole("button", { name: /actions\.export/ }));

    await waitFor(() => expect(mockExportMemories).toHaveBeenCalled());
    expect(mockTrackEvent).toHaveBeenCalledWith("memory_export", { count: 1 });
    expect(createUrl).toHaveBeenCalled();
  });

  it("renders the empty-domains state when no domains exist", async () => {
    mockGetMemoryDomains.mockResolvedValue([] as never);
    mockGetMemoryStats.mockResolvedValue({
      total_memories: 0,
      unique_domains: 0,
      by_category: {},
    } as never);
    render(<Memory />);
    expect(await screen.findByText("domains.empty")).toBeInTheDocument();
  });

  it("renders gracefully (no crash, empty domains) when the initial load rejects", async () => {
    mockGetMemoryStats.mockRejectedValue(new Error("boom"));
    mockGetMemoryDomains.mockRejectedValue(new Error("boom"));
    render(<Memory />);
    // Page still mounts; the domains panel header is present.
    expect(await screen.findByText("domains.title")).toBeInTheDocument();
    expect(screen.getByText("domains.empty")).toBeInTheDocument();
  });

  it("shows empty memories message when a search returns no results", async () => {
    mockSearchMemories.mockResolvedValue([] as never);
    const user = userEvent.setup();
    render(<Memory />);
    await screen.findByText("greenhouse.io");

    await user.type(screen.getByPlaceholderText("search.placeholder"), "nothing");
    await user.click(screen.getByRole("button", { name: "search.button" }));

    expect(await screen.findByText("memories.noMemoriesFound")).toBeInTheDocument();
  });

  it("marks success/failure on individual memories", async () => {
    const user = userEvent.setup();
    render(<Memory />);
    await screen.findByText("greenhouse.io");
    await user.click(screen.getByText("greenhouse.io"));

    await screen.findByText("Click the apply button.");
    // First memory success=true, second success=false.
    expect(screen.getByText("memories.success")).toBeInTheDocument();
    expect(screen.getByText("memories.failure")).toBeInTheDocument();
  });
});
