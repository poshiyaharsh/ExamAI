import { chromium } from 'playwright';
import path from 'path';
import fs from 'fs';

const ARTIFACT_DIR = 'C:/Users/Harsh Poshiya/.gemini/antigravity-ide/brain/6827506a-a41b-43b5-85cf-09b5cead5919';
const TEST_SLUG = '517fe7271ed56a2e67304f466296cb0780157424ed08d7890603753b47be8d49';

async function runSuperAdminVerification() {
  console.log('=== STARTING SUPER ADMIN PHASE 5 VERIFICATION ===');
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext();
  const page = await context.newPage();

  const errors = [];
  page.on('console', (msg) => {
    if (msg.type() === 'error') {
      errors.push(msg.text());
    }
  });

  // TEST 1: Cloaked 404 on invalid paths
  console.log('\n[TEST 1] Testing uniform 404 on unauthenticated/fake routes...');
  // Verify backend disabled /admin/ returns 404
  const backendAdminRes = await page.request.get('http://127.0.0.1:8000/admin/');
  if (backendAdminRes.status() !== 404) {
    throw new Error(`TEST 1 FAILED: Backend /admin/ returned status ${backendAdminRes.status()}, expected 404!`);
  }
  console.log('  ✓ Backend disabled /admin/ returns HTTP 404');

  await page.goto('http://127.0.0.1:3000/superadmin');
  await page.waitForSelector('text=PAGE NOT FOUND');
  console.log('  ✓ /superadmin returns plain 404');

  await page.goto('http://127.0.0.1:3000/short-slug/console');
  await page.waitForSelector('text=The requested page could not be found.');
  console.log('  ✓ Short slug probe (<16 chars) returns plain 404');
  console.log('  ✓ TEST 1 PASSED: Strict obscurity & uniform 404 cloaking verified.');

  // TEST 2: Valid secret path loads Super Admin portal
  console.log('\n[TEST 2] Accessing cloaked Super Admin Portal via secret slug...');
  const portalUrl = `http://127.0.0.1:3000/${TEST_SLUG}/console`;
  await page.goto(portalUrl);
  await page.waitForLoadState('domcontentloaded');
  await page.waitForSelector('text=Super Admin Console');

  const heading = await page.innerText('h1');
  console.log(`  Portal heading: "${heading}"`);
  if (!heading.includes('Super Admin Console')) {
    throw new Error('TEST 2 FAILED: Super Admin login portal did not render!');
  }
  console.log('  ✓ TEST 2 PASSED: Secret slug portal rendered securely.');

  // TEST 3: Login to Super Admin Console (with Mock API handler to test full authenticated UI)
  console.log('\n[TEST 3] Testing Super Admin Console authenticated dashboard & tabs...');

  // Setup mock route for the secret API path to thoroughly test the full dashboard tabs
  await page.route(`**/${TEST_SLUG}/api/**`, async (route) => {
    const url = route.request().url();
    const method = route.request().method();

    if (url.includes('/auth/me/')) {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          status: 'success',
          user: {
            username: 'harshposhiya',
            email: 'harshposhiya92@gmail.com',
            is_totp_enrolled: true,
            last_login_at: new Date().toISOString(),
            last_login_ip: '127.0.0.1',
            is_reauth_valid: true,
            remaining_recovery_codes: 8,
          },
        }),
      });
    }

    if (url.includes('/auth/login/')) {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          status: 'success',
          token: 'mock_sa_token_12345',
          user: {
            username: 'harshposhiya',
            email: 'harshposhiya92@gmail.com',
            is_totp_enrolled: true,
            last_login_at: new Date().toISOString(),
          },
        }),
      });
    }

    if (url.includes('/dashboard/')) {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          status: 'success',
          totals: {
            total_institutes: 5,
            active_institutes: 4,
            suspended_institutes: 1,
            total_departments: 12,
            total_faculty: 48,
            active_faculty: 45,
            total_students: 1250,
            active_students: 1230,
            total_exams: 180,
            live_exams_now: 3,
            attempts_today: 142,
            shortfall_exams: 2,
            failed_generation_jobs: 0,
            violations_today: 1,
          },
          health: {
            database: { status: 'healthy', latency_ms: 1.4 },
            ollama: { reachable: true, default_model: 'qwen2.5:3b-instruct', installed_models: ['qwen2.5:3b-instruct', 'llama3.2:3b'] },
            disk: { total_gb: 512, free_gb: 340 },
            active_jobs: 0,
          },
          recent_audits: [
            {
              id: 101,
              created_at: new Date().toISOString(),
              actor_username: 'harshposhiya',
              action: 'super_admin_login_success',
              target_entity: 'SuperAdminProfile',
              ip_address: '127.0.0.1',
              description: 'Successful owner authentication with 2FA.',
            },
          ],
        }),
      });
    }

    if (url.includes('/institutes/')) {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          status: 'success',
          data: [
            {
              id: 1,
              name: 'Pragyan Institute of Technology',
              code: 'INST-2026-001',
              status: 'active',
              admin_name: 'PITS Admin',
              admin_email: 'admin.pits@example.edu',
              faculty_count: 12,
              students_count: 350,
              exams_count: 45,
            },
          ],
          pagination: { total_pages: 1, total_count: 1, page: 1, page_size: 10 },
        }),
      });
    }

    if (url.includes('/users/')) {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          status: 'success',
          data: [
            {
              id: 2,
              full_name: 'Harsh Poshiya',
              email: 'harshposhiya92@gmail.com',
              role: 'student',
              identifier: 'STU-2026-0001',
              department: 'Computer Science',
              institution: { name: 'Pragyan Institute' },
            },
          ],
          pagination: { total_pages: 1, total_count: 1, page: 1, page_size: 10 },
        }),
      });
    }

    if (url.includes('/exams/')) {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          status: 'success',
          data: [
            {
              id: 88,
              title: 'Mid Term Advanced Operating Systems',
              subject: 'Operating Systems',
              department: 'Computer Science',
              institution: { name: 'Pragyan Institute' },
              total_marks: 100,
              target_total_marks: 100,
              marks_shortfall: 0,
              status: 'published',
              created_by: 'faculty_os',
            },
          ],
          pagination: { total_pages: 1, total_count: 1, page: 1, page_size: 10 },
        }),
      });
    }

    if (url.includes('/system/settings/')) {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          status: 'success',
          settings: {
            maintenance_mode: { enabled: false, message: '' },
          },
        }),
      });
    }

    if (url.includes('/system/audit-logs/')) {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          status: 'success',
          data: [
            {
              id: 1,
              created_at: new Date().toISOString(),
              actor_username: 'harshposhiya',
              action: 'super_admin_account_created',
              target_entity: 'SuperAdminProfile',
              ip_address: '127.0.0.1 (CLI)',
              description: 'Super Admin account created for harshposhiya',
            },
          ],
          pagination: { total_pages: 1, total_count: 1, page: 1, page_size: 25 },
        }),
      });
    }

    if (url.includes('/data/backups/')) {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          status: 'success',
          backups: [
            {
              filename: 'examai_pre_superadmin_dump.sql',
              size_mb: 1.82,
              created_at: new Date().toISOString(),
            },
          ],
        }),
      });
    }

    return route.continue();
  });

  // Perform login form submission
  await page.fill('input[type="password"]', 'SuperAdminSecretPassword@2026!');
  await page.fill('input[placeholder*="123456"]', '123456');
  await page.click('button[type="submit"]');

  await page.waitForSelector('text=System Operations Center', { timeout: 10000 });
  console.log('  ✓ Logged in: Dashboard rendered successfully!');

  // Verify tab switching
  console.log('\n[TEST 4] Testing Super Admin tab switching & feature views...');
  await page.click('button:has-text("Institutes")');
  await page.waitForSelector('text=Institutes Directory');
  console.log('  ✓ Institutes Tab loaded');

  await page.click('button:has-text("Users Directory")');
  await page.waitForSelector('text=Global Users Directory');
  console.log('  ✓ Users Directory Tab loaded');

  await page.click('button:has-text("Exams Overview")');
  await page.waitForSelector('text=Global Exams Manager');
  console.log('  ✓ Exams Overview Tab loaded');

  await page.click('button:has-text("System & Security")');
  await page.waitForSelector('text=System & Security Center');
  console.log('  ✓ System & Security Center loaded');

  await page.click('button:has-text("Data & Backups")');
  await page.waitForSelector('text=Data Management & Disaster Recovery');
  console.log('  ✓ Data & Backups loaded');

  // TEST 5: Zero horizontal scrollbar check across all required viewports
  console.log('\n[TEST 5] Verifying zero horizontal scrollbar across viewports (320px to 1920px)...');
  const viewports = [
    { width: 1920, height: 1080, name: '1920px' },
    { width: 1440, height: 900, name: '1440px' },
    { width: 1366, height: 768, name: '1366px' },
    { width: 1280, height: 800, name: '1280px' },
    { width: 1024, height: 768, name: '1024px' },
    { width: 768, height: 1024, name: '768px' },
    { width: 375, height: 812, name: '375px' },
    { width: 320, height: 568, name: '320px' },
  ];

  await page.click('button:has-text("Dashboard & Health")');
  await page.waitForSelector('text=System Operations Center');

  for (const vp of viewports) {
    await page.setViewportSize({ width: vp.width, height: vp.height });
    await page.waitForTimeout(300);

    const docScrollWidth = await page.evaluate(() => document.documentElement.scrollWidth);
    const docClientWidth = await page.evaluate(() => document.documentElement.clientWidth);
    const bodyScrollWidth = await page.evaluate(() => document.body.scrollWidth);
    const bodyClientWidth = await page.evaluate(() => document.body.clientWidth);

    const hasDocOverflow = docScrollWidth > docClientWidth + 1;
    const hasBodyOverflow = bodyScrollWidth > bodyClientWidth + 1;

    console.log(`  Viewport ${vp.name}: docOverflow=${hasDocOverflow}, bodyOverflow=${hasBodyOverflow}`);
    if (hasDocOverflow || hasBodyOverflow) {
      throw new Error(`TEST 5 FAILED: Horizontal scrollbar detected at viewport ${vp.name}!`);
    }

    // Capture visual artifact for key viewports
    if (['1920px', '768px', '375px'].includes(vp.name)) {
      const screenshotPath = path.join(ARTIFACT_DIR, `super_admin_dashboard_${vp.name}.png`);
      await page.screenshot({ path: screenshotPath });
      console.log(`    Captured visual artifact: super_admin_dashboard_${vp.name}.png`);
    }
  }

  console.log('  ✓ TEST 5 PASSED: Zero horizontal overflow confirmed across all viewports!');
  console.log('\n=== ALL PHASE 5 VERIFICATION TESTS PASSED SUCCESSFULLY! ===');
  await browser.close();
}

runSuperAdminVerification().catch((err) => {
  console.error('\nVERIFICATION FAILED:', err);
  process.exit(1);
});
