// T217 (FR-105, A8): add a passkey, then sign in with it alone, with Chrome's virtual
// authenticator against the local fake sign-in.

import { expect, test, type Page } from "@playwright/test";

test.skip(!!process.env.BASE_URL, "needs the local fake sign-in");

async function signInWithCode(page: Page, address: string) {
  await page.goto("/account");
  await page.getByRole("button", { name: "Yes, I am 16 or older" }).click();
  await page.getByLabel("E-mail address").fill(address);
  await page.getByRole("button", { name: "Send me a code" }).click();
  await page.getByLabel("Code").fill("123456");
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByRole("heading", { level: 1, name: "Your account" })).toBeVisible();
}

test("add a passkey, then sign in with it instead of a code", async ({ page }) => {
  const cdp = await page.context().newCDPSession(page);
  await cdp.send("WebAuthn.enable");
  await cdp.send("WebAuthn.addVirtualAuthenticator", {
    options: {
      protocol: "ctap2",
      transport: "internal",
      hasResidentKey: true,
      hasUserVerification: true,
      isUserVerified: true,
      automaticPresenceSimulation: true,
    },
  });

  const address = `passkey-${crypto.randomUUID().slice(0, 8)}@example.test`;
  await signInWithCode(page, address);
  await page.getByRole("button", { name: "Add a passkey" }).click();
  await expect(page.getByRole("status")).toContainText("Passkey added.");
  await expect(page.getByRole("button", { name: "Remove Passkey" })).toBeVisible();

  // Signed out on this tab (sign-out itself comes with US6): no tokens left.
  await page.evaluate(() => {
    sessionStorage.removeItem("staysharp.session");
    localStorage.removeItem("staysharp.refresh");
  });
  await page.goto("/account");
  await page.getByRole("button", { name: "Yes, I am 16 or older" }).click();
  await page.getByLabel("E-mail address").fill(address);
  await page.getByRole("button", { name: "Sign in with a passkey instead" }).click();
  await expect(page.getByRole("heading", { level: 1, name: "Your account" })).toBeVisible();
  await expect(page.getByText(`Signed in as ${address}.`)).toBeVisible();
});
