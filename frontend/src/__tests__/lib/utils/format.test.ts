import {
  formatDuration,
  formatCost,
  formatTokens,
  formatNumber,
  formatPercent,
} from "@/lib/utils/format";

describe("formatDuration", () => {
  it('returns "—" for null/undefined', () => {
    expect(formatDuration(null)).toBe("—");
    expect(formatDuration(undefined)).toBe("—");
  });

  it("formats milliseconds", () => {
    expect(formatDuration(42)).toBe("42ms");
  });

  it("formats seconds", () => {
    expect(formatDuration(1500)).toBe("1.5s");
  });

  it("formats minutes", () => {
    expect(formatDuration(125000)).toBe("2m 5s");
  });
});

describe("formatCost", () => {
  it('returns "—" for null/undefined', () => {
    expect(formatCost(null)).toBe("—");
  });

  it('returns "$0.00" for zero', () => {
    expect(formatCost(0)).toBe("$0.00");
  });

  it("shows 4 decimal places for small amounts", () => {
    expect(formatCost(0.0012)).toBe("$0.0012");
  });

  it("shows 2 decimal places for normal amounts", () => {
    expect(formatCost(5.99)).toBe("$5.99");
  });
});

describe("formatTokens", () => {
  it('returns "—" for null/undefined', () => {
    expect(formatTokens(null)).toBe("—");
  });

  it("returns raw number for < 1000", () => {
    expect(formatTokens(500)).toBe("500");
  });

  it("formats thousands", () => {
    expect(formatTokens(1500)).toBe("1.5K");
  });

  it("formats millions", () => {
    expect(formatTokens(1_500_000)).toBe("1.50M");
  });
});

describe("formatNumber", () => {
  it("formats with locale separators", () => {
    expect(formatNumber(1234567)).toBe("1,234,567");
  });
});

describe("formatPercent", () => {
  it("formats as percentage", () => {
    expect(formatPercent(0.856)).toBe("85.6%");
  });
});
