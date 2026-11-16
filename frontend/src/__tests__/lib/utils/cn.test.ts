import { cn } from "@/lib/utils/cn";

describe("cn", () => {
  it("merges class names", () => {
    expect(cn("foo", "bar")).toBe("foo bar");
  });

  it("handles conditional classes", () => {
    expect(cn("foo", false && "bar", "baz")).toBe("foo baz");
  });

  it("resolves tailwind conflicts", () => {
    const result = cn("px-2 py-1", "px-4");
    expect(result).toContain("px-4");
    expect(result).not.toContain("px-2");
  });

  it.each(["text-caption", "text-compact"])(
    "merges %s as a font size without dropping text colors",
    (size) => {
      expect(cn("text-xs text-text-muted", size)).toBe(
        `text-text-muted ${size}`,
      );
      expect(cn(size, "text-info", "text-sm")).toBe("text-info text-sm");
    },
  );

  it("handles undefined and null", () => {
    expect(cn("foo", undefined, null, "bar")).toBe("foo bar");
  });
});
