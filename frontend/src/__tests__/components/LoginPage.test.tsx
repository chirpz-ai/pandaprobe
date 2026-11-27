import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import LoginPage from "@/app/(auth)/login/page";

const mockAuthenticate = jest.fn();
jest.mock("next/navigation", () => ({
  useRouter: () => ({ push: jest.fn() }),
  useSearchParams: () => new URLSearchParams(),
}));
jest.mock("@/components/providers/AuthProvider", () => ({
  useAuth: () => ({
    authEnabled: true,
    signInWithEmail: mockAuthenticate,
    signUpWithEmail: mockAuthenticate,
  }),
}));
jest.mock("@/lib/auth/auth-service", () => ({ resetPassword: jest.fn() }));

it.each(["Sign in", "Create account"])(
  "can reveal and hide the password before submitting %s",
  async (submitLabel) => {
    mockAuthenticate.mockClear();
    const user = userEvent.setup();
    render(<LoginPage />);
    if (submitLabel === "Create account") {
      await user.click(screen.getByRole("button", { name: "Create one" }));
    }

    const password = screen.getByPlaceholderText("Password");
    expect(password).toHaveAttribute("type", "password");
    await user.type(screen.getByPlaceholderText("Email"), "user@example.com");
    await user.type(password, "test-password");
    await user.click(screen.getByRole("button", { name: "Show password" }));
    expect(password).toHaveAttribute("type", "text");
    expect(password).toHaveValue("test-password");

    await user.tab();
    expect(screen.getByRole("button", { name: "Hide password" })).toHaveFocus();
    await user.keyboard("{Enter}");
    expect(password).toHaveAttribute("type", "password");
    expect(mockAuthenticate).not.toHaveBeenCalled();

    await user.click(screen.getByRole("button", { name: submitLabel }));
    expect(mockAuthenticate).toHaveBeenCalledWith(
      "user@example.com",
      "test-password",
    );
  },
);

it("masks a revealed password when switching between sign-in and sign-up", async () => {
  const user = userEvent.setup();
  render(<LoginPage />);
  await user.click(screen.getByRole("button", { name: "Show password" }));
  await user.click(screen.getByRole("button", { name: "Create one" }));
  expect(screen.getByPlaceholderText("Password")).toHaveAttribute(
    "type",
    "password",
  );
  await user.click(screen.getByRole("button", { name: "Show password" }));
  await user.click(screen.getByRole("button", { name: "Sign in" }));
  expect(screen.getByPlaceholderText("Password")).toHaveAttribute(
    "type",
    "password",
  );
});
