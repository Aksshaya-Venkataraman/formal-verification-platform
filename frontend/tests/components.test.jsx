import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import AuthForm from "../src/components/AuthForm.jsx";
import { ResultsTable, StatusBadge } from "../src/components/Results.jsx";

vi.mock("../src/api.js", () => ({
  api: {
    login: vi.fn(async (email) => {
      if (email === "bad@example.com") {
        const err = new Error("Invalid email or password.");
        err.body = { error: "invalid_credentials" };
        throw err;
      }
      return { user: { email } };
    }),
    register: vi.fn(),
  },
}));

afterEach(cleanup);

describe("results", () => {
  const run = {
    verdict: "theorem",
    results: [
      { prover: "vampire", status: "Theorem", seconds: 0.12, output: "<img src=x onerror=alert(1)>" },
      { prover: "otter", status: "Timeout", seconds: 10, output: "" },
    ],
  };

  it("shows the verdict and one row per prover", () => {
    render(<ResultsTable run={run} />);
    expect(screen.getByRole("status").textContent).toContain("Proved");
    expect(screen.getAllByRole("row")).toHaveLength(3);
    expect(screen.getByText("0.12 s")).toBeTruthy();
  });

  it("renders prover output as text, never as HTML", () => {
    const { container } = render(<ResultsTable run={run} />);
    expect(container.querySelector("img")).toBeNull();
    expect(screen.getByText("<img src=x onerror=alert(1)>")).toBeTruthy();
  });

  it("colours statuses by meaning", () => {
    const { container } = render(<StatusBadge status="CounterSatisfiable" />);
    expect(container.firstChild.className).toContain("warn");
  });
});

describe("auth form", () => {
  it("logs in and reports the user", async () => {
    const onAuthenticated = vi.fn();
    render(<AuthForm onAuthenticated={onAuthenticated} />);
    await userEvent.type(screen.getByLabelText("Email"), "ada@example.com");
    await userEvent.type(screen.getByLabelText("Password"), "a-long-passphrase");
    await userEvent.click(screen.getByRole("button", { name: "Log in" }));
    expect(onAuthenticated).toHaveBeenCalledWith({ email: "ada@example.com" });
  });

  it("shows the server's error message", async () => {
    render(<AuthForm onAuthenticated={vi.fn()} />);
    await userEvent.type(screen.getByLabelText("Email"), "bad@example.com");
    await userEvent.type(screen.getByLabelText("Password"), "wrong-password");
    await userEvent.click(screen.getByRole("button", { name: "Log in" }));
    expect((await screen.findByRole("alert")).textContent).toBe("Invalid email or password.");
  });
});
