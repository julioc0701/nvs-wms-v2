export async function waitForPlanningPage(page) {
  await page.waitForLoadState('domcontentloaded');

  const loaded = await Promise.race([
    page
      .getByText(/Planeje seu envio para o Full|Planejamento de envios|Estoque para enviar/i)
      .first()
      .waitFor({ timeout: 30000 })
      .then(() => true)
      .catch(() => false),
    page
      .getByText(/Entre|Digite seu e-mail|E-mail, telefone ou usuário|Identifique-se/i)
      .first()
      .waitFor({ timeout: 30000 })
      .then(() => false)
      .catch(() => null),
  ]);

  if (loaded === true) return 'planning';
  if (loaded === false) return 'login';

  const url = page.url();
  if (/login|registration|identification/i.test(url)) return 'login';
  return 'unknown';
}

export async function getPlanningSummary(page) {
  const resultText = await page
    .locator('text=/\\d+\\s+resultados/i')
    .first()
    .textContent({ timeout: 5000 })
    .catch(() => null);

  const inputCount = await page.locator('input').count().catch(() => 0);
  const continueVisible = await page
    .getByRole('button', { name: /^Continuar$/i })
    .isVisible()
    .catch(() => false);

  return {
    url: page.url(),
    resultText,
    inputCount,
    continueVisible,
  };
}
