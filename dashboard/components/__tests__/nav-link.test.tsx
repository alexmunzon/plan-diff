import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { NavLink } from "@/components/nav-link";

vi.mock("next/navigation", () => ({ usePathname: () => "/" }));

describe("NavLink", () => {
  it("marks the current page and shows unbuilt pages as text, not links", () => {
    render(
      <>
        <NavLink href="/" label="Overview" />
        <NavLink label="Trust" />
      </>,
    );
    expect(screen.getByRole("link", { name: "Overview" })).toHaveAttribute("aria-current", "page");
    expect(screen.queryByRole("link", { name: /Trust/ })).not.toBeInTheDocument();
    expect(screen.getByText("Trust")).toHaveAttribute("aria-disabled", "true");
    expect(screen.getByText("(coming soon)")).toBeInTheDocument();
  });
});
